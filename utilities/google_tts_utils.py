import os
import argparse
from gtts import gTTS
import subprocess

# VOICES WE CAN USE #
# Below are the different English language options and how to reference them in gTTS:
# 'en'    : 'English (default)'
# 'en-au' : 'English (Australia)'   - Use tld='com.au'
# 'en-uk' : 'English (United Kingdom)' - Use tld='co.uk'
# 'en-us' : 'English (United States)' - Use tld='com'
# 'en-in' : 'English (India)'       - Use tld='co.in'
# 'en-za' : 'English (South Africa)' - Use tld='co.za'

# GLOBAL VARIABLES
DEFAULT_LANGUAGE = 'en'   # Default language code for English
DEFAULT_TLD = 'com.au'  # Default top-level domain for Australian English
DEFAULT_VIDEO_FILE = 'test.mp4'  # Default path to the video file
DEFAULT_OUTPUT_VIDEO_FILE = 'output_video_with_tts.mp4'  # Default path for the output video file
DEFAULT_SAMPLE_TEXT = """Hello, this is a test voice generated using Google Text-to-Speech.
                         This tool can convert text to speech quite efficiently.
                         Let's see how it sounds when overlaid on a video."""

# Function to generate TTS audio from text
def generate_tts_audio(text, output_file='temp_tts_audio.mp3', lang=DEFAULT_LANGUAGE, tld=DEFAULT_TLD):
    tts = gTTS(text, lang=lang, tld=tld)
    tts.save(output_file)
    print(f"Audio has been saved as {output_file}")
    return output_file

# Function to adjust the speed of the TTS audio
def adjust_audio_speed(input_audio_file, rate, output_file='temp_adjusted_tts_audio.mp3'):
    subprocess.run([
        'ffmpeg', '-y', '-i', input_audio_file, '-filter:a', f"atempo={rate}", output_file
    ], check=True)
    print(f"Adjusted audio speed and saved as {output_file}")
    return output_file

def add_silence_to_audio(input_audio_file, target_duration, output_file='temp_final_tts_audio.mp3'):
    # Get the duration of the input audio
    result = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', input_audio_file],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )
    audio_duration = float(result.stdout)
    print(f"Input audio duration: {audio_duration} seconds")

    # Calculate the amount of silence needed
    silence_duration = max(0, target_duration - audio_duration)
    
    # Adjust the audio by adding silence
    subprocess.run([
        'ffmpeg', '-y', '-i', input_audio_file,
        '-filter_complex', f'apad=pad_dur={silence_duration}',
        '-t', str(target_duration),
        output_file
    ], check=True)
    print(f"Adjusted audio with silence and saved as {output_file}")
    return output_file

def mix_audio_on_video(video_file, tts_audio_file, output_video_file, tts_volume=5, background_volume=-15):
    try:
        # Ensure input volumes are in decibel values
        tts_volume_str = f'volume={tts_volume}dB'
        background_volume_str = f'volume={background_volume}dB'

        # FFmpeg command to mix original and TTS audio
        subprocess.run([
            'ffmpeg', '-y', '-i', video_file, '-i', tts_audio_file,
            '-filter_complex', f'[1:a]{tts_volume_str}[a1];[0:a]{background_volume_str}[a0];[a0][a1]amerge=inputs=2,pan=stereo|c0<c0+c2|c1<c1+c3[a]', 
            '-map', '0:v', '-map', '[a]',
            '-c:v', 'copy',
            '-c:a', 'aac', '-b:a', '192k',
            '-shortest', output_video_file
        ], check=True)
        
        print(f"[INFO] Output video with overlaid audio has been saved as {output_video_file}")
        
        # Cleanup temporary files
        os.remove(tts_audio_file)
        print("Temporary files have been removed.")
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Failed to mix audio on video: {e}")
        raise

def pad_audio_to_video_duration(video_file, audio_file):
    padded_audio_file = 'temp_padded_tts_audio.mp3'

    # Get the duration of the video
    result = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', video_file],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )
    video_duration = float(result.stdout)
    print(f"Video duration: {video_duration} seconds")
    
    # Pad the TTS audio to match the video duration
    subprocess.run([
        'ffmpeg', '-y', '-i', audio_file, 
        '-af', f'apad=pad_dur={video_duration}', 
        '-t', str(video_duration), 
        padded_audio_file
    ], check=True)
    print(f"Padded audio has been saved as {padded_audio_file}")
    return padded_audio_file

def main():
    # Setup argument parser
    parser = argparse.ArgumentParser(description="Overlay TTS audio on a video file.")
    parser.add_argument('-video_file', type=str, default=DEFAULT_VIDEO_FILE, help="Path to the video file")
    parser.add_argument('-output_video_file', type=str, default=DEFAULT_OUTPUT_VIDEO_FILE, help="Path for the output video file")
    parser.add_argument('-text_to_speak', type=str, default=DEFAULT_SAMPLE_TEXT, help="Text to convert to speech")
    parser.add_argument('-language', type=str, default=DEFAULT_LANGUAGE, help="Language for TTS (e.g., 'en' for English)")
    parser.add_argument('-tld', type=str, default=DEFAULT_TLD, help="Top-level domain to specify accent (e.g., 'com.au' for Australian English)")
    args = parser.parse_args()

    # Generate TTS audio file
    tts_audio_file = generate_tts_audio(args.text_to_speak, output_file='temp_tts_audio.mp3', lang=args.language, tld=args.tld)
    
    # Ensure the video file exists
    if not os.path.exists(args.video_file):
        print(f"Sample video file {args.video_file} does not exist. Please provide a valid video file.")
        return
    
    # Overlay TTS audio on the video
    mix_audio_on_video(args.video_file, tts_audio_file, args.output_video_file)

if __name__ == "__main__":
    main()