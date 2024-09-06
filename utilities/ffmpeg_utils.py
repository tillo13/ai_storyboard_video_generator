# ffmpeg_utils.py

import ffmpeg
import os
import subprocess
import textwrap
import requests
from mutagen.mp3 import MP3
import shutil


# Function to get the length of a media file using ffprobe
def get_length(filename):
    result = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                             "format=duration", "-of",
                             "default=noprint_wrappers=1:nokey=1", filename],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    return float(result.stdout)


# Function to download an image from a URL
def download_image(url, dest_folder, filename):
    response = requests.get(url)
    if response.status_code == 200:
        with open(os.path.join(dest_folder, filename), 'wb') as f:
            f.write(response.content)
    else:
        print(f"Error downloading {url}: Status code {response.status_code}")


# Function to get a list of image files from a folder, sorted by creation or last modification date
def get_image_files(directory):
    # Get a list of files with their creation times
    files = [(os.path.join(directory, f), os.path.getctime(os.path.join(directory, f))) 
             for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
    
    # Sort files by creation time
    files.sort(key=lambda x: x[1])
    
    # Return only the file paths
    return [f[0] for f in files]

# Function to create images with captions
def create_captioned_images(image_files, captions, image_output_dir, video_width, video_height, caption_props):
    max_text_width = int(video_width * 0.95)

    for idx, (image_path, caption_text) in enumerate(zip(image_files, captions)):
        print(f"Applying caption '{caption_text}' to the image {os.path.basename(image_path)}")

        wrapped_caption_text = textwrap.fill(caption_text, width=50)
        filename = os.path.basename(image_path)
        new_filename = f'image{idx:04d}{os.path.splitext(filename)[1]}'
        new_filepath_with_caption = os.path.join(image_output_dir, new_filename)

        video_filter = (
            ffmpeg
            .input(image_path)
            .filter('scale', width=video_width, height=video_height, force_original_aspect_ratio='decrease')
            .filter('pad', width=video_width, height=video_height, x='(ow-iw)/2', y='(oh-ih)/2', color='black')
        )
        
        video_filter = video_filter.filter(
            'drawtext',
            text=wrapped_caption_text,
            fontcolor=caption_props.get('font_color', 'white'),
            fontsize=caption_props.get('font_size', 36),
            x='(w-tw)/2',
            y=caption_props.get('caption_offset_y', '0.10*h'),
            box=1,
            boxcolor=caption_props.get('box_color', 'black@0.5'),
            boxborderw=caption_props.get('box_borderw', 5),
            line_spacing=caption_props.get('line_spacing', 10),
            fix_bounds=True
        )

        video_filter.output(new_filepath_with_caption).run(overwrite_output=True)


# Function to generate a video from images and an audio file
def generate_video_from_images(input_folder, audio_file, output_video, display_duration_per_image):
    # Get the sorted list of image files
    image_files = get_image_files(input_folder)
    
    # Create a temporary file list
    list_file = 'file_list.txt'
    with open(list_file, 'w') as f:
        for image_file in image_files:
            f.write(f"file '{image_file}'\n")
            f.write(f"duration {display_duration_per_image}\n")
    
    # Add the last image file without duration (required by FFmpeg)
    if image_files:
        with open(list_file, 'a') as f:
            f.write(f"file '{image_files[-1]}'\n")

    # Prepare FFmpeg command
    ffmpeg_cmd = [
        'ffmpeg',
        '-f', 'concat',
        '-safe', '0',
        '-i', list_file,
        '-vsync', 'vfr',
        '-pix_fmt', 'yuv420p'
    ]
    
    # Add audio file if provided
    if audio_file:
        ffmpeg_cmd.extend(['-i', audio_file, '-c:a', 'copy'])
    
    # Add output video file
    ffmpeg_cmd.append(output_video)
    
    # Run FFmpeg command
    try:
        subprocess.run(ffmpeg_cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"An FFmpeg error occurred while creating the video: {e}")
    finally:
        # Clean up the temporary file list
        if os.path.exists(list_file):
            os.remove(list_file)

# Function to trim audio to a target length
def trim_audio_to_exact_length(filename, target_length):
    file_extension = os.path.splitext(filename)[1].lower()
    
    if file_extension == ".mp3":
        audio = MP3(filename)
        audio_length = int(audio.info.length)
    elif file_extension == ".mp4":
        result = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                 "format=duration", "-of",
                                 "default=noprint_wrappers=1:nokey=1", filename],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        audio_length = float(result.stdout)
    else:
        print(f"Unsupported file format: {file_extension}")
        return False

    if audio_length == target_length:
        return True
    elif audio_length > target_length:
        trimmed_filename = f"{os.path.splitext(filename)[0]}_trimmed{file_extension}"
        subprocess.run([
            "ffmpeg", "-i", filename,
            "-ss", "0", "-to", str(target_length),
            "-c", "copy", trimmed_filename,
            "-y"
        ])
        os.remove(filename)
        os.rename(trimmed_filename, filename)
        return True
    else:
        return False


# Function to clean up temporary files
def cleanup(image_output_dir, audio_file):
    try:
        if os.path.exists(image_output_dir):
            shutil.rmtree(image_output_dir)
        if os.path.exists(audio_file):
            os.remove(audio_file)
    except OSError as e:
        print(f"An error occurred while cleaning up files: {e.strerror}")

# Function to add text to a video before it ends
def add_text_to_video(input_path, output_path, time_until_end=3, text_to_add="this is text 3 seconds before end"):
    duration = get_length(input_path)
    start_time = duration - time_until_end
    
    # Using ffmpeg to add the text with drawtext
    subprocess.run([
        'ffmpeg', 
        '-i', input_path, 
        '-vf', f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:text='{text_to_add}':fontcolor=white:fontsize=24:box=1:boxcolor=black@0.5:boxborderw=5:x=(w-text_w)/2:y=(h-text_h)/2:enable='gte(t,{start_time})'", 
        '-codec:a', 'copy', 
        output_path,
        '-y'  # Overwrite output file without asking
    ])