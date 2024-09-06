import os
import sys
import time
import json
import random
import logging
from datetime import datetime
import re
import torch
from diffusers import StableDiffusionXLPipeline, DPMSolverMultistepScheduler
from PIL import Image

import GLOBAL_VARIABLES as gv

# Make sure the 'utilities' directory is in your Python path
utilities_path = os.path.join(os.path.dirname(__file__), 'utilities')
if utilities_path not in sys.path:
    sys.path.append(utilities_path)

import utilities.stablediffusion_utils as sdu
from utilities.enhance_image_via_import import enhance_image

# Setup logging
logging.basicConfig(level=logging.DEBUG)

# Define scheduler and settings
SPECIFIC_SCHEDULER = "DPM++ 2M Karras"
guidance_scale = 8.0
num_inference_steps = 30
negative_prompt = "blurry, ugly, duplicate, poorly drawn face, deformed, mosaic, artifacts, bad limbs"
RANDOMIZE_SEED = True  # Set to True to randomize the seed
fixed_seed = 3450349066
seed = fixed_seed if not RANDOMIZE_SEED else random.randint(0, 2**32 - 1)
torch.manual_seed(seed)  # Set the global seed for reproducibility

model_id = "stabilityai/stable-diffusion-xl-base-1.0"
pipe = StableDiffusionXLPipeline.from_pretrained(model_id, torch_dtype=torch.float16)
pipe = pipe.to("cuda")

# Directory paths
GENERATED_IMAGES_PATH = "generated_images"
ENHANCED_IMAGES_PATH = "enhanced_images"
COMPARISONS_PATH = "comparisons"
ARCHIVE_FOLDER_NAME = "archive"
FOLDERS_TO_ARCHIVE = [COMPARISONS_PATH, GENERATED_IMAGES_PATH, ENHANCED_IMAGES_PATH]

# Function to create directories
def create_directories(path):
    if not os.path.exists(path):
        os.makedirs(path)

# Ensure the output directories exist
create_directories(GENERATED_IMAGES_PATH)
create_directories(ENHANCED_IMAGES_PATH)
create_directories(COMPARISONS_PATH)

# Function to get the current timestamp
def get_timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def update_storyline_with_generated_image(storyline_data, index, model_name, filename, storyline_path):
    sanitized_model_name = re.sub(r'\W+', '_', model_name)
    chapter_image_key = f"chapter_image_location_{sanitized_model_name}"
    storyline_data['story_chapters'][index][chapter_image_key] = filename

    with open(storyline_path, 'w') as json_file:
        json.dump(storyline_data, json_file, indent=2)

def ensure_subdir(base_dir, subdir_name):
    path = os.path.join(base_dir, subdir_name)
    if not os.path.exists(path):
        os.makedirs(path)
    return path

def generate_images_for_character():
    storyline_files = [f for f in os.listdir(sdu.STORYLINES_PATH) if f.endswith('_summaries.json')]
    if not storyline_files:
        logging.error("No storyline files are found in storylines")
        return

    latest_file = max(storyline_files, key=lambda f: os.path.getctime(os.path.join(sdu.STORYLINES_PATH, f)))
    storyline_path = os.path.join(sdu.STORYLINES_PATH, latest_file)

    with open(storyline_path, 'r') as f:
        storyline_data = json.load(f)

    story_chapters = storyline_data['story_chapters']

    # Ensure sub-directory for model within ENHANCED_IMAGES_PATH
    model_subdir = re.sub(r'\W+', '_', SPECIFIC_SCHEDULER)
    model_enhanced_path = ensure_subdir(ENHANCED_IMAGES_PATH, model_subdir)

    for i, scene in enumerate(story_chapters, start=1):
        prompt = f"{gv.USER_PROVIDED_EXACT_CHARACTER}, a superhero, {scene} Highly detailed, sharp, photorealism, cinematic lighting"
        
        pipe.scheduler = DPMSolverMultistepScheduler.from_config(pipe.scheduler.config)
        
        if hasattr(pipe.scheduler.config, 'lower_order_final'):
            pipe.scheduler.config.lower_order_final = True

        start_time = time.time()
        generator_seed = seed + i  # Adjust the seed slightly for each generation
        if RANDOMIZE_SEED:
            generator_seed = random.randint(0, 2**32 - 1)
        generator = torch.Generator(device="cuda").manual_seed(generator_seed)
        result = pipe(
            prompt=prompt,
            negative_prompt=negative_prompt,
            num_inference_steps=num_inference_steps,
            guidance_scale=guidance_scale,
            generator=generator
        )
        image = result.images[0]
        time_taken = time.time() - start_time

        timestamp = get_timestamp()
        output_image_name = f"scene_{i}_DPM++_2M_Karras_{timestamp}.png"
        output_image_path = os.path.join(GENERATED_IMAGES_PATH, output_image_name)
        image.save(output_image_path)
        logging.info(f"Generated image for scene {i} with DPM++ 2M Karras saved as {output_image_path} (time taken: {time_taken:.2f}s)")

        # Enhance the image
        try:
            enhanced_image_result = enhance_image(output_image_path, model_enhanced_path)
            # Set final path for enhanced image
            enhanced_image_filename = output_image_name.replace(".png", "_enhanced.png")
            enhanced_image_result_path = os.path.join(model_enhanced_path, enhanced_image_filename)
            enhanced_image_result.save(enhanced_image_result_path)
            logging.info(f"Enhanced image saved as {enhanced_image_result_path}")
            
            # Update the storyline with the generated image filename
            update_storyline_with_generated_image(storyline_data, i-1, SPECIFIC_SCHEDULER, enhanced_image_result_path, storyline_path)
        
        except Exception as e:
            logging.error(f"Error enhancing image: {output_image_path}, error: {e}")

generate_images_for_character()