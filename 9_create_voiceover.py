import os
import json
import argparse
import shutil
from datetime import datetime
from utilities.ffmpeg_utils import get_length, add_text_to_video
from utilities.google_tts_utils import generate_tts_audio, add_silence_to_audio, adjust_audio_speed, mix_audio_on_video

# Configurations
storylines_folder = 'storylines'
videos_folder = 'created_videos'
final_videos_folder = 'final_voiceover_video'
temp_tts_creation = 'temp_tts_creation'  # Folder to store all temporary files
temp_ffmpeg_folder = os.path.join(temp_tts_creation, 'temp_ffmpeg')
tts_audio_folder = os.path.join(temp_tts_creation, 'tts_audio_files')

# Volume settings (in decibels)
TTS_VOLUME_DB = 7  # Range: -10 dB to 10 dB; Set higher to make TTS louder. 0 dB means no change.
BACKGROUND_VOLUME_DB = -10  # Range: -20 dB to 10 dB; Set lower to make background quieter. -20 dB means the background is much quieter.

# Speed of the speech (normal speed is 1.0)
SPEED_OF_SPEECH = 1.4  # Recommended range: 0.5 to 2.0; lower for slower, higher for faster.

def ensure_directory_exists(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)

def get_latest_json_file(directory):
    latest_file, latest_time = None, None
    formats = ["%Y-%m-%d_%H-%M", "%Y%m%d_%H%M%S"]
    for filename in os.listdir(directory):
        if filename.endswith("_summaries.json"):
            for fmt in formats:
                try:
                    file_time = datetime.strptime(filename[:16], fmt)
                    if not latest_time or file_time > latest_time:
                        latest_time, latest_file = file_time, os.path.join(directory, filename)
                    break
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

def create_temp_ffmpeg_folder():
    ensure_directory_exists(temp_ffmpeg_folder)
    return temp_ffmpeg_folder

def cleanup_temp_ffmpeg_folder():
    if os.path.exists(temp_ffmpeg_folder):
        shutil.rmtree(temp_ffmpeg_folder)


def process_voiceover_for_storyline(json_file, final_folder):
    temp_folder = create_temp_ffmpeg_folder()
    try:
        summary_data = read_json(json_file)
        if summary_data is None:
            return False

        video_keys = [key for key in summary_data.keys() if key.startswith("created_video_location_")]
        if not video_keys:
            print(f"[ERROR] No created video locations found in {json_file}")
            return False

        for video_key in video_keys:
            video_path = summary_data.get(video_key)
            if not video_path or not os.path.exists(video_path):
                print(f"[ERROR] Video file {video_path} does not exist.")
                continue

            base_video_name = os.path.basename(video_path)
            base_name = os.path.splitext(base_video_name)[0]
            model_name_suffix = video_key.replace("created_video_location_", "")
            
            story_chapters = summary_data.get("story_chapters", [])
            if not story_chapters:
                print(f"[ERROR] No story chapters found in {json_file}")
                continue

            tts_audio_files = []
            for index, chapter in enumerate(story_chapters):
                padded_index = f"{index + 1:03}"
                summary_text = chapter['chapter_summary']
                tts_audio_file = os.path.join(tts_audio_folder, f"tts_{model_name_suffix}_{padded_index}.mp3")

                # Generate TTS audio if it doesn't already exist
                if not os.path.exists(tts_audio_file):
                    generate_tts_audio(summary_text, output_file=tts_audio_file)

                # Adjust speed of TTS audio if necessary
                adjusted_speed_audio_file = os.path.join(tts_audio_folder, f"tts_{model_name_suffix}_{padded_index}_adjusted.mp3")
                adjust_audio_speed(tts_audio_file, SPEED_OF_SPEECH, output_file=adjusted_speed_audio_file)
                
                # Ensure TTS audio is properly padded
                segment_duration = get_length(video_path) / len(story_chapters)
                final_tts_audio_file = os.path.join(tts_audio_folder, f"tts_{model_name_suffix}_{padded_index}_final.mp3")
                add_silence_to_audio(adjusted_speed_audio_file, segment_duration, output_file=final_tts_audio_file)
                
                tts_audio_files.append(final_tts_audio_file)

            concatenated_audio_path = os.path.join(temp_folder, f"{base_name}_concatenated_tts_audio.mp3")
            with open(concatenated_audio_path, 'wb') as outfile:
                for audio_file in tts_audio_files:
                    with open(audio_file, 'rb') as infile:
                        outfile.write(infile.read())

            intermediate_video_file = os.path.join(temp_folder, f"{base_name}_voiceover_intermediate.mp4")
            mix_audio_on_video(video_path, concatenated_audio_path, intermediate_video_file, tts_volume=TTS_VOLUME_DB, background_volume=BACKGROUND_VOLUME_DB)
            
            output_video_file = os.path.join(final_folder, f"{base_name}_voiceover.mp4")
            #add_text_to_video(intermediate_video_file, output_video_file, time_until_end=3, text_to_add="Full story in description!")
            add_text_to_video(intermediate_video_file, output_video_file, time_until_end=3, text_to_add="")

            summary_data[f"voiceover_created_video_location_{model_name_suffix}"] = output_video_file

        write_json(summary_data, json_file)
        return True
    except Exception as e:
        print(f"[ERROR] An error occurred while processing voiceover: {e}")
        return False
    finally:
        cleanup_temp_ffmpeg_folder()

def main():
    parser = argparse.ArgumentParser(description="Create voiceover videos from storyline summaries.")
    args = parser.parse_args()

    ensure_directory_exists(final_videos_folder)
    ensure_directory_exists(tts_audio_folder)

    latest_json_file = get_latest_json_file(storylines_folder)
    if not latest_json_file:
        print("[ERROR] No summary JSON file found.")
        return

    print(f"[INFO] Processing {latest_json_file}")
    success = process_voiceover_for_storyline(latest_json_file, final_videos_folder)

    if success:
        print("[INFO] Voiceover processing completed successfully.")
    else:
        print("[ERROR] Voiceover processing failed.")

if __name__ == "__main__":
    main()