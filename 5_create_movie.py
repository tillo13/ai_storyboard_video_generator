import os
import re
import shutil
import argparse
import subprocess
import random
import json
import time
from PIL import Image
from datetime import datetime
import yt_dlp  # Import yt-dlp properly

from utilities.rfm_music_utils import (
    create_directories, fetch_lilla_random_song, download_youtube_video,
    fetch_amacha_random_song, download_amacha_mp3, GENRE_DICT,
    YOUTUBE_DIRECTORY, trim_audio_to_length
)
from utilities.google_tts_utils import generate_tts_audio, adjust_audio_speed  # Import adjust_audio_speed

try:
    from GLOBAL_VARIABLES import DEFAULT_VIDEO_LENGTH as GLOBAL_DEFAULT_VIDEO_LENGTH
    from GLOBAL_VARIABLES import USER_PROVIDED_YOUTUBE_MUSIC
except ImportError:
    GLOBAL_DEFAULT_VIDEO_LENGTH = 55
    USER_PROVIDED_YOUTUBE_MUSIC = ""

# Configurations
output_folder = 'enhanced_images'
videos_folder = 'created_videos'
temp_tts_creation = 'temp_tts_creation'  # Folder to store all temporary files
temp_group_folder = os.path.join(temp_tts_creation, 'temp_group_images')
temp_image_folder = os.path.join(temp_tts_creation, 'temp_images_on_create_video')
tts_durations_folder = os.path.join(temp_tts_creation, 'tts_durations')
storylines_folder = 'storylines'

# Speed of the speech (normal speed is 1.0)
SPEED_OF_SPEECH = 1.4  # Recommended range: 0.5 to 2.0; lower for slower, higher for faster.

def ensure_directory_exists(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)

def convert_images_to_jpeg(image_folder, temp_directory):
    """Convert all images in the folder to JPEG and save with consistent naming, with retries."""
    image_files = sorted(f for f in os.listdir(image_folder) if f.lower().endswith(('.jpg', '.jpeg', '.png')))
    temp_image_paths = []
   
    def convert_image_with_retries(image_path, output_path, retry_attempts=3):
        for attempt in range(1, retry_attempts + 3):
            try:
                img = Image.open(image_path).convert('RGB')
                img.save(output_path, 'JPEG')
                temp_image_paths.append(output_path)
                return True
            except Exception as e:
                print(f"Attempt {attempt} failed for {image_path}: {e}")
                if attempt < retry_attempts:
                    print(f"Retrying in {attempt * 2} seconds...")
                    time.sleep(attempt * 2)
        return False

    for i, image_file in enumerate(image_files):
        image_path = os.path.join(image_folder, image_file)
        output_path = os.path.join(temp_directory, f'img{i:03d}.jpg')
        success = convert_image_with_retries(image_path, output_path)
        if not success:
            print(f"Failed to convert {image_file} after multiple attempts.")
    
    return temp_image_paths

def generate_video_from_images(image_folder, audio_file, output_file, display_durations, temp_directory):
    # Ensure all directories exist
    ensure_directory_exists(temp_directory)

    temp_jpeg_images = convert_images_to_jpeg(image_folder, temp_directory)
    
    input_txt_path = os.path.join(temp_directory, 'input.txt')
    # Opening the input file within the context so it's properly handled
    with open(input_txt_path, 'w') as f:
        for i, (image_file, duration) in enumerate(zip(temp_jpeg_images, display_durations)):
            f.write(f"file '{os.path.abspath(image_file)}'\n")
            f.write(f"duration {duration}\n")
            
        # Ensure the last image duration is specified to avoid issues
        if temp_jpeg_images:
            last_duration = display_durations[-1]
            f.write(f"file '{os.path.abspath(temp_jpeg_images[-1])}'\n")
            f.write(f"duration {last_duration}\n")

    # Run ffmpeg to process the video
    subprocess.run([
        'ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', input_txt_path, '-i', audio_file,
        '-c:v', 'libx264', '-vf', 'scale=-2:720,setsar=1', 
        '-shortest', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', output_file
    ], check=True)
    
    # Clean up the temporary JPEG files and input.txt
    for temp_file in temp_jpeg_images:
        os.remove(temp_file)
    os.remove(input_txt_path)

def sanitize_filename(filename):
    """Sanitize the filename to be alphanumeric with underscores, preserving extension."""
    # Split the filename into name and extension
    name, ext = os.path.splitext(filename)
    # Replace non-alphanumeric characters with underscores
    name = re.sub(r'\W+', '_', name)
    # Remove double underscores
    name = re.sub(r'__+', '_', name)
    # Convert to lowercase
    name = name.lower()
    return name + ext

def convert_to_mp3(input_filepath, output_filepath):
    """Convert an audio file to mp3 using ffmpeg."""
    try:
        # Direct ffmpeg command to convert audio files
        result = subprocess.run(
            ['ffmpeg', '-y', '-i', input_filepath, '-q:a', '0', '-map', 'a', output_filepath],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print("Conversion failed.")
        print(f"Command: {e.cmd}")
        print(f"Return Code: {e.returncode}")
        print(f"Output: {e.stdout}")
        print(f"Error: {e.stderr}")
        return False


def download_youtube_video(url, output_dir, video_length):
    """Download a video from YouTube and sanitize the filename, converting audio to mp3 if necessary."""
    try:
        # Ensure the output directory exists
        ensure_directory_exists(output_dir)
        
        # Set yt-dlp options to download the file into the correct directory
        ydl_opts = {
            'format': 'bestaudio',
            'extract-audio': True,
            'audio-format': 'm4a',  # Initial format to download before conversion
            'outtmpl': os.path.join(output_dir, '%(title)s.%(ext)s'),  # Filename template
            'restrict-filenames': True  # This ensures filenames are more neutral
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            original_title = info_dict.get('title', None)
            if original_title is None:
                raise Exception("Failed to retrieve title from downloaded info.")
            
            # Sanitize the original title
            sanitized_title = sanitize_filename(original_title)
            
            # Determine the downloaded m4a file path
            original_filepath = os.path.join(output_dir, f"{original_title}.m4a")
            sanitized_filepath = os.path.join(output_dir, f"{sanitized_title}.m4a")

            # Rename the file to sanitized filename
            if os.path.exists(original_filepath):
                os.rename(original_filepath, sanitized_filepath)
            else:
                raise Exception(f"Downloaded file not found: {original_filepath}")
            
            print(f"[DEBUG] Original filename: {original_filepath}")
            print(f"[DEBUG] Renamed to sanitized filename: {sanitized_filepath}")
            
            # Now, convert sanitized m4a to mp3
            mp3_filepath = os.path.join(output_dir, f"{sanitized_title}.mp3")
            if convert_to_mp3(sanitized_filepath, mp3_filepath):
                os.remove(sanitized_filepath)  # Remove the original m4a file if conversion is successful
                return mp3_filepath
            else:
                return sanitized_filepath  # Fallback to the original file if conversion fails

    except Exception as e:
        print(f"Download failed: {e}")
        return None

def download_audio(video_length):
    """Download the audio file based on the provided YouTube link or pick a random song."""
    try:
        if USER_PROVIDED_YOUTUBE_MUSIC:
            file_path = download_youtube_video(USER_PROVIDED_YOUTUBE_MUSIC, YOUTUBE_DIRECTORY, video_length)
        else:
            genre_choice = random.choice(list(GENRE_DICT.keys()) + ['lilla'])
            if genre_choice == 'lilla':
                file_path = download_youtube_video(fetch_lilla_random_song(), YOUTUBE_DIRECTORY, video_length)
            else:
                file_path = download_amacha_mp3(fetch_amacha_random_song(genre_choice), YOUTUBE_DIRECTORY)
                file_path = trim_audio_to_length(file_path, video_length)
        return file_path if file_path else None
    except Exception as e:
        print(f"Audio download failed: {e}")
        return None

def unique_filepath(filepath):
    if not os.path.exists(filepath):
        return filepath
    base, ext = os.path.splitext(filepath)
    return f"{base}_{datetime.now().strftime('%H%M%S')}{ext}"

def get_latest_summary_file(directory):
    latest_file, latest_time = None, None
    formats = ["%Y-%m-%d_%H-%M", "%Y%m%d_%H%M%S"]
    for filename in os.listdir(directory):
        if filename.endswith("_summaries.json"):
            for fmt in formats:
                try:
                    file_time = datetime.strptime(filename[:16], fmt)
                    if not latest_time or file_time > latest_time:
                        latest_time, latest_file = file_time, os.path.join(directory, filename)
                except ValueError:
                    continue
    return latest_file

def read_json(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    except Exception as e:
        print(f"[ERROR] Failed to read JSON file {file_path}: {e}")
        return None

def write_json(data, file_path):
    try:
        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump(data, file, ensure_ascii=False, indent=4)
        print(f"[INFO] JSON file {file_path} updated successfully.")
    except Exception as e:
        print(f"[ERROR] Failed to write to JSON file {file_path}: {e}")

def find_enhanced_images(data):
    enhanced_images = {}
    for chapter in data.get("story_chapters", []):
        for key, value in chapter.items():
            if key.startswith("chapter_image_location_"):
                if "_subtitled" not in key and "enhanced_images" in value:
                    model_name = key.replace("chapter_image_location_", "")
                    if model_name not in enhanced_images:
                        enhanced_images[model_name] = []
                    enhanced_images[model_name].append((value, chapter["chapter_summary"], chapter))
    return enhanced_images

def sanitize_filename_component(component, length=20):
    sanitized = re.sub(r'\W+', '_', component.lower())
    sanitized = re.sub(r'__+', '_', sanitized)  # Remove double underscores
    return sanitized[:length]

def generate_video_filename(model_name, chapter_summary, audio_file, group_time_str, final_video_length):
    chapter_part = sanitize_filename_component(chapter_summary)
    audio_base = sanitize_filename_component(os.path.splitext(os.path.basename(audio_file))[0])
    return f"{model_name}_{chapter_part}_{audio_base}_{group_time_str}_{int(final_video_length)}s.mp4"

def cleanup_temp_directories():
    if os.path.exists(temp_tts_creation):
        shutil.rmtree(temp_tts_creation)

def update_json_with_timings(data, enhanced_images, chapters_info):
    """Update the JSON data with start and end times for each chapter."""
    for model_name, images_and_summaries in enhanced_images.items():
        for i, (_, summary, chapter) in enumerate(images_and_summaries):
            start_time = chapters_info[model_name][i]["chapter_summary_start_time"]
            end_time = chapters_info[model_name][i]["chapter_summary_end_time"]
            chapter["chapter_summary_start_time"] = start_time
            chapter["chapter_summary_end_time"] = end_time
    return data

def main():
    parser = argparse.ArgumentParser(description="Create movie from enhanced images.")
    parser.add_argument('-length', type=int, default=GLOBAL_DEFAULT_VIDEO_LENGTH, help="Desired length of the video in seconds.")
    args = parser.parse_args()
    video_length = args.length

    ensure_directory_exists(videos_folder)
    ensure_directory_exists(temp_group_folder)
    ensure_directory_exists(temp_image_folder)
    ensure_directory_exists(tts_durations_folder)

    json_file_path = get_latest_summary_file(storylines_folder)
    if not json_file_path:
        print("[ERROR] No summary JSON file found.")
        return

    data = read_json(json_file_path)
    if data is None:
        return

    enhanced_images = find_enhanced_images(data)
    if not enhanced_images:
        print("[INFO] No enhanced images found.")
        return

    created_videos = {}
    chapters_info = {}

    for model_name, images_and_summaries in enhanced_images.items():
        model_run_folder = f"{model_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        model_run_path = os.path.join(output_folder, model_run_folder)
        ensure_directory_exists(model_run_path)

        temp_image_subfolder = os.path.join(temp_image_folder, model_name)
        ensure_directory_exists(temp_image_subfolder)

        image_files = [img for img, summary, _ in images_and_summaries]
        num_images = len(image_files)
        if not num_images:
            print(f"No image files found for '{model_name}'.")
            continue

        # Calculate and store adjusted TTS durations for each chapter summary
        tts_durations = []
        chapter_info_list = []  # To store start and end time for each chapter
        current_time = 0.0  # Start time for the first chapter
        for i, (_, summary, chapter) in enumerate(images_and_summaries):
            tts_audio_file = os.path.join(tts_durations_folder, f"tts_{model_name}_{i}.mp3")
            generate_tts_audio(summary, output_file=tts_audio_file)

            # Adjust the speed of the TTS audio
            adjusted_tts_audio_file = os.path.join(tts_durations_folder, f"tts_{model_name}_{i}_adjusted.mp3")
            adjust_audio_speed(tts_audio_file, SPEED_OF_SPEECH, output_file=adjusted_tts_audio_file)
            
            result = subprocess.run(
                ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', adjusted_tts_audio_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT
            )
            tts_duration = float(result.stdout)
            tts_durations.append(tts_duration)

            # Store chapter summary start and end times
            chapter_info = {
                "chapter_summary_start_time": current_time,
                "chapter_summary_end_time": current_time + tts_duration
            }
            chapter_info_list.append(chapter_info)

            # Update current time for the next chapter
            current_time += tts_duration

        # Save chapter info for the current model
        chapters_info[model_name] = chapter_info_list

        # Calculate display duration for each image
        display_durations = [max(duration, 5.0) for duration in tts_durations]  # Ensure minimum duration of 5 seconds

        final_video_length = sum(display_durations)

        audio_file = download_audio(final_video_length)
        if not audio_file:
            print(f"Failed to obtain audio for '{model_name}'. Keeping files for troubleshooting.")
            continue

        group_time_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_video = os.path.join(videos_folder, generate_video_filename(model_name, images_and_summaries[0][1], audio_file, group_time_str, final_video_length))

        print(f"Creating movie for model '{model_name}' at time '{group_time_str}' with {num_images} images, total video length: {final_video_length:.2f} seconds")
        group_temp_dir = os.path.join(temp_group_folder, f"{model_name}_{group_time_str}")
        ensure_directory_exists(group_temp_dir)

        for image_path, chapter_summary, _ in images_and_summaries:
            shutil.copy(image_path, group_temp_dir)

        generate_video_from_images(group_temp_dir, audio_file, output_video, display_durations, temp_image_subfolder)
        print(f"Movie for model '{model_name}' created successfully at '{output_video}'.")

        created_videos[f"created_video_location_{model_name.replace('/', '_')}"] = output_video

        print(f"Suggestion: Remove images in '{model_run_path}' if successful.")
        
    # Update the JSON data with the timings
    updated_data = update_json_with_timings(data, enhanced_images, chapters_info)

    # Merge created videos into the original data
    updated_data.update(created_videos)

    # Write the updated data back to the JSON file
    write_json(updated_data, json_file_path)

    # Clean up temporary directories
    cleanup_temp_directories()

if __name__ == "__main__":
    create_directories()
    main()