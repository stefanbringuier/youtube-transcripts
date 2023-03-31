# Basic script based on video from 
# https://www.youtube.com/watch?v=2936_Y80nUk&t=506s
# to transcribe a youtube video

import os, sys, shutil
import tempfile

import whisper
from pytube import YouTube


# Link to video
url = sys.argv[1]
yt = YouTube(url)

# Grab audio stream
audio = yt.streams.filter(only_audio=True).first()
folder = tempfile.mkdtemp()
audio.download(output_path=folder,filename="audio.mp3")

#Audio to Text
model = whisper.load_model("base")
result = model.transcribe(f"{folder}/audio.mp3")

def create_and_open_txt(url,text, filename):
    with open(filename, "w") as file:
        file.write(f"Transcribed text for {url}\n")
        file.write(text)

create_and_open_txt(url,result["text"],f"./transcripts/{sys.argv[2]}")

shutil.rmtree(folder)