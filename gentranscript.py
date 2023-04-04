# Simple script for transcribing YouTube videos. Initial idea from:
# https://www.youtube.com/watch?v=2936_Y80nUk&t=506s
# End use is to transcribe a youtube video and then use it for Chat LLMs

import os
import sys
import tempfile
import argparse
from datetime import datetime
import re
import textwrap
from rich import print as rprint
from rich.panel import Panel
from rich.text import Text
from rich.padding import Padding

from pytube import YouTube
from transformers import pipeline
import whisper
import openai


def parse_arguments():
    parser = argparse.ArgumentParser(description='Transcribe a YouTube video')
    parser.add_argument('url', type=str, help='URL of the YouTube video')
    parser.add_argument('-tw', '--text-width', type=int,
                        default=80, help='Width to wrap the transcribed text.')
    parser.add_argument('-o', '--output', type=str, default=None,
                        help='Path for the output transcript file (default: transcript_[date])')
    parser.add_argument('-m', '--whisper-model', type=str, default="base",
                        help="See https://github.com/openai/whisper#available-models-and-languages for options.")
    parser.add_argument('-openai', '--open-ai-summary', action="store_true",
                        help="Summarize the transcript. Note OPENAI_API_KEY env variable should be set.")
    parser.add_argument('-bart', '--bart-summary',
                        action="store_true", help="Use a simple summary transformer that can run on low-end hardware.")
    return parser.parse_args()


def validate_youtube_url(url):
    youtube_regex = re.compile(r'(https?://)?(www\.)?youtube\.com/watch\?v=.+')
    match = youtube_regex.match(url)
    return match is not None


def get_video_id(url):
    video_id_regex = re.compile(
        r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]+)')
    match = video_id_regex.match(url)
    return match.group(1) if match else None


def download_audio(yt, video_id, cache_folder):
    audio_path = os.path.join(cache_folder, f"{video_id}.mp3")

    if not os.path.exists(audio_path):
        # Grab audio stream
        audio = yt.streams.filter(only_audio=True).first()
        audio.download(output_path=cache_folder, filename=f"{video_id}.mp3")
        print(
            f"Finished downloading audio for video ID: {video_id}. Caching temporarily.")
    else:
        print(f"Reusing cached download for video ID: {video_id}")

    return audio_path


def write_transcript(url, text, filename, width=80):
    # Adjust the width as desired
    wrapped_text = textwrap.fill(text, width=width)
    with open(filename, "w") as file:
        file.write(f"Transcribed text for {url}\n")
        file.write(wrapped_text)


def split_text_into_chunks(text, max_chunk_size=2048):
    words = text.split()
    chunks = []
    current_chunk = []

    for word in words:
        current_chunk.append(word)
        if sum(len(w) for w in current_chunk) > max_chunk_size - 1:
            chunks.append(' '.join(current_chunk))
            current_chunk = []

    if current_chunk:
        chunks.append(' '.join(current_chunk))

    return chunks


def bart_summarize(text: str, max_chunk_size: int = 1024, max_length: int = 50, min_length: int = 25) -> str:

    text_chunks = split_text_into_chunks(text, max_chunk_size=max_chunk_size)
    summaries = []

    summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-12-6",
                          device=0 if sys.platform == "cuda" else -1)

    for chunk in text_chunks:
        summary = summarizer(chunk, max_length=max_length,
                             min_length=min_length, do_sample=False)
        summaries.append(summary[0]["summary_text"])

    return "".join(summaries)


def gpt_completion(prompt, model, max_tokens):
    response = openai.Completion.create(
        engine=model,
        prompt=prompt,
        max_tokens=max_tokens,  # Adjust the number of tokens based on the desired summary length
        n=1,
        stop=None,
        temperature=0.7,
    )
    return response


def gpt_summarize_key_points(text, model="text-davinci-003", max_tokens=150):
    """
    Summarize the given text and list key points using OpenAI GPT model.

    :param text: str, input text to be summarized
    :param model: str, name of the GPT model to use (default: "text-davinci-003")
    :param max_tokens: int = 150
    :return: str, summarized text with key points
    """
    openai.api_key = os.getenv("OPENAI_API_KEY")

    text_chunks = split_text_into_chunks(text)
    summaries = ""

    for chunk in text_chunks[:-1]:
        prompt = f"Please summarize the following audio transcribed text:\n\n{chunk}"
        response = gpt_completion(chunk, model, max_tokens)
        summaries += response.choices[0].text.strip() + "\n"

    prompt = f"Please provide 2-4 sentence summary and a list of key points from the combined summaries of audio transcribed text:\n\n{summaries}"
    response = gpt_completion(prompt, model, max_tokens)
    response = response.choices[0].text.strip() + "\n"

    return response.strip()


def blend_colors(color1, color2, alpha):
    """
    Create effective alpha for display box
    """
    r1, g1, b1 = int(color1[1:3], 16), int(
        color1[3:5], 16), int(color1[5:7], 16)
    r2, g2, b2 = int(color2[1:3], 16), int(
        color2[3:5], 16), int(color2[5:7], 16)
    r = int(r1 * alpha + r2 * (1 - alpha))
    g = int(g1 * alpha + g2 * (1 - alpha))
    b = int(b1 * alpha + b2 * (1 - alpha))
    return f"#{r:02x}{g:02x}{b:02x}"


def display_summary(summary, url):
    """
    Display the summary text in a styled format in the terminal.

    :param summary: str, summarized text with key points
    """
    background_color = "#ADD8E6"
    terminal_color = "#D3D3D3"
    alpha = 0.5

    blended_color = blend_colors(background_color, terminal_color, alpha)

    # Split the summary into lines and add bullets for lists
    lines = summary.split("\n")
    formatted_lines = []

    for line in lines:
        if line.startswith(" - ") or line.startswith(" • "):
            formatted_line = Text()
            formatted_line.append(" • ", style="bold green")
            formatted_line.append(line[3:])
        else:
            formatted_line = line

        formatted_lines.append(formatted_line)

    # Create a rich text object with formatted lines and blended background color
    formatted_summary = Text("\n".join(str(
        line) for line in formatted_lines), justify="left", style=f"bg:{blended_color}")

    # Add padding and create a panel around the text
    padded_summary = Padding(formatted_summary, (1, 2))
    panel = Panel(padded_summary, expand=True,
                  title=f"Summary for {url}", title_align="left")

    # Print the styled panel
    rprint(panel)


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

    # Audio to Text
    model = whisper.load_model(args.whisper_model)
    result = model.transcribe(audio_path, fp16=False)

    # Set default output path if not provided
    if args.output is None:
        date_str = datetime.now().strftime('%Y-%m-%d')
        output_path = f"transcript_{date_str}.txt"
    else:
        output_path = args.output

    write_transcript(url, result["text"], output_path, width=args.text_width)

    if args.open_ai_summary:
        summary = gpt_summarize_key_points(result['text'])
        display_summary(summary, args.url)
    elif args.bart_summary:
        summary = bart_summarize(result['text'])
        display_summary(summary, args.url)


if __name__ == "__main__":
    main()
