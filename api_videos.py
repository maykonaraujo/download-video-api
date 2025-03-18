from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse, JSONResponse
import yt_dlp
import io
import logging
from typing import Optional, List, Dict, Any
import uvicorn
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import os
import tempfile
import shutil
import ssl
import certifi

# Configuração do logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Forçar o uso do certifi para certificados SSL
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

# Desativar verificação de certificado SSL para yt-dlp (não recomendado em produção, mas pode resolver o problema temporariamente)
ssl._create_default_https_context = ssl._create_unverified_context

# Criação da aplicação FastAPI
app = FastAPI(
    title="YouTube Video Downloader API",
    description="API para download de vídeos do YouTube",
    version="1.0.0"
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class VideoInfo(BaseModel):
    title: str
    uploader: str
    duration: int
    thumbnail: str
    formats: List[Dict[str, Any]]

@app.get("/")
async def root():
    return {"message": "YouTube Video Downloader API. Use /info para informações e /download para baixar vídeos."}

@app.get("/info")
async def get_video_info(url: str = Query(..., description="URL do vídeo do YouTube")):
    try:
        logger.info(f"Obtendo informações do vídeo: {url}")
        
        # Configurações do yt-dlp para evitar detecção como bot e problemas de SSL
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,  # Ignora erros de certificado
            'ignoreerrors': False,
            'no_call_home': True,
            'format': 'best',
            'noprogress': True,
        }
        
        # Obter informações do vídeo
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
        # Extrair formatos disponíveis
        formats = []
        for f in info.get('formats', []):
            if f.get('height') and f.get('ext') == 'mp4':
                formats.append({
                    'format_id': f.get('format_id'),
                    'resolution': f'{f.get("height")}p',
                    'ext': f.get('ext'),
                    'filesize': f.get('filesize')
                })
        
        # Remover duplicados com base na resolução
        unique_formats = []
        seen_resolutions = set()
        for fmt in formats:
            if fmt['resolution'] not in seen_resolutions:
                seen_resolutions.add(fmt['resolution'])
                unique_formats.append(fmt)
        
        # Ordenar por resolução (maior para menor)
        unique_formats.sort(key=lambda x: int(x['resolution'].replace('p', '')), reverse=True)
        
        video_info = VideoInfo(
            title=info.get('title', 'Unknown'),
            uploader=info.get('uploader', 'Unknown'),
            duration=info.get('duration', 0),
            thumbnail=info.get('thumbnail', ''),
            formats=unique_formats
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
        temp_dir = tempfile.mkdtemp()
        
        try:
            height = int(resolution.replace('p', ''))
            # Configurar formato baseado na resolução solicitada
            format_str = f'bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/best[height<={height}][ext=mp4]/best[ext=mp4]/best'
            
            logger.info(f"Obtendo informações do vídeo: {url}")
        
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'nocheckcertificate': True,
                'ssl_verify': False,  # Contorna o erro SSL temporariamente
                'ignoreerrors': False,
                'no_call_home': True,
                'format': 'best',
                'noprogress': True,
            }
            
            # Baixar o vídeo
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                filename = ydl.prepare_filename(info)
            
            # Verificar se o arquivo existe
            if not os.path.exists(filename):
                # Tentar encontrar o arquivo com extensão mp4
                possible_filename = os.path.join(temp_dir, 'video.mp4')
                if os.path.exists(possible_filename):
                    filename = possible_filename
                else:
                    # Procurar qualquer arquivo no diretório
                    files = [f for f in os.listdir(temp_dir) if os.path.isfile(os.path.join(temp_dir, f))]
                    if files:
                        filename = os.path.join(temp_dir, files[0])
                    else:
                        raise FileNotFoundError("Arquivo de vídeo não encontrado após o download")
            
            # Preparar nome para o download
            safe_title = ''.join(c for c in info.get('title', 'video') if c.isalnum() or c in ['_', '.', '-']).replace(' ', '_')
            download_filename = f"{safe_title}.mp4"
            
            # Ler o arquivo para memória
            with open(filename, 'rb') as f:
                buffer = io.BytesIO(f.read())
            
            # Retornar o vídeo como resposta de streaming
            return StreamingResponse(
                buffer,
                media_type="video/mp4",
                headers={
                    "Content-Disposition": f'attachment; filename="{download_filename}"',
                    "Content-Length": str(os.path.getsize(filename))
                }
            )
            
        finally:
            # Limpar arquivos temporários
            shutil.rmtree(temp_dir, ignore_errors=True)
            
    except Exception as e:
        logger.error(f"Erro ao baixar vídeo: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao baixar vídeo: {str(e)}")

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)