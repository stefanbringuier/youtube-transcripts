# Simple script for transcribing YouTube videos. Initial idea from:
# https://www.youtube.com/watch?v=2936_Y80nUk&t=506s
# End use is to transcribe a youtube video and then use it for Chat LLMs

import os, sys
import tempfile
import argparse
from datetime import datetime
import re
import textwrap
import whisper
from pytube import YouTube

def parse_arguments():
    parser = argparse.ArgumentParser(description='Transcribe a YouTube video')
    parser.add_argument('url', type=str, help='URL of the YouTube video')
    parser.add_argument('-tw', '--text-width', type=int, default=80, help='Width to wrap the transcribed text.')
    parser.add_argument('-o', '--output', type=str, default=None, help='Path for the output transcript file (default: transcripts/transcript_[date])')
    parser.add_argument('-m', '--whisper-model',type=str, default="base", help="See https://github.com/openai/whisper#available-models-and-languages for options.")
    return parser.parse_args()

def validate_youtube_url(url):
    youtube_regex = re.compile(r'(https?://)?(www\.)?youtube\.com/watch\?v=.+')
    match = youtube_regex.match(url)
    return match is not None


def get_video_id(url):
    video_id_regex = re.compile(r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]+)')
    match = video_id_regex.match(url)
    return match.group(1) if match else None

def download_audio(yt, video_id, cache_folder):
    audio_path = os.path.join(cache_folder, f"{video_id}.mp3")

    if not os.path.exists(audio_path):
        # Grab audio stream
        audio = yt.streams.filter(only_audio=True).first()
        audio.download(output_path=cache_folder, filename=f"{video_id}.mp3")
        print(f"Finished downloading audio for video ID: {video_id}")
    else:
        print(f"Reusing cached download for video ID: {video_id}")

    return audio_path

def write_transcript(url, text, filename,width=80):
    wrapped_text = textwrap.fill(text, width=width)  # Adjust the width as desired
    with open(filename, "w") as file:
        file.write(f"Transcribed text for {url}\n")
        file.write(wrapped_text)

def main():
    args = parse_arguments()

    if not validate_youtube_url(args.url):
        print("Error: Only YouTube URLs are supported.")
        sys.exit(1)

    # Link to video
    url = args.url
    yt = YouTube(url)
    video_id = get_video_id(url)

    # Create temporary cache folder
    cache_folder = os.path.join(tempfile.gettempdir(), "youtube_audio_cache")
    os.makedirs(cache_folder, exist_ok=True)

    # Download or reuse audio
    audio_path = download_audio(yt, video_id, cache_folder)

    #Audio to Text
    model = whisper.load_model(args.whisper_model)
    result = model.transcribe(audio_path,fp16=False)

    # Set default output path if not provided
    if args.output is None:
        date_str = datetime.now().strftime('%Y-%m-%d')
        output_path = f"./transcripts/transcript_{date_str}.txt"
    else:
        output_path = args.output

    write_transcript(url, result["text"], output_path,width=args.text_width)

if __name__ == "__main__":
    main()
