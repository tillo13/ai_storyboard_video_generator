import os
import subprocess
from datetime import datetime
import shlex

# GLOBAL VARIABLES #
INPUT_VIDEO_NAME = "digiplay_Photon_v1_A3svABDnmio_Chris_Stapleton___Starting_Over__Official_Music_Video__55.0s_091426.mp4"
OUTPUT_VIDEO_FORMAT = "mp4"
FONT_PATH = "/path/to/your/font.ttf"
OVERLAY_TEXT = "This is a long sentence intended to demonstrate text wrapping functionality at the top of the video."
FONT_SIZE = 24
FONT_COLOR = "white"
BOX_COLOR = "black@0.5"  # Color with 50% opacity
BOX_BORDER_WIDTH = 5
LINE_SPACING = 5  # Extra line spacing in pixels
LEFT_RIGHT_MARGIN_PERCENTAGE = 0.1  # 10% margin for left and right
TOP_BOTTOM_MARGIN_PERCENTAGE = 0.05  # 5% margin for top and bottom
BOX_POSITION = "top"  # Options: "top", "bottom"
SPACE_BETWEEN_LINES = -2  # Negative value to reduce the space between lines
TEXT_ALIGNMENT = "center"  # Options: "left", "center"

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

def pad_text(lines, max_len):
    padded_lines = []
    for line in lines:
        spaces_needed = (max_len - len(line))
        padded_line = ' ' * (spaces_needed // 2) + line + ' ' * (spaces_needed // 2)
        if spaces_needed % 2 != 0:
            padded_line += ' '
        padded_lines.append(padded_line)
    return padded_lines

# Define the input video path
current_dir = os.getcwd()
input_video_path = os.path.join(current_dir, "created_videos", INPUT_VIDEO_NAME)

# Generate the output file name with current date and time
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
output_video_filename = f"{timestamp}_videotest.{OUTPUT_VIDEO_FORMAT}"
output_video_path = os.path.join(current_dir, "created_videos", output_video_filename)

# Get the video dimensions using ffprobe
result = subprocess.run(
    ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-of', 'csv=p=0', input_video_path],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT
)
video_dimensions = result.stdout.decode().strip().split(',')
video_width = int(video_dimensions[0])
video_height = int(video_dimensions[1])

# Define the text wrapping width (width within margins)
wrap_width = int(video_width * (1.0 - 2 * LEFT_RIGHT_MARGIN_PERCENTAGE))

# Margins
margin_x = int(video_width * LEFT_RIGHT_MARGIN_PERCENTAGE)
margin_y = int(video_height * TOP_BOTTOM_MARGIN_PERCENTAGE)

# Assuming an average character width of 12 pixels for fontsize 24
char_width = 12
wrapped_lines = wrap_text(OVERLAY_TEXT, wrap_width, char_width)

# Apply padding to each line for center alignment if needed
if TEXT_ALIGNMENT == "center":
    max_line_len = max(len(line) for line in wrapped_lines)
    wrapped_lines = pad_text(wrapped_lines, max_line_len)
wrapped_text = '\n'.join(wrapped_lines)

# Compute drawtext X and Y coordinates based on TEXT_ALIGNMENT
if TEXT_ALIGNMENT == "left":
    drawtext_x = f"{margin_x}"  # Ensure left margin
    drawtext_y = f"h - th - {margin_y}" if BOX_POSITION == "bottom" else f"{margin_y}"
elif TEXT_ALIGNMENT == "center":
    drawtext_x = f"(w - tw) / 2"
    drawtext_y = f"h - th - {margin_y}" if BOX_POSITION == "bottom" else f"{margin_y}"

# Safely quote wrapped_text for FFmpeg command
wrapped_text_quoted = shlex.quote(wrapped_text)

# Construct FFmpeg command
ffmpeg_command = [
    'ffmpeg',
    '-i', input_video_path,
    '-vf', f"drawtext=fontfile='{FONT_PATH}':text={wrapped_text_quoted}:x={drawtext_x}:y={drawtext_y}:fontsize={FONT_SIZE}:fontcolor={FONT_COLOR}:box=1:boxcolor={BOX_COLOR}:boxborderw={BOX_BORDER_WIDTH}:line_spacing={SPACE_BETWEEN_LINES}",
    '-codec:a', 'copy',
    output_video_path
]

# Execute the FFmpeg command
subprocess.run(ffmpeg_command, check=True)

print(f"Output video saved as {output_video_path}")