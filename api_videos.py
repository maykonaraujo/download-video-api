from fastapi import FastAPI
from fastapi.responses import FileResponse
import os
import yt_dlp

app = FastAPI()

@app.get("/")
def home():
    return {"message": "API de Download de Vídeos da Web"}

@app.get("/youtube/")
def download_video(url: str):
    download_path = "videos/youtube"
    os.makedirs(download_path, exist_ok=True)

    ydl_opts = {
        'format': 'best',
        'outtmpl': f'{download_path}/%(title)s.%(ext)s',
        'noplaylist': True
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        file_name = ydl.prepare_filename(info)

    return FileResponse(file_name, media_type="video/mp4", filename=os.path.basename(file_name))

