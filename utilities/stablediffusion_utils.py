import os
import logging
import json
import random
import re
import sys
import shutil
import time
from datetime import datetime
from PIL import Image
from diffusers import DiffusionPipeline, StableDiffusionPipeline, AutoencoderKL, DDIMScheduler
from huggingface_hub import hf_hub_download
import torch

# Adjust the sys.path to include the parent directory for GLOBAL_VARIABLES
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Importing global variables and utilities
import GLOBAL_VARIABLES as gv
import utilities.faceid_utils as faceid_utils
from enhance_image_via_import import enhance_image
import utilities.main_character_generator_utils as mcg  # Importing the main character generator module

# Constants from GLOBAL_VARIABLES with defaults
TOP_MODELS = getattr(gv, 'TOP_MODELS', ["runwayml/stable-diffusion-v1-5"])
DISABLE_SAFETY_CHECKER = getattr(gv, 'DISABLE_SAFETY_CHECKER', True)
ADD_COMPARISONS_TO_ENHANCED_VS_GENERATED = getattr(gv, 'ADD_COMPARISONS_TO_ENHANCED_VS_GENERATED', False)
CFG_SCALE = getattr(gv, 'CFG_SCALE', 7.5)
NUM_SAMPLES = getattr(gv, 'NUM_SAMPLES', 1)
DEFAULT_WIDTH = getattr(gv, 'DEFAULT_WIDTH', 512)
DEFAULT_HEIGHT = getattr(gv, 'DEFAULT_HEIGHT', 512)
NUMBER_OF_STEPS = getattr(gv, 'NUMBER_OF_STEPS', 30)
RANDOMIZE_SEED_VALUE = getattr(gv, 'RANDOMIZE_SEED_VALUE', True)
SEED = getattr(gv, 'SEED', 42)
IP_CKPT_FILENAME = "ip-adapter-faceid-plusv2_sd15.bin"
NEGATIVE_PROMPTS = getattr(gv, 'NEGATIVE_PROMPTS', {
    "default": "nsfw, portrait, inactive, closeup, nsfw"
})

# Other Constants
STORYLINES_PATH = "storylines"  # Ensure this is defined
AI_GENERATED_USERS_PATH = "ai_generated_characters"
GENERATED_IMAGES_PATH = "generated_images"
ENHANCED_IMAGES_PATH = "enhanced_images"
COMPARISONS_PATH = "comparisons"
ARCHIVE_FOLDER_NAME = "archive"
FOLDERS_TO_ARCHIVE = [COMPARISONS_PATH, GENERATED_IMAGES_PATH, ENHANCED_IMAGES_PATH, AI_GENERATED_USERS_PATH]

def bytes_to_gb(bytes):
    return bytes / (1024 * 1024 * 1024)

def get_free_disk_space():
    statvfs = os.statvfs('/')
    return statvfs.f_frsize * statvfs.f_bavail

def clear_cache_if_disk_space_low(min_free_space_bytes):
    free_space = get_free_disk_space()
    if free_space < min_free_space_bytes:
        logging.info("Low disk space, clearing cache")
        shutil.rmtree("path/to/cache")

def check_and_download(repo_id, filename):
    logging.info(f"Checking for {filename} in the cache or downloading if not present from repo: {repo_id}...")
    try:
        file_path = hf_hub_download(repo_id=repo_id, filename=filename)
        abs_path = os.path.abspath(file_path)
        logging.info(f"Found or successfully downloaded {filename} at {abs_path}")
        return abs_path
    except Exception as e:
        logging.error(f"Failed to download {filename} from {repo_id}: {e}")
        return None

def load_pipeline(model_id, disable_safety_checker):
    try:
        logging.info(f"Loading pipeline for model: {model_id}")
        pipeline = DiffusionPipeline.from_pretrained(
            model_id,
            torch_dtype=torch.float16
        ).to("cuda")
        if disable_safety_checker:
            pipeline.safety_checker = None  
            logging.info(f"Safety checker disabled for pipeline.")
        return pipeline
    except Exception as e:
        logging.error(f"Failed to load model {model_id}: {e}")
        return None

def generate_image(prompt, negative_prompt, seed, width, height, pipeline):
    generator = torch.manual_seed(seed)
    try:
        logging.info(f"Generating image with prompt: {prompt}, negative_prompt: {negative_prompt}, seed: {seed}")
        image = pipeline(
            prompt=prompt,
            negative_prompt=negative_prompt,
            num_inference_steps=NUMBER_OF_STEPS,
            guidance_scale=CFG_SCALE,
            width=width,
            height=height,
            generator=generator
        ).images[0]
        return image
    except Exception as e:
        logging.error(f"Error generating image: {e}")
        return None

def find_correct_image_path(image_path):
    base_name = os.path.splitext(image_path)[0]
    directory = os.path.dirname(image_path)
    possible_extensions = ['.jpg', '.jpeg', '.png']
    
    for ext in possible_extensions:
        potential_path = base_name + ext
        if os.path.exists(potential_path):
            return potential_path
    return None

def extract_embeddings(image_path):
    logging.info(f"[extract_face_embedding] Extracting face embedding from {image_path}")

    try:
        embeddings, aligned_face = faceid_utils.extract_face_embedding(image_path)

        # Assumption: embeddings and aligned_face are not None when face detection is successful
        if embeddings is not None and aligned_face is not None:
            logging.info(f"Face recognition successful for {image_path}")
            print(f"Face recognition successful for {image_path}")
            return embeddings, aligned_face
        else:
            logging.error(f"Face recognition failed for {image_path}")
            print(f"Face recognition failed for {image_path}")
            return None, None

    except Exception as e:
        logging.error(f"Error extracting face embedding from {image_path}: {e}")
        print(f"Error extracting face embedding from {image_path}: {e}")
        return None, None

def save_main_character_image(image, path):
    if image and path:
        image.save(path)

def load_main_character_image(image_path):
    if os.path.exists(image_path):
        try:
            image = Image.open(image_path)
            logging.info(f"Main character image successfully loaded from {image_path}")
            return image
        except Exception as e:
            logging.error(f"Unable to load main character image. Error: {e}")
    else:
        logging.error(f"Main character image path does not exist: {image_path}")
    return None

def sanitize_filename(filename):
    sanitized = re.sub(r'\W+', '_', filename)
    return sanitized[:15]

def sanitize_model_name(model_name):
    return re.sub(r'\W+', '_', model_name)

def combine_images(image1_path, image2_path, output_path):
    image1 = Image.open(image1_path)
    image2 = Image.open(image2_path)
    
    combined_width = image1.width + image2.width
    combined_height = max(image1.height, image2.height)
    
    combined_image = Image.new('RGB', (combined_width, combined_height))
    combined_image.paste(image1, (0, 0))
    combined_image.paste(image2, (image1.width, 0))
    
    combined_image.save(output_path)

def initialize_main_character(main_character_description, main_character_gender, storyline_data, storyline_path):
    user_provided_image_path = storyline_data.get('user_image_path', None)

    if user_provided_image_path and user_provided_image_path.lower() != 'null':
        corrected_image_path = find_correct_image_path(user_provided_image_path)
        if corrected_image_path:
            user_image = load_main_character_image(corrected_image_path)
            logging.info(f"Using user-provided main character image from {corrected_image_path}")
            return user_image, corrected_image_path
        else:
            logging.error("Main character image not found or not valid.")
            exit(1)
    else:
        logging.info("No user-provided image. Generating main character image...")

        attempts = 0
        success = False
        main_character_image_path = None

        while attempts < 5 and not success:
            main_character_image_path = mcg.create_main_character_image(main_character_description, storyline_data.get('main_character_age', 30), main_character_gender)
            logging.info(f"Main character image generated and saved at: {main_character_image_path}")

            initial_embedding, initial_aligned_face = extract_embeddings(main_character_image_path)
            if initial_embedding is not None and initial_aligned_face is not None:
                success = True
            else:
                attempts += 1
                logging.warning("Failed to extract embedding from main character image. Retrying...")
                print(f"Attempt {attempts}: Failed to extract embedding from main character image. Retrying...")

        if not success:
            logging.error("Failed to extract embedding from main character image after 5 attempts. Exiting.")
            print("Failed to extract embedding from main character image after 5 attempts. Exiting.")
            exit(1)

        storyline_data['user_image_path'] = main_character_image_path
        with open(storyline_path, 'w') as f:
            json.dump(storyline_data, f, indent=4)
        
        return load_main_character_image(main_character_image_path), main_character_image_path

def remove_extra_spaces_in_prompts(prompt):
    return ','.join(part.strip() for part in prompt.split(','))

def process_model(selected_model, storyline_data, storyline_path, initial_embedding, initial_aligned_face, total_images_generated, total_generation_time, file_path):
    logging.info(f"Downloading model '{selected_model}' from the hub.")
    pipeline = load_pipeline(selected_model, DISABLE_SAFETY_CHECKER)

    if not pipeline:
        logging.error(f"Failed to load model '{selected_model}'. Skipping.")
        return total_images_generated, total_generation_time

    logging.info(f"Setting up Stable Diffusion pipeline using model: '{selected_model}'.")
    vae_model_path = "stabilityai/sd-vae-ft-mse"
    noise_scheduler = DDIMScheduler(
        num_train_timesteps=1000,
        beta_start=0.00085,
        beta_end=0.012,
        beta_schedule="scaled_linear",
        clip_sample=False,
        set_alpha_to_one=False,
        steps_offset=1,
    )
    vae = AutoencoderKL.from_pretrained(vae_model_path).to(dtype=torch.float16)
    pipe = StableDiffusionPipeline.from_pretrained(
        selected_model,
        torch_dtype=torch.float16,
        scheduler=noise_scheduler,
        vae=vae,
        feature_extractor=None,
        safety_checker=None 
    ).to("cuda")
    logging.info(f"Stable Diffusion pipeline set up using model: {selected_model}")

    from ip_adapter.ip_adapter_faceid import IPAdapterFaceIDPlus

    logging.info("Loading IP-Adapter.")
    device = "cuda"
    image_encoder_path = "laion/CLIP-ViT-H-14-laion2B-s32B-b79K"
    ip_model = IPAdapterFaceIDPlus(pipe, image_encoder_path, file_path, device)
    logging.info("IP-Adapter loaded successfully.")

    logging.info("Processing chapter images...")
    
    for chapter in storyline_data['story_chapters']:
        chapter['positive_ai_prompt'] = remove_extra_spaces_in_prompts(chapter['positive_ai_prompt'])
        chapter['negative_ai_prompt'] = remove_extra_spaces_in_prompts(chapter['negative_ai_prompt'])

    total_images_generated, total_generation_time = process_chapter_images(
        selected_model,
        storyline_data,
        storyline_path,
        pipeline,
        ip_model,
        initial_embedding,
        initial_aligned_face,
        NEGATIVE_PROMPTS,
        total_images_generated,
        total_generation_time
    )
    
    return total_images_generated, total_generation_time
def process_chapter_images(model_name, storyline_data, storyline_path, pipeline, ip_model, initial_embedding, initial_aligned_face, NEGATIVE_PROMPTS, total_images_generated, total_generation_time):
    artistic_style = storyline_data.get("artistic_style", "default style")
    sanitized_model_name = sanitize_model_name(model_name)
    model_generated_images_path = os.path.join(GENERATED_IMAGES_PATH, sanitized_model_name)
    os.makedirs(model_generated_images_path, exist_ok=True)

    model_enhanced_images_path = os.path.join(ENHANCED_IMAGES_PATH, sanitized_model_name)
    os.makedirs(model_enhanced_images_path, exist_ok=True)

    model_comparisons_path = os.path.join(COMPARISONS_PATH, sanitized_model_name)
    os.makedirs(model_comparisons_path, exist_ok=True)

    for idx, chapter in enumerate(storyline_data['story_chapters']):  # fixed the loop
        image_start_time = time.time()
        positive_prompt = f"in the style of {artistic_style}, {chapter['positive_ai_prompt']}"
        negative_prompt = f"{NEGATIVE_PROMPTS['default']}, {chapter['negative_ai_prompt']}"

        if RANDOMIZE_SEED_VALUE:
            seed = random.randint(0, 100000)
        else:
            seed = SEED + idx

        try:
            images = ip_model.generate(
                prompt=positive_prompt,
                negative_prompt=negative_prompt,
                faceid_embeds=initial_embedding,
                face_image=initial_aligned_face,
                shortcut=True,
                s_scale=CFG_SCALE,
                num_samples=NUM_SAMPLES,
                width=DEFAULT_WIDTH,
                height=DEFAULT_HEIGHT,
                num_inference_steps=NUMBER_OF_STEPS,
                seed=seed
            )
            if images is None or len(images) == 0:
                raise ValueError("Generated image is None or empty.")
        except Exception as e:
            logging.error(f"Error generating image: {e}")
            continue

        adjusted_image = images[0]
        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        sanitized_activity = sanitize_filename(chapter.get('chapter', 'chapter'))

        filename_prefix = f"{timestamp_str}_{sanitized_model_name}_{sanitized_activity}_{seed}"
        result_image_path = os.path.join(model_generated_images_path, f"{filename_prefix}.png")
        adjusted_image.save(result_image_path)
        
        try:
            enhanced_image_result = enhance_image(result_image_path, model_enhanced_images_path)
            enhanced_image_result_path = os.path.join(model_enhanced_images_path, f"{filename_prefix}_enhanced.png")
            enhanced_image_result.save(enhanced_image_result_path)
            chapter_image_key = f"chapter_image_location_{sanitized_model_name}"
            storyline_data['story_chapters'][idx][chapter_image_key] = enhanced_image_result_path

            with open(storyline_path, 'w') as json_file:
                json.dump(storyline_data, json_file, indent=2)

            if ADD_COMPARISONS_TO_ENHANCED_VS_GENERATED:
                comparison_image_path = os.path.join(model_comparisons_path, f"{filename_prefix}_comparison.png")
                combine_images(result_image_path, enhanced_image_result_path, comparison_image_path)
                logging.info(f"Comparison image saved to {comparison_image_path}")

        except Exception as e:
            logging.error(f"Error enhancing image: {result_image_path}, error: {e}")

        total_images_generated += 1
        elapsed_time = time.time() - image_start_time
        total_generation_time += elapsed_time

    return total_images_generated, total_generation_time