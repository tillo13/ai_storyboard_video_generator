import os
import time
import json
from collections import defaultdict
import shutil
import sys

# Add the parent directory to the sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Get the current directory where the script is located
current_dir = os.path.dirname(os.path.abspath(__file__))

# Define the paths relative to the current directory
mosaics_dir = os.path.abspath(os.path.join(current_dir, "..", "mosaics"))
please_review_dir = os.path.join(mosaics_dir, "please_review")
archive_dir = os.path.abspath(os.path.join(current_dir, "..", "archive"))

# Create the please_review directory if it does not exist
if not os.path.exists(please_review_dir):
    os.makedirs(please_review_dir)

# Function to get the basename without extension
def get_basename(file_path):
    return os.path.splitext(os.path.basename(file_path))[0]

# Function to extract the timestamp part
def extract_timestamp(file_name):
    parts = file_name.split('_story_summaries')
    if len(parts) > 1:
        return parts[0]  # This removes everything after '_story_summaries'
    return ''

# Function to move files from the please_review folder back to mosaics if they are unique
def review_and_move_files():
    # Initialize dictionary to count the occurrences of each timestamped story summary in the please_review folder
    review_timestamp_counts = defaultdict(int)
    review_file_timestamp_map = defaultdict(list)
    
    # Scan the please_review directory
    for review_file in os.listdir(please_review_dir):
        review_path = os.path.join(please_review_dir, review_file)
        if os.path.isfile(review_path) and review_path.endswith('.png'):
            review_basename = get_basename(review_path)
            timestamp = extract_timestamp(review_basename)
            if timestamp:
                review_timestamp_counts[timestamp] += 1
                review_file_timestamp_map[timestamp].append(review_path)

    # Move unique files back to the mosaics directory
    for timestamp, count in review_timestamp_counts.items():
        if count == 1:
            for file_path in review_file_timestamp_map[timestamp]:
                shutil.move(file_path, mosaics_dir)
                print(f"Moved {file_path} back to {mosaics_dir}")

def main():
    # Run the review and move process
    review_and_move_files()

    # Start measuring the execution time
    start_time = time.time()

    # Initialize counters for matches and fails
    matches = 0
    fails = 0

    # Initialize dictionary to count the occurrences of each timestamped story summary
    timestamp_counts = defaultdict(int)
    file_timestamp_map = defaultdict(list)

    # Scan the entire mosaics directory
    print(f"Scanning mosaics directory: {mosaics_dir}")
    for mosaic_file in os.listdir(mosaics_dir):
        mosaic_path = os.path.join(mosaics_dir, mosaic_file)
        if os.path.isfile(mosaic_path) and mosaic_path.endswith('.png'):
            print(f"Processing file: {mosaic_path}")
            mosaic_basename = get_basename(mosaic_path)
            timestamp = extract_timestamp(mosaic_basename)
            if timestamp:
                timestamp_counts[timestamp] += 1
                file_timestamp_map[timestamp].append(mosaic_path)
            
            found_match = False
            
            # Loop through the archive directory and subfolders to find the matching storyline
            for root, _, files in os.walk(archive_dir):
                for archive_file in files:
                    archive_basename = get_basename(os.path.join(root, archive_file))
                    if mosaic_basename.startswith(archive_basename):
                        json_path = os.path.join(root, archive_file)
                        with open(json_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        
                        movie_title = data.get("movie_title", "N/A")
                        story_summary = data.get("story_summary", "N/A")
                        story_keywords = data.get("story_keywords", "N/A")

                        # Get the voiceover directory and search for the matching voiceover file
                        voiceover_dir = os.path.join(os.path.dirname(root), "final_voiceover_video")
                        voiceover_file = None
                        if os.path.exists(voiceover_dir):
                            for file in os.listdir(voiceover_dir):
                                if file.endswith(".mp4"):  # Assuming that voiceover files are in mp4 format
                                    voiceover_file = os.path.join(voiceover_dir, file)
                                    break

                        print(f"Match found: {mosaic_path} <=> {json_path}")
                        print(f"Movie Title: {movie_title}")
                        print(f"Story Summary: {story_summary}")
                        print(f"Story Keywords: {story_keywords}")
                        print(f"Voiceover File: {voiceover_file}\n")
                        
                        matches += 1
                        found_match = True
                        break  # Stop searching when a match is found
                if found_match:
                    break
            
            # If no match is found
            if not found_match:
                print(f"No match found for: {mosaic_path}")
                fails += 1

    print("\nMoving duplicate timestamp files to please_review directory")
    # Move files with duplicate timestamps to the please_review directory
    for timestamp, count in timestamp_counts.items():
        if count > 1:
            for file_path in file_timestamp_map[timestamp]:
                shutil.move(file_path, please_review_dir)
                print(f"Moved {file_path} to {please_review_dir}")

    # End measuring the execution time
    end_time = time.time()

    # Calculate the total runtime
    total_time = end_time - start_time

    # Print the summary
    print("\n=== Summary ===")
    print(f"Total files processed: {matches + fails}")
    print(f"Matches found: {matches}")
    print(f"Fails: {fails}")
    print(f"Total time taken: {total_time:.2f} seconds")

    # Print the counts for each timestamped story summary in descending order
    print("\n=== Story Summary Counts ===")
    for timestamp, count in sorted(timestamp_counts.items(), key=lambda item: item[1], reverse=True):
        print(f"{timestamp} = {count}")

if __name__ == "__main__":
    main()