import os
import json
import sys
import logging
from datetime import datetime
from time import time

import torch
from PIL import Image
from diffusers import DDIMScheduler, StableDiffusionPipeline, AutoencoderKL

import GLOBAL_VARIABLES as gv

# Make sure the 'utilities' directory is in your Python path
utilities_path = os.path.join(os.path.dirname(__file__), 'utilities')
if utilities_path not in sys.path:
    sys.path.append(utilities_path)

import utilities.stablediffusion_utils as sdu
import utilities.archive_utils as au  # Importing the archive utility module
import utilities.main_character_generator_utils as mcg  # Importing the main character generator module

logging.basicConfig(level=logging.DEBUG)

# Function to create directories
def create_directories(path):
    if not os.path.exists(path):
        os.makedirs(path)

# Check if USER_PROVIDED_EXACT_CHARACTER is populated
if getattr(gv, 'USER_PROVIDED_EXACT_CHARACTER', ''):
    # Invoke 4b_unique_character.py instead
    logging.info("USER_PROVIDED_EXACT_CHARACTER is populated. Redirecting to 4b_unique_character.py.")
    import subprocess
    result = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "4b_unique_character.py")], text=True)
    print(result.stdout)
    if result.returncode != 0:
        logging.error(f"Error while invoking 4b_unique_character.py: {result.stderr}")
    exit(0)

# Directory paths
GENERATED_IMAGES_PATH = "generated_images"
ENHANCED_IMAGES_PATH = "enhanced_images"
COMPARISONS_PATH = "comparisons"
ARCHIVE_FOLDER_NAME = "archive"
FOLDERS_TO_ARCHIVE = [COMPARISONS_PATH, GENERATED_IMAGES_PATH, ENHANCED_IMAGES_PATH]

# Ensure the output directories exist
create_directories(GENERATED_IMAGES_PATH)
create_directories(ENHANCED_IMAGES_PATH)
create_directories(COMPARISONS_PATH)

# Original create_images.py logic below
# ...

# Initialize variables
TOP_MODELS = gv.TOP_MODELS
DISABLE_SAFETY_CHECKER = gv.DISABLE_SAFETY_CHECKER
ADD_COMPARISONS_TO_ENHANCED_VS_GENERATED = gv.ADD_COMPARISONS_TO_ENHANCED_VS_GENERATED

# Constants
MIN_FREE_SPACE_BYTES = 15 * 1024 * 1024 * 1024  # 15 GB

def check_and_clear_cache_if_needed(min_free_space_bytes):
    """
    Check disk space and clear cache if it's below the specified threshold.
    """
    logging.info(f"Checking and clearing cache if free disk space is lower than {au.bytes_to_gb(min_free_space_bytes)} GB.")
    free_space_before = au.get_free_disk_space()
    logging.info(f"Free disk space before clearing: {au.bytes_to_gb(free_space_before)} GB.")
    au.clear_cache_if_disk_space_low(min_free_space_bytes)
    free_space_after = au.get_free_disk_space()
    logging.info(f"Free disk space after clearing: {au.bytes_to_gb(free_space_after)} GB.")
    freed_space = free_space_after - free_space_before
    logging.info(f"Total space freed up: {au.bytes_to_gb(freed_space)} GB.")

# Initial disk space check and cache clearing
check_and_clear_cache_if_needed(MIN_FREE_SPACE_BYTES)

storyline_files = [f for f in os.listdir(sdu.STORYLINES_PATH) if f.endswith('_summaries.json')]
if not storyline_files:
    logging.error("No storyline files are found in storylines")
    exit(1)

latest_file = max(storyline_files, key=lambda f: os.path.getctime(os.path.join(sdu.STORYLINES_PATH, f)))
storyline_path = os.path.join(sdu.STORYLINES_PATH, latest_file)

with open(storyline_path, 'r') as f:
    storyline_data = json.load(f)

main_character_description = getattr(gv, 'USER_PROVIDED_MAIN_CHARACTER_DESCRIPTION', '') or storyline_data.get('main_character_description', 'this is a default character description, doh.')
main_character_gender = getattr(gv, 'USER_PROVIDED_GENDER', '') or storyline_data.get('main_character_gender', 'Unknown')
main_character_age = storyline_data.get('main_character_age', 30)  # Default age if not specified
story_chapters = storyline_data['story_chapters']

print(f"Main Character Description: {main_character_description}")
print(f"Main Character Gender: {main_character_gender}")

repo_id = "h94/IP-Adapter-FaceID"
file_path = sdu.check_and_download(repo_id, sdu.IP_CKPT_FILENAME)
if not file_path:
    logging.error(f"IP-Adapter checkpoint could not be downloaded.")
    exit(1)

# Update function call to pass necessary parameters
attempts = 0
success = False

user_image, user_image_path = sdu.initialize_main_character(main_character_description, main_character_gender, storyline_data, storyline_path)
logging.info(f"Main character image generated and saved at: {user_image_path}")

initial_embedding, initial_aligned_face = sdu.extract_embeddings(user_image_path)
if initial_embedding is not None and initial_aligned_face is not None:
    success = True

if not success:
    logging.error("Failed to extract embedding from main character image after 5 attempts. Exiting.")
    exit(1)

total_start_time = time()

total_images_generated = 0
total_generation_time = 0

for selected_model in TOP_MODELS:
    logging.info(f"Processing model: {selected_model}")
    check_and_clear_cache_if_needed(MIN_FREE_SPACE_BYTES)
    total_images_generated, total_generation_time = sdu.process_model(
        selected_model, storyline_data, storyline_path, initial_embedding, initial_aligned_face, total_images_generated, total_generation_time, file_path)

total_end_time = time()
total_elapsed_time = total_end_time - total_start_time

if total_images_generated > 0:
    average_time_per_image = total_elapsed_time / total_images_generated
else:
    average_time_per_image = 0

logging.info("=== SUMMARY ===")
logging.info(f"Total images generated: {total_images_generated}")
logging.info(f"Total elapsed time: {total_elapsed_time:.2f} seconds")
logging.info(f"Average time per image: {average_time_per_image:.2f} seconds")
logging.info("All images have been generated.")