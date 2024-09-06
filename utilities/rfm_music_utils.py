import sys
import os
import re
import requests
from bs4 import BeautifulSoup
import random
import subprocess
import argparse
import yt_dlp as youtube_dl
from urllib.parse import urlparse, parse_qs
import logging
import time

# Constants
BASE_DOWNLOAD_DIRECTORY = "music_downloads"
AMACHA_DIRECTORY = os.path.join(BASE_DOWNLOAD_DIRECTORY, "amacha")
YOUTUBE_DIRECTORY = os.path.join(BASE_DOWNLOAD_DIRECTORY, "youtube")

# Utility Functions
def create_directories():
    if not os.path.exists(BASE_DOWNLOAD_DIRECTORY):
        os.makedirs(BASE_DOWNLOAD_DIRECTORY)
    if not os.path.exists(AMACHA_DIRECTORY):
        os.makedirs(AMACHA_DIRECTORY)
    if not os.path.exists(YOUTUBE_DIRECTORY):
        os.makedirs(YOUTUBE_DIRECTORY)

def standardize_youtube_url(url):
    parsed_url = urlparse(url)
    if parsed_url.hostname in ['www.youtube.com', 'youtube.com']:
        query = parse_qs(parsed_url.query)
        if 'v' in query:
            return f"https://www.youtube.com/watch?v={query['v'][0]}"
    elif parsed_url.hostname in ['youtu.be']:
        return f"https://www.youtube.com/watch?v={parsed_url.path[1:]}"
    return url

def trim_audio_to_length(filename, target_length):
    original_length = get_length(filename)
    num_loops = int(target_length / original_length)
    remainder_length = target_length % original_length

    looped_filenames = []
    for i in range(num_loops):
        looped_filenames.append(filename)

    if remainder_length > 0:
        partial_filename = f"{os.path.splitext(filename)[0]}_part_{remainder_length}s.mp3"
        subprocess.run(
            ["ffmpeg", "-i", filename, "-ss", "0", "-t", str(remainder_length), "-c", "copy", partial_filename, "-y"]
        )
        looped_filenames.append(partial_filename)
    
    with open("filelist.txt", "w") as f:
        for file in looped_filenames:
            f.write(f"file '{os.path.abspath(file)}'\n")
    
    trimmed_filename = f"{os.path.splitext(filename)[0]}_{target_length}s.mp3"
    subprocess.run(
        ["ffmpeg", "-f", "concat", "-safe", "0", "-i", "filelist.txt", "-c", "copy", trimmed_filename, "-y"]
    )

    os.remove("filelist.txt")
    for partial_file in looped_filenames:
        if partial_file != filename:
            os.remove(partial_file)

    os.remove(filename)
    return trimmed_filename

def get_length(filename):
    """ Get the length of an audio file using ffprobe. """
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", filename],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )
    return float(result.stdout)

def on_progress(d):
    """ Handle progress update for downloads. """
    if d['status'] == 'downloading':
        p = d['_percent_str']
        logging.info(f"Downloading... {p}")
        print(f"Downloading... {p}")

def get_youtube_video_details(video_link):
    """ Get the details of a YouTube video without downloading. """
    ydl_opts = {}
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_link, download=False)
    return {
        'title': info.get('title'),
        'link': video_link,
        'length': info.get('duration')
    }

# Amacha Functions
AMACHA_BASE_URL = "https://amachamusic.chagasi.com/"
AMACHA_GENRES = [

    "genre_rpg.html",


    "genre_techno.html",
    "genre_darktechno.html",

]

GENRE_DICT = {genre.split('_')[1].split('.')[0]: genre for genre in AMACHA_GENRES}

def get_amacha_mp3_links(genre_page_url):
    page = requests.get(genre_page_url)
    soup = BeautifulSoup(page.content, 'html.parser')
    mp3_links = [AMACHA_BASE_URL + a_tag['href'] for a_tag in soup.find_all('a', href=True) if a_tag['href'].endswith('.mp3')]
    return mp3_links

def get_amacha_all_pages(genre_url):
    page_urls = [genre_url]
    page = requests.get(genre_url)
    soup = BeautifulSoup(page.content, 'html.parser')
    pager = soup.find('ul', class_='pager')
    if pager:
        for a_tag in pager.find_all('a', href=True):
            page_url = AMACHA_BASE_URL + a_tag['href']
            if page_url not in page_urls:
                page_urls.append(page_url)
    return page_urls

def fetch_amacha_random_song(genre):
    if genre not in GENRE_DICT:
        print(f"Unsupported genre. Supported genres are: {', '.join(GENRE_DICT.keys())}")
        return None
    genre_url = AMACHA_BASE_URL + GENRE_DICT[genre]
    page_urls = get_amacha_all_pages(genre_url)
    all_mp3_links = []
    for page_url in page_urls:
        all_mp3_links.extend(get_amacha_mp3_links(page_url))
    if not all_mp3_links:
        print(f"No MP3 links found for the genre: {genre}")
        return None
    return random.choice(all_mp3_links)

def download_amacha_mp3(mp3_url, download_directory):
    filename = os.path.join(download_directory, re.sub(r'[^a-zA-Z0-9]', '_', mp3_url.split('/')[-1]))
    final_filename = f"{os.path.splitext(filename)[0]}.mp3"  # Final filename without clipping
    if os.path.exists(final_filename):
        print(f"File already exists: {final_filename}")
        return final_filename
    response = requests.get(mp3_url, stream=True)
    if response.status_code == 200:
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)
        print(f"Downloaded: {filename}")
        return filename
    else:
        print(f"Failed to download: {mp3_url}")
        return None

# YouTube Functions
def download_youtube_video(youtube_url, download_directory, length, retries=3):
    video_id = standardize_youtube_url(youtube_url).split('=')[-1]

    retry_count = 0
    while retry_count < retries:
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(download_directory, '%(title)s.%(ext)s'),
            'noplaylist': True,  # Ensuring no playlist is downloaded
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'progress_hooks': [on_progress],
        }

        try:
            with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(youtube_url, download=False)
                title = re.sub(r'[^a-zA-Z0-9]', '_', info_dict['title'])
                final_filename = os.path.join(download_directory, f"{video_id}_{title}_{length}s.mp3")
                if os.path.exists(final_filename):
                    print(f"File already exists: {final_filename}")
                    return final_filename

                info_dict = ydl.extract_info(youtube_url, download=True)
                downloaded_filename = ydl.prepare_filename(info_dict).replace('.webm', '.mp3').replace('.m4a', '.mp3')
                trimmed_filename = trim_audio_to_length(downloaded_filename, length)
                os.rename(trimmed_filename, final_filename)
                return final_filename
        except youtube_dl.utils.DownloadError as e:
            retry_count += 1
            wait_time = 2 ** retry_count
            print(f"Download error ({e}), retrying in {wait_time} seconds... (attempt {retry_count}/{retries})")
            time.sleep(wait_time)

    print(f"Failed to download video after {retries} attempts.")
    return None

# lilla specific logic for genre
LILLA_URLS = [
    "https://www.youtube.com/watch?v=Dn3Md8a7mQ0",
    "https://www.youtube.com/watch?v=Df4s5d1yPBM",
    "https://www.youtube.com/watch?v=lHOAcyQMyq0",
    "https://www.youtube.com/watch?v=l3phNdFl-uI",
    "https://www.youtube.com/watch?v=IO9-1R06LPY",
    "https://www.youtube.com/watch?v=fB1y0O_7QxA",
    "https://www.youtube.com/watch?v=FPiMtYmviP0",
    "https://www.youtube.com/watch?v=SAw4bFhkHio",
    "https://www.youtube.com/watch?v=O8s-OJQupJ0"
]

def fetch_lilla_random_song():
    youtube_url = random.choice(LILLA_URLS)
    return youtube_url

# Main Function
def main():
    parser = argparse.ArgumentParser(description="Download and trim AmachaMusic tracks or YouTube videos.")
    parser.add_argument("-genre", type=str, help="The genre of the music.")
    parser.add_argument("-youtube", type=str, help="YouTube video URL to download and trim.")
    parser.add_argument("-length", type=int, help="The length to trim the song or video to in seconds.")
    args = parser.parse_args()

    # Ensure directories exist
    create_directories()
    
    if args.length is None:
        args.length = 30  # Default length of 30 seconds

    if args.genre:
        genre = args.genre.strip().lower()
        if genre == "lilla":
            youtube_url = fetch_lilla_random_song()
            downloaded_file = download_youtube_video(youtube_url, YOUTUBE_DIRECTORY, args.length)
            if downloaded_file:
                print(f"Downloaded and trimmed file: {downloaded_file}")
            else:
                print("Failed to download and trim Lilla song.")
        elif genre in GENRE_DICT:
            song_url = fetch_amacha_random_song(genre)
            if song_url:
                print(f"Random {genre} song URL: {song_url}")
                downloaded_file = download_amacha_mp3(song_url, AMACHA_DIRECTORY)
                if downloaded_file:
                    final_file = f"{os.path.splitext(downloaded_file)[0]}_{args.length}s.mp3"
                    if os.path.exists(final_file):
                        print(f"Trimmed file already exists: {final_file}")
                    else:
                        trimmed_file = trim_audio_to_length(downloaded_file, args.length)
                        os.rename(trimmed_file, final_file)
                        print(f"Trimmed and saved file as: {final_file}")
        else:
            print(f"Unsupported genre. Supported genres are: {', '.join(GENRE_DICT.keys())}")
            sys.exit(1)
    elif args.youtube:
        youtube_url = standardize_youtube_url(args.youtube.strip())
        
        # Extract video details and check if file exists
        video_details = get_youtube_video_details(youtube_url)
        video_id = youtube_url.split('=')[-1]
        title = re.sub(r'[^a-zA-Z0-9]', '_', video_details['title'])
        final_filename = os.path.join(YOUTUBE_DIRECTORY, f"{video_id}_{title}_{args.length}s.mp3")
        
        if os.path.exists(final_filename):
            print(f"File already exists: {final_filename}")
        else:
            downloaded_file = download_youtube_video(youtube_url, YOUTUBE_DIRECTORY, args.length)
            if downloaded_file:
                print(f"Downloaded and trimmed file: {downloaded_file}")
            else:
                print("Failed to download and trim YouTube video.")
    else:
        # Default to downloading a random Amacha techno song at 30 seconds length
        genre = "techno"
        song_url = fetch_amacha_random_song(genre)
        if song_url:
            print(f"Random {genre} song URL: {song_url}")
            downloaded_file = download_amacha_mp3(song_url, AMACHA_DIRECTORY)
            if downloaded_file:
                final_file = f"{os.path.splitext(downloaded_file)[0]}_{args.length}s.mp3"
                if os.path.exists(final_file):
                    print(f"Trimmed file already exists: {final_file}")
                else:
                    trimmed_file = trim_audio_to_length(downloaded_file, args.length)
                    os.rename(trimmed_file, final_file)
                    print(f"Trimmed and saved file as: {final_file}")
        else:
            print(f"No MP3 links found for the genre: {genre}")

if __name__ == "__main__":
    main()