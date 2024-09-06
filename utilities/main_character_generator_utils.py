from diffusers import DiffusionPipeline
import torch
from datetime import datetime
import os
import argparse
from PIL import Image
import random

# Create the ai_generated_characters directory if it doesn't exist
os.makedirs('ai_generated_characters', exist_ok=True)

# Define the model ID
model_id = "digiplay/Photon_v1"

# Use random seed
USE_RANDOM_SEED = True

# Disable safety checker
SAFETY_CHECKER = False

# Recommended settings and these examples' commonalities
sampling_steps = 35
guidance_scale = 6  # Assuming a middle value; adjust as needed

# Prompts
male_prompt_template = "portrait photo of {} y.o man, perfect face, extremely detailed, intricate, natural skin, professional business man"
female_prompt_template = "portrait photo of {} y.o woman, perfect face, extremely detailed, intricate, natural skin, professional business woman"
negative_prompt = "extra limbs, cross eyes, ugly, (worst quality, low quality, normal quality:2)"

def generate_image(pipeline, prompt, negative_prompt, base_file_name):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"ai_generated_characters/{base_file_name}_{timestamp}.png"
    
    # Set seed for reproducibility if not using random seed
    seed = random.randint(0, 2**32 - 1) if USE_RANDOM_SEED else 1060
    torch.manual_seed(seed)

    # Generate image
    with torch.no_grad():
        result = pipeline(prompt=prompt, negative_prompt=negative_prompt, num_inference_steps=sampling_steps, guidance_scale=guidance_scale)

    # Extract the image
    image = result.images[0]
    
    # Save image
    image.save(file_name)
    print(f"Generated and saved: {file_name}")
    return file_name

def create_main_character_image(description="blonde tall beautiful", age=15, gender="female"):
    # Load the model pipeline
    pipeline = DiffusionPipeline.from_pretrained(model_id)
    
    # Disable the safety checker
    if not SAFETY_CHECKER:
        pipeline.safety_checker = None
        
    pipeline.to('cuda' if torch.cuda.is_available() else 'cpu')  # Use GPU if available
    
    # Select the appropriate prompt
    if gender.lower() == 'male':
        prompt = male_prompt_template.format(age) + ", " + description
        base_file_name = "photon_v1_main_character_male"
    elif gender.lower() == 'female':
        prompt = female_prompt_template.format(age) + ", " + description
        base_file_name = "photon_v1_main_character_female"
    else:
        raise ValueError("Invalid gender. Use 'male' or 'female'.")

    # Generate and save the image
    return generate_image(pipeline, prompt, negative_prompt, base_file_name)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate photorealistic portraits using a diffusion model.')
    parser.add_argument('-age', type=int, required=False, default=15, help="Age of the person in the portrait")
    parser.add_argument('-gender', type=str, required=False, choices=["male", "female"], default="female", help="Gender of the person in the portrait")
    parser.add_argument('-desc', type=str, default="blonde tall beautiful", help="Description of the character")
    args = parser.parse_args()
    
    create_main_character_image(args.desc, args.age, args.gender)  # Use provided or default parameters