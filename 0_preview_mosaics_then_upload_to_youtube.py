import subprocess
import json
import os
import datetime
import sys
import csv
import shutil
import pytz
from datetime import timedelta
import re  # Import the regex module



# Adjust the sys.path to include utilities and youtube for importing
current_dir = os.path.dirname(os.path.abspath(__file__))
utilities_dir = os.path.join(current_dir, "utilities")
youtube_dir = os.path.join(utilities_dir, "youtube")

sys.path.insert(0, utilities_dir)
sys.path.insert(0, youtube_dir)

from utilities.mosaic_validator_utils import main as run_mosaic_validator
from utilities.youtube_csv_prep_utils import main as prepare_csv_for_uploads
from utilities.archive_utils import archive_previous_generations
from utilities.youtube.youtube_scheduler_utils import get_authenticated_service, list_scheduled_videos, SEATTLE_TZ, DAILY_POST_FREQUENCY_SCHEDULE

QUEUE_TO_UPLOAD_FILE = os.path.abspath(os.path.join(current_dir, "mosaics", "file_upload_log.csv"))
COMPLETED_DIR = os.path.join(os.path.dirname(QUEUE_TO_UPLOAD_FILE), "completed")

def update_csv_file(new_row, csv_rows):
    try:
        fieldnames = ["title", "file_creation_date", "mosaic_filepath", "local_video_path", "description", "keywords", "youtube_publish_date", "youtube_publish_url"]
        for row in csv_rows:
            if row['mosaic_filepath'] == new_row['mosaic_filepath']:
                row.update(new_row)
                break
        with open(QUEUE_TO_UPLOAD_FILE, 'w', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(csv_rows)
    except Exception as e:
        print(f"Error updating CSV file: {str(e)}")

def read_csv_queue():
    try:
        with open(QUEUE_TO_UPLOAD_FILE, mode='r', newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            rows = [row for row in reader]
        return rows
    except Exception as e:
        print(f"Error reading CSV file: {str(e)}")
        return []


def upload_to_youtube(file_details, next_publish_time):
    try:
        absolute_video_path = os.path.abspath(file_details["local_video_path"])
        print(f"Trying to upload video file: {absolute_video_path}")

        # Validate that the video file exists before attempting upload
        if not os.path.isfile(absolute_video_path):
            print(f"Error: Video file '{absolute_video_path}' does not exist. Skipping upload.")
            return None

        cmd = [
            "python", os.path.join(current_dir, "utilities", "youtube", "youtube_scheduler_utils.py"),
            f'--file={absolute_video_path}',
            f'--title={file_details["title"]}',
            f'--description={file_details["description"]}',
            f'--keywords={file_details["keywords"]}',
            '--category=24',
            '--privacyStatus=private',
            f'--publishAt={next_publish_time.isoformat()}'
        ]

        # Print the full command to be executed for debugging
        print("Here is how we are sending to youtube_scheduler_utils.py:")
        print(" ".join(cmd))

        result = subprocess.run(cmd, capture_output=True, text=True)
        output = result.stdout + result.stderr
        print("YouTube Scheduler Output:\n", output)  # Print all outputs for debugging

        # Extract JSON from output using regex
        json_string = re.search(r'(\{.*\})', output, re.DOTALL)
        if json_string:
            try:
                cleaned_json_str = json_string.group(1).replace("\\n", "").replace('\\"', '"')
                response = json.loads(cleaned_json_str)
                print("Response parsed successfully.")
                return response
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON: {str(e)}")
                print(f"Invalid JSON:\n{cleaned_json_str}")
                return None
        else:
            print("Failed to find JSON in the YouTube Scheduler output.")
            return None

    except Exception as e:
        print(f"Error uploading to YouTube: {str(e)}")
        return None

def move_to_completed(mosaic_path):
    # Create the completed directory if it doesn't exist
    if not os.path.exists(COMPLETED_DIR):
        os.makedirs(COMPLETED_DIR)
    
    try:
        shutil.move(mosaic_path, COMPLETED_DIR)
        print(f"Moved {mosaic_path} to {COMPLETED_DIR}")
    except Exception as e:
        print(f"Error moving file {mosaic_path} to completed directory: {str(e)}")

def get_next_publish_time(scheduled_videos, daily_post_frequency):
    interval_hours = 24 / daily_post_frequency
    
    if scheduled_videos:
        last_scheduled_time = max([datetime.datetime.fromisoformat(video['scheduled_publish_time']).astimezone(SEATTLE_TZ) for video in scheduled_videos])
    else:
        last_scheduled_time = datetime.datetime.now(tz=SEATTLE_TZ).replace(hour=8, minute=0, second=0, microsecond=0)
    
    next_publish_time = last_scheduled_time + timedelta(hours=interval_hours)
    return next_publish_time


def main():
    # Archive previous generations first
    archive_previous_generations()

    # Step 1: Run the Mosaic Validator Utils (this cleans and prepares the mosaics folder)
    print("Running Mosaic Validator Utils...")
    run_mosaic_validator()

    # Step 2: Prepare the CSV for YouTube uploads
    print("Preparing CSV for YouTube uploads...")
    prepare_csv_for_uploads()

    # Step 3: Read the CSV queue to get the files to upload
    print("Reading CSV queue for uploads...")
    csv_rows = read_csv_queue()

    # Select the top file to upload
    if not csv_rows:
        print("No files to upload.")
        return
    
    file_details = csv_rows[0]  # Always select the first entry

    # Step 4: Check the scheduled posts
    youtube = get_authenticated_service()
    scheduled_videos = list_scheduled_videos(youtube)
    
    if not scheduled_videos:
        scheduled_videos = []

    # Step 5: Determine the next publish time
    next_publish_time = get_next_publish_time(scheduled_videos, DAILY_POST_FREQUENCY_SCHEDULE)
    
    print(f"The next video will be scheduled to post at: {next_publish_time.isoformat()} (Seattle time)")

    response = upload_to_youtube(file_details, next_publish_time)
    if response and isinstance(response, dict) and 'id' in response:
        try:
            url = f"https://www.youtube.com/watch?v={response['id']}"
            publish_at = response['snippet']['publishedAt']
            publish_date = datetime.datetime.fromisoformat(publish_at.replace('Z', '+00:00')).isoformat()

            # Print returned values for later use
            print("#####UPLOAD SUCCESSFUL#####")
            print(f"Returned youtube_publish_date: {publish_date}")
            print(f"Returned youtube_publish_url: {url}")
            print("###########################################")

            # Move the mosaic file to the completed directory
            move_to_completed(file_details["mosaic_filepath"])

            # Update the CSV entry
            file_details["youtube_publish_date"] = publish_date
            file_details["youtube_publish_url"] = url
            
            # Update the CSV file with updated entry
            update_csv_file(file_details, csv_rows)
            print("CSV file updated after processing uploads.")
        except Exception as e:
            print(f"Error processing upload response: {str(e)}")
    else:
        print(f"Failed to upload the video '{file_details['title']}' or parse the response.")

    # Print the final line with scheduling details
    print("\nBased on publishing schedule here is what we know:")
    if scheduled_videos:
        last_scheduled_video = max(scheduled_videos, key=lambda x: x['scheduled_publish_time'])
        print(f"Your last video is scheduled to be published:\nTitle: \"{last_scheduled_video['title']}\", Scheduled Publish Time (Seattle): {last_scheduled_video['scheduled_publish_time']}")
    else:
        print("No previous videos are scheduled.")

    next_upload_time_est = next_publish_time + timedelta(hours=24 / DAILY_POST_FREQUENCY_SCHEDULE)
    print(f"Based on the DAILY_POST_FREQUENCY_SCHEDULE, your next video whether successful or not, based solely on the math, would mean it would post at: {next_upload_time_est.isoformat()} Seattle time.")

if __name__ == "__main__":
    main()