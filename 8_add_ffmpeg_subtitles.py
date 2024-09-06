import os
import subprocess
import json
from datetime import datetime
import cv2
import dlib
import re

# GLOBAL VARIABLES #
FONT_SIZE = 24
FONT_COLOR = "white"
BOX_COLOR = "black@0.5"
BOX_BORDER_WIDTH = 5
SPACE_BETWEEN_LINES = -2
TEXT_ALIGNMENT = "center"
FRAMES_DIR = "frames"
STORYLINES_FOLDER = 'storylines'

# Ensure the frames directory exists and is empty
if os.path.exists(FRAMES_DIR):
    for file in os.listdir(FRAMES_DIR):
        os.remove(os.path.join(FRAMES_DIR, file))
else:
    os.makedirs(FRAMES_DIR, exist_ok=True)

# Load the dlib face detector
detector = dlib.get_frontal_face_detector()

def wrap_text(text, max_width, char_width):
    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        if len(current_line + word) * char_width > max_width:
            lines.append(current_line.strip())
            current_line = word + " "
        else:
            current_line += word + " "
    lines.append(current_line.strip())
    return lines

def find_faces(frame_path):
    image = cv2.imread(frame_path)
    if image is None:
        print(f"Error: Could not open image {frame_path}")
        return []
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    faces = detector(gray)
    return faces

def extract_frame_at_timestamp(video_path, timestamp, output_path):
    command = [
        'ffmpeg',
        '-y',
        '-ss', str(timestamp),
        '-i', video_path,
        '-vframes', '1',
        '-update', '1',
        '-frames:v', '1',
        output_path
    ]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        print(f"Error extracting frame at timestamp {timestamp}: {result.stderr}")
        exit(1)

def read_json(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    except Exception as e:
        print(f"[ERROR] Failed to read JSON file {file_path}: {e}")
        return None

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

def get_model_name_from_filename(filename):
    parts = filename.split('_')
    if parts:
        return parts[0]
    return None

def find_chapter_info(data, model_name):
    chapters_info = []
    for chapter in data["story_chapters"]:
        for key in chapter.keys():
            if key.startswith("chapter_image_location_") and model_name in chapter[key]:
                chapters_info.append({
                    "chapter_summary": chapter["chapter_summary"],
                    "chapter_summary_start_time": chapter["chapter_summary_start_time"],
                    "chapter_summary_end_time": chapter["chapter_summary_end_time"]
                })
                break
    return chapters_info

def sanitize_text(text):
    return re.sub(r'[^\w\s\.\,\:\;\!\?\-\(\)\[\]\&]', '`', text)

def create_text_filters(input_video_path, video_width, video_height, chapter_timings, margin_x, margin_y, wrap_width, char_width):
    filters = []
    for i, chapter in enumerate(chapter_timings):
        start_time = chapter['chapter_summary_start_time']
        end_time = chapter['chapter_summary_end_time']
        summary_text = chapter['chapter_summary']

        frame_path = os.path.join(FRAMES_DIR, f'frame_{i}.png')
        extract_frame_at_timestamp(input_video_path, start_time, frame_path)

        faces = find_faces(frame_path)

        if faces:
            total_faces = len(faces)
            avg_y = sum((face.top() + face.bottom()) // 2 for face in faces) // total_faces

            if avg_y < video_height // 2:
                drawtext_y = f"(h - text_h - {margin_y})"
                print(f"Segment {i}: Face(s) detected at top, placing text at bottom.")
            else:
                drawtext_y = f"{margin_y}"
                print(f"Segment {i}: Face(s) detected at bottom, placing text at top.")
        else:
            drawtext_y = f"(h - text_h - {margin_y})"
            print(f"Segment {i}: No faces detected, placing text at bottom.")

        # Wrap the text properly and replace new line characters
        wrapped_lines = wrap_text(summary_text, wrap_width, char_width)
        wrapped_text = '\n'.join(wrapped_lines)

        # Sanitize the text
        sanitized_text = sanitize_text(wrapped_text)

        drawtext_x = f"(w - text_w) / 2" if TEXT_ALIGNMENT == "center" else str(margin_x)

        filter_str = (f"drawtext=text='{sanitized_text}':x={drawtext_x}:y={drawtext_y}:"
                      f"fontsize={FONT_SIZE}:fontcolor={FONT_COLOR}:box=1:boxcolor={BOX_COLOR}:"
                      f"boxborderw={BOX_BORDER_WIDTH}:line_spacing={SPACE_BETWEEN_LINES}:"
                      f"enable='between(t,{start_time},{end_time})'")

        filters.append(filter_str)

        print(f"Filter {i}: {filter_str}")
    return filters

videos_dir = "created_videos"
completed_videos_dir = os.path.join(videos_dir, "completed_videos")
os.makedirs(completed_videos_dir, exist_ok=True)

json_file_path = get_latest_summary_file(STORYLINES_FOLDER)
if not json_file_path:
    print("[ERROR] No summary JSON file found.")
    exit()

data = read_json(json_file_path)
if data is None:
    print("[ERROR] Failed to read the summary JSON file.")
    exit()

to_process_videos = []
for video_filename in os.listdir(videos_dir):
    if not video_filename.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):  # Assuming these file formats.
        continue
    input_video_path = os.path.join(videos_dir, video_filename)
    if not os.path.isfile(input_video_path):
        continue
    to_process_videos.append((video_filename, input_video_path))

for video_filename, input_video_path in to_process_videos:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_video_filename = f"{timestamp}_{video_filename}"
    output_video_path = os.path.join(completed_videos_dir, output_video_filename)

    result = subprocess.run(
        ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-of', 'csv=p=0', input_video_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )
    video_dimensions = result.stdout.decode().strip().split(',')
    video_width = int(video_dimensions[0])
    video_height = int(video_dimensions[1])

    wrap_width = int(video_width * (1.0 - 0.2))

    margin_x = int(video_width * 0.1)
    margin_y = int(video_height * 0.05)

    char_width = 12

    model_name = get_model_name_from_filename(video_filename)
    if not model_name:
        print(f"[ERROR] Could not extract model name from {video_filename}")
        continue

    chapters_info = find_chapter_info(data, model_name)
    if not chapters_info:
        print(f"[ERROR] No chapter information found for model {model_name} in JSON data.")
        continue

    filters = create_text_filters(input_video_path, video_width, video_height, chapters_info, margin_x, margin_y, wrap_width, char_width)

    full_filter = ','.join(filters)

    print(f"Full Filter String: {full_filter}")

    ffmpeg_command = [
        'ffmpeg', '-y', '-i', input_video_path, '-filter_complex', full_filter, '-preset', 'fast', '-c:a', 'copy', output_video_path
    ]
    subprocess.run(ffmpeg_command, check=True)

    print(f"Output video saved as {output_video_path}")

    # Move the original video to completed_videos with timestamp
    completed_original_path = os.path.join(completed_videos_dir, f"original_{timestamp}_{video_filename}")
    os.rename(input_video_path, completed_original_path)

    # Move the new video to replace the original in created_videos
    new_video_replacement_path = os.path.join(videos_dir, video_filename)
    os.rename(output_video_path, new_video_replacement_path)

    print(f"Original video moved to {completed_original_path}")
    print(f"New video moved to {new_video_replacement_path}")

print("All videos processed.")