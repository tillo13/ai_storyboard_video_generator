import os
import subprocess
from datetime import datetime
import json

# Constants
CREATED_VIDEOS_DIR = "created_videos"
PROCESSED_VIDEOS_DIR = os.path.join(CREATED_VIDEOS_DIR, "processed")
STORYLINES_FOLDER = "storylines"
GLOBAL_PAN_SPEED = 50  # Speed of the pan and zoom effects (10 is fast, 200 is slow)
ZOOM_PATTERN = "1 + 0.2*sin(in/25)"  # Customize the zoom pattern here

# Ensure the processed videos directory exists
os.makedirs(PROCESSED_VIDEOS_DIR, exist_ok=True)

def get_latest_summary_file(directory):
    latest_file = None
    latest_time = None
    formats_to_try = ["%Y-%m-%d_%H-%M", "%Y%m%d_%H%M%S"]

    for filename in os.listdir(directory):
        if filename.endswith("_summaries.json"):
            for fmt in formats_to_try:
                try:
                    file_time = datetime.strptime(filename[:16], fmt)
                    if latest_time is None or file_time > latest_time:
                        latest_time = file_time
                        latest_file = os.path.join(directory, filename)
                except ValueError:
                    continue

    return latest_file

def parse_summary_file(summary_file):
    with open(summary_file, 'r', encoding='utf-8') as file:
        data = json.load(file)
    return data

def process_videos():
    summary_file = get_latest_summary_file(STORYLINES_FOLDER)
    if not summary_file:
        print("No summary file found.")
        return

    summary_data = parse_summary_file(summary_file)
    
    for video_file in os.listdir(CREATED_VIDEOS_DIR):
        video_path = os.path.join(CREATED_VIDEOS_DIR, video_file)
        
        if not video_path.endswith(".mp4"):
            continue
        
        # Get the video length using ffprobe
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', video_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )
        video_duration = float(result.stdout.decode().strip())
        
        # Get the video dimensions using ffprobe
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-of', 'csv=p=0', video_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )
        video_dimensions = result.stdout.decode().strip().split(',')
        video_width = int(video_dimensions[0])
        video_height = int(video_dimensions[1])
        
        # Adding a smooth and varied zoom and pan effect for the entire video
        # Apply GLOBAL_PAN_SPEED to pan and zoom functions
        zoompan_filter = (
            f"zoompan=z='{ZOOM_PATTERN}':"  # Use the global ZOOM_PATTERN
            f"x='trunc(iw/2-(iw/zoom/2)+(sin(in/{GLOBAL_PAN_SPEED})*iw/4))':"  # Horizontal panning
            f"y='trunc(ih/2-(ih/zoom/2)+(cos(in/{GLOBAL_PAN_SPEED})*ih/4))':"  # Vertical panning
            f"d=1:s={video_width}x{video_height}:fps=25"
        )
        
        # Generate the temporary output filename
        temp_output_video_filename = f"{os.path.splitext(video_file)[0]}_temp_processed.mp4"
        temp_output_video_path = os.path.join(PROCESSED_VIDEOS_DIR, temp_output_video_filename)
        
        # Process the video with FFmpeg
        ffmpeg_command = [
            'ffmpeg', '-y', '-i', video_path, '-vf', zoompan_filter, '-preset', 'fast', '-c:a', 'copy', temp_output_video_path
        ]
        subprocess.run(ffmpeg_command, check=True)
        
        # Generate the processed original filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        processed_original_filename = f"{os.path.splitext(video_file)[0]}_{timestamp}.mp4"
        processed_original_path = os.path.join(PROCESSED_VIDEOS_DIR, processed_original_filename)
        
        # Move the original video to the processed directory with timestamp
        os.rename(video_path, processed_original_path)
        
        # Rename the processed video to have the same name as the original video
        os.rename(temp_output_video_path, video_path)
        
        print(f"Processed video saved as {video_path}. Original video moved to {processed_original_path}.")

if __name__ == "__main__":
    process_videos()