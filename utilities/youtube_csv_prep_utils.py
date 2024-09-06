import os
import csv
import json
import sys
import shutil
import re
from collections import defaultdict
from datetime import datetime
import pytz

# Correctly resolve base_dir relative to the script's location
script_dir = os.path.dirname(os.path.abspath(__file__))
base_dir = os.path.join(script_dir, "..")

# Directory paths
mosaics_dir = os.path.join(base_dir, "mosaics")
archive_dir = os.path.join(base_dir, "archive")
output_csv = os.path.join(mosaics_dir, "file_upload_log.csv")
unmatched_mosaics_dir = os.path.join(mosaics_dir, "unmatched_mosaics")
archived_csv_dir = os.path.join(mosaics_dir, "archived_csv")

# Ensure directories exist
os.makedirs(unmatched_mosaics_dir, exist_ok=True)
os.makedirs(archived_csv_dir, exist_ok=True)

# Timezone for Seattle
seattle_tz = pytz.timezone('America/Los_Angeles')


def get_basename(file_path):
    return os.path.splitext(os.path.basename(file_path))[0]


def extract_timestamp(file_name):
    parts = file_name.split('_story_summaries')
    if len(parts) > 1:
        return parts[0]
    return ''


def get_file_creation_date(file_path):
    try:
        creation_time = datetime.fromtimestamp(os.path.getctime(file_path))
        creation_time_seattle = creation_time.astimezone(seattle_tz)
        creation_time_str = creation_time_seattle.strftime('%Y-%m-%d %H:%M:%S')
        return creation_time_str
    except Exception as e:
        print(f"Error getting creation date for {file_path}: {e}")
        return ''


def keep_description_under_5k(description):
    max_length = 4900
    if len(description) > max_length:
        return description[:max_length] + "..."
    return description

def sanitize_text(text):
    # Strip leading/trailing whitespaces; replace multiple spaces/newlines with a single space
    sanitized_text = re.sub(r'\s+', ' ', text).strip()

    # Properly escape quotes for CSV
    sanitized_text = sanitized_text.replace('"', '""')

    # Add formatting for chapters
    sanitized_text = re.sub(r'\bChapter\s*(\d+)\b', r'==== Chapter \1 ====', sanitized_text)
    
    return sanitized_text


def extract_json_metadata(mosaic_basename, json_file_path):
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading {json_file_path}: {e}")
        return None

    video_paths = {key: value for key, value in data.items() if key.startswith("voiceover_created_video_location_")}
    description = data.get("story_summary", "N/A") + " " + data.get("chapters_combined", "")
    sanitized_description = sanitize_text(keep_description_under_5k(description))
    sanitized_keywords = sanitize_text(data.get("story_keywords", "N/A"))
    return {
        "title": data.get("movie_title", "N/A"),
        "description": sanitized_description,
        "keywords": sanitized_keywords,
        "local_video_paths": video_paths
    }


def write_csv_data(csv_filepath, data, columns):
    try:
        with open(csv_filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=columns, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            for row in data:
                writer.writerow(row)
        print(f"CSV successfully written to {csv_filepath}")
    except IOError as e:
        print(f"Error writing CSV: {e}")


def archive_existing_csv(output_csv, archived_csv_dir):
    if os.path.exists(output_csv):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archived_csv_path = os.path.join(archived_csv_dir, f"file_upload_log_{timestamp}.csv")
        try:
            print(f"Moving file (file timestamp: {timestamp}) {output_csv} to archived_csv folder and naming it {archived_csv_path}")
            shutil.move(output_csv, archived_csv_path)
            print(f"Archived existing CSV to: {archived_csv_path}")

            if not os.path.exists(archived_csv_path):
                print(f"Error: Archived CSV file is not found at: {archived_csv_path}")
                sys.exit(1)
        except Exception as e:
            print(f"Error archiving CSV file: {output_csv}, {e}")
            sys.exit(1)


def validate_and_cleanup_files(mosaics_dir, archive_dir, unmatched_mosaics_dir):
    for mosaic_file in os.listdir(mosaics_dir):
        mosaic_path = os.path.join(mosaics_dir, mosaic_file)
        if os.path.isfile(mosaic_path) and mosaic_path.endswith('.png'):
            mosaic_basename = get_basename(mosaic_path)
            model_name_part = mosaic_basename.split('_story_summaries_')[1]

            print(f"Checking png file to see if it has a valid video link: {mosaic_path}")
            found_match = False
            for timestamped_dir_name in os.listdir(archive_dir):
                timestamped_dir_path = os.path.join(archive_dir, timestamped_dir_name)
                if os.path.isdir(timestamped_dir_path):
                    for root, _, archive_files in os.walk(timestamped_dir_path):
                        for archive_file in archive_files:
                            archive_basename = get_basename(archive_file)
                            if mosaic_basename.startswith(archive_basename):
                                json_path = os.path.join(root, archive_file)
                                print(f"Here is the path I am checking: {json_path}")
                                metadata = extract_json_metadata(mosaic_basename, json_path)
                                if metadata is None:
                                    continue

                                final_voiceover_video_dir = os.path.join(timestamped_dir_path, "final_voiceover_video")
                                if not os.path.exists(final_voiceover_video_dir):
                                    continue

                                video_path_full = None
                                video_files = os.listdir(final_voiceover_video_dir)

                                for video_file in video_files:
                                    if model_name_part in video_file:
                                        video_path_full = os.path.join(final_voiceover_video_dir, video_file)
                                        break

                                if video_path_full and os.path.exists(video_path_full):
                                    print(f"Here is the result if I found the file: yes")
                                    found_match = True
                                    break
                        if found_match:
                            break
                if found_match:
                    break
            if not found_match:
                print(f"Here is the result if I found the file: no")
                print(f"Based on the answer, this will not be added to the csv file.")
                try:
                    shutil.move(mosaic_path, unmatched_mosaics_dir)
                    print(f"Moved unmatched mosaic: {mosaic_path} to {unmatched_mosaics_dir}")
                except Exception as e:
                    print(f"Error moving mosaic file: {mosaic_path}, {e}")


def process_new_files(file_timestamp_map, archive_dir):
    csv_data = {}

    for timestamp, files in file_timestamp_map.items():
        if len(files) == 1:
            mosaic_path = files[0]
            mosaic_basename = get_basename(mosaic_path)
            model_name_part = mosaic_basename.split('_story_summaries_')[1]

            found_match = False
            for timestamped_dir_name in os.listdir(archive_dir):
                timestamped_dir_path = os.path.join(archive_dir, timestamped_dir_name)
                if os.path.isdir(timestamped_dir_path):
                    for root, _, archive_files in os.walk(timestamped_dir_path):
                        for archive_file in archive_files:
                            archive_basename = get_basename(archive_file)
                            if mosaic_basename.startswith(archive_basename):
                                json_path = os.path.join(root, archive_file)
                                metadata = extract_json_metadata(mosaic_basename, json_path)
                                if metadata is None:
                                    continue

                                file_creation_date = get_file_creation_date(mosaic_path)

                                final_voiceover_video_dir = os.path.join(timestamped_dir_path, "final_voiceover_video")
                                if not os.path.exists(final_voiceover_video_dir):
                                    continue

                                video_path_full = None
                                video_files = os.listdir(final_voiceover_video_dir)

                                for video_file in video_files:
                                    if model_name_part in video_file:
                                        video_path_full = os.path.join(final_voiceover_video_dir, video_file)
                                        break

                                if video_path_full and os.path.exists(video_path_full):
                                    csv_data[mosaic_path] = {
                                        "title": metadata["title"],
                                        "file_creation_date": file_creation_date,
                                        "mosaic_filepath": mosaic_path,
                                        "local_video_path": video_path_full,
                                        "description": metadata["description"],
                                        "keywords": metadata["keywords"],
                                        "youtube_publish_date": "",
                                        "youtube_publish_url": ""
                                    }
                                    found_match = True
                                    break
                        if found_match:
                            break
                if found_match:
                    break
            if not found_match:
                shutil.move(mosaic_path, unmatched_mosaics_dir)
                print(f"No matching video found for {mosaic_path}, moved to {unmatched_mosaics_dir}")
    return csv_data


def main():
    archive_existing_csv(output_csv, archived_csv_dir)

    validate_and_cleanup_files(mosaics_dir, archive_dir, unmatched_mosaics_dir)

    timestamp_counts = defaultdict(int)
    file_timestamp_map = defaultdict(list)

    new_files = []
    duplicate_files = []
    removed_files = []

    print(f"Scanning mosaics directory: {mosaics_dir}")
    current_file_paths = set()
    for mosaic_file in os.listdir(mosaics_dir):
        mosaic_path = os.path.join(mosaics_dir, mosaic_file)
        if os.path.isfile(mosaic_path) and mosaic_path.endswith('.png'):
            current_file_paths.add(mosaic_path)

            print(f"Processing file: {mosaic_path}")
            mosaic_basename = get_basename(mosaic_path)
            timestamp = extract_timestamp(mosaic_basename)
            if timestamp:
                timestamp_counts[timestamp] += 1
                file_timestamp_map[timestamp].append(mosaic_path)
                new_files.append(mosaic_path)

    new_csv_data = process_new_files(file_timestamp_map, archive_dir)

    all_csv_data = {mosaic_path: data for mosaic_path, data in new_csv_data.items()}

    def sort_key(item):
        return datetime.strptime(item["file_creation_date"], '%Y-%m-%d %H:%M:%S')

    csv_data_sorted = sorted(all_csv_data.values(), key=sort_key)

    csv_columns = ["title", "file_creation_date", "mosaic_filepath", "local_video_path", "description", "keywords", "youtube_publish_date", "youtube_publish_url"]
    write_csv_data(output_csv, csv_data_sorted, csv_columns)

    print("\n==SUMMARY==")
    print(f"New files added: {len(new_files)}")
    for file in new_files:
        print(file)
    print(f"Duplicate files: {len(duplicate_files)}")
    for file in duplicate_files:
        print(file)
    print(f"Removed files: {len(removed_files)}")
    for file in removed_files:
        print(file)


if __name__ == "__main__":
    main()