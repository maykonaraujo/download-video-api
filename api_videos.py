from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse, JSONResponse
from pytube import YouTube
import io
import random
import logging
from typing import Optional
import uvicorn
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

# Configuração do logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Lista de user agents para simular diferentes navegadores
user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0"
]

# Criação da aplicação FastAPI
app = FastAPI(
    title="YouTube Video Downloader API",
    description="API para download de vídeos do YouTube com headers que evitam detecção como bot",
    version="1.0.0"
)

# Configurar CORS para permitir requisições de diferentes origens
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permitir todas as origens
    allow_credentials=True,
    allow_methods=["*"],  # Permitir todos os métodos
    allow_headers=["*"],  # Permitir todos os headers
)

class VideoInfo(BaseModel):
    title: str
    author: str
    length: int
    thumbnail_url: str
    available_resolutions: list

@app.get("/")
async def root():
    return {"message": "YouTube Video Downloader API. Use /download endpoint with a URL parameter."}

@app.get("/info")
async def get_video_info(url: str = Query(..., description="URL do vídeo do YouTube")):
    try:
        logger.info(f"Obtendo informações do vídeo: {url}")
        
        # Usar um User-Agent aleatório
        headers = {
            'User-Agent': random.choice(user_agents),
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Connection': 'keep-alive',
            'DNT': '1',  # Do Not Track
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
            'Referer': 'https://www.google.com/'
        }
        
        # Criar instância do YouTube com os headers personalizados
        yt = YouTube(url)
        yt._http._headers.update(headers)  # Adicionar headers personalizados
        
        # Obter streams disponíveis
        streams = yt.streams.filter(progressive=True)
        available_resolutions = [f"{stream.resolution} - {stream.mime_type}" for stream in streams]
        
        video_info = VideoInfo(
            title=yt.title,
            author=yt.author,
            length=yt.length,
            thumbnail_url=yt.thumbnail_url,
            available_resolutions=available_resolutions
        )
        
        return video_info
        
    except Exception as e:
        logger.error(f"Erro ao obter informações do vídeo: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao processar o vídeo: {str(e)}")

@app.get("/download")
async def download_video(
    url: str = Query(..., description="URL do vídeo do YouTube"),
    resolution: Optional[str] = Query("720p", description="Resolução do vídeo (ex: 720p, 480p, 360p)")
):
    try:
        logger.info(f"Iniciando download do vídeo: {url} com resolução {resolution}")
        
        # Usar um User-Agent aleatório
        headers = {
            'User-Agent': random.choice(user_agents),
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Connection': 'keep-alive',
            'DNT': '1',  # Do Not Track
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
            'Referer': 'https://www.google.com/'
        }
        
        # Criar instância do YouTube com os headers personalizados
        yt = YouTube(url)
        yt._http._headers.update(headers)  # Adicionar headers personalizados
        
        # Selecionar stream com a resolução desejada ou a mais próxima disponível
        stream = yt.streams.filter(progressive=True, res=resolution).first()
        
        # Se não encontrar a resolução específica, pegar a melhor disponível
        if not stream:
            logger.warning(f"Resolução {resolution} não disponível, usando a melhor resolução disponível")
            stream = yt.streams.filter(progressive=True).order_by('resolution').desc().first()
            
        if not stream:
            logger.error("Nenhum stream disponível para download")
            raise HTTPException(status_code=404, detail="Nenhum stream disponível para download")
        
        # Download do vídeo para buffer
        buffer = io.BytesIO()
        stream.stream_to_buffer(buffer)
        buffer.seek(0)
        
        # Nome do arquivo para download
        filename = f"{yt.title.replace(' ', '_')}.mp4"
        filename = ''.join(c for c in filename if c.isalnum() or c in ['_', '.', '-'])
        
        # Retornar o vídeo como resposta de streaming
        return StreamingResponse(
            buffer,
            media_type="video/mp4",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(buffer.getbuffer().nbytes)
            }
        )
        
    except Exception as e:
        logger.error(f"Erro ao baixar vídeo: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao baixar vídeo: {str(e)}")

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)