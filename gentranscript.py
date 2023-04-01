# Basic script based on video from 
# https://www.youtube.com/watch?v=2936_Y80nUk&t=506s
# to transcribe a youtube video

import os, sys, shutil
import tempfile
import argparse
from datetime import datetime

import whisper
from pytube import YouTube

def parse_arguments():
    parser = argparse.ArgumentParser(description='Transcribe a YouTube video')
    parser.add_argument('url', type=str, help='URL of the YouTube video')
    parser.add_argument('-o', '--output', type=str, default=None, help='Path for the output transcript file (default: transcripts/transcript_[date])')
    return parser.parse_args()

def main():
    args = parse_arguments()

    # Link to video
    url = args.url
    yt = YouTube(url)

    # Grab audio stream
    audio = yt.streams.filter(only_audio=True).first()
    folder = tempfile.mkdtemp()
    audio.download(output_path=folder,filename="audio.mp3")

    #Audio to Text
    model = whisper.load_model("base")
    result = model.transcribe(f"{folder}/audio.mp3")

    # Set default output path if not provided
    if args.output is None:
        date_str = datetime.now().strftime('%Y-%m-%d')
        output_path = f"./transcripts/transcript_{date_str}.txt"
    else:
        output_path = args.output

    write_transcript(url, result["text"], output_path)

    shutil.rmtree(folder)

def write_transcript(url, text, filename):
    with open(filename, "w") as file:
        file.write(f"Transcribed text for {url}\n")
        file.write(text)

if __name__ == "__main__":
    main()
