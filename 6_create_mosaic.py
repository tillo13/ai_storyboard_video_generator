import os
from datetime import datetime
from PIL import Image
import json

# Directory paths
OUTPUT_FOLDER = 'mosaics'
STORYLINES_FOLDER = 'storylines'
GENERATED_IMAGES_BASE_PATH = 'enhanced_images'

# Ensure the output folder exists
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def get_latest_summary_file(directory):
    latest_file = None
    latest_time = None
    formats_to_try = ["%Y-%m-%d_%H-%M", "%Y%m%d_%H%M%S"]

    for filename in os.listdir(directory):
        if filename.endswith("_summaries.json"):
            for fmt in formats_to_try:
                try:
                    file_time = datetime.strptime(filename[:16], fmt)
                    if latest_time is None or file_time > latest_time:
                        latest_time = file_time
                        latest_file = os.path.join(directory, filename)
                except ValueError:
                    continue
    
    return latest_file

def parse_summary_file(summary_file):
    with open(summary_file, 'r', encoding='utf-8') as file:
        data = json.load(file)
    return data

def create_mosaic(image_paths, columns=3):
    images = [Image.open(image_path) for image_path in sorted(image_paths)]
    if not images:
        print("Warning: No images to create mosaic.")
        return None

    widths, heights = zip(*(i.size for i in images))
    max_width = max(widths)
    max_height = max(heights)
    rows = -(-len(images) // columns)
    mosaic_width = columns * max_width
    mosaic_height = rows * max_height

    mosaic_image = Image.new('RGBA', (mosaic_width, mosaic_height), (255, 255, 255, 0))
    for index, image in enumerate(images):
        row, col = divmod(index, columns)
        x = col * max_width
        y = row * max_height
        mosaic_image.paste(image, (x, y))

    return mosaic_image

def resize_image(image, max_width=1024, max_height=1024):
    thumbnail_size = (max_width, max_height)
    image.thumbnail(thumbnail_size, Image.LANCZOS)

def main():
    print("Starting processing of images.")
    summary_file = get_latest_summary_file(STORYLINES_FOLDER)
    
    if not summary_file:
        print("No summary file found.")
        return
    
    summary_data = parse_summary_file(summary_file)
    story_filename = os.path.splitext(os.path.basename(summary_file))[0]
    
    model_image_paths = {}

    for model_run_folder in os.listdir(GENERATED_IMAGES_BASE_PATH):
        model_run_path = os.path.join(GENERATED_IMAGES_BASE_PATH, model_run_folder)

        if not os.path.isdir(model_run_path):
            print(f"Skipping non-directory: {model_run_folder}")
            continue

        for chapter in summary_data["story_chapters"]:
            chapter_items = list(chapter.items())
            for key, image_file in chapter_items:
                if key.startswith("chapter_image_location") and key != "chapter_summary" and "subtitled" not in key:
                    model = key.replace("chapter_image_location_", "").replace("_subtitled", "")

                    if model != model_run_folder:
                        continue

                    filepath = os.path.normpath(image_file)

                    if not os.path.exists(filepath):
                        print(f"Image file {filepath} does not exist.")
                        continue

                    print(f"Processing image: {filepath} for model: {model}")
                    
                    if model not in model_image_paths:
                        model_image_paths[model] = []
                    model_image_paths[model].append(filepath)

    for model, image_paths in model_image_paths.items():
        mosaic_image = create_mosaic(image_paths)
        if mosaic_image:
            resize_image(mosaic_image)
            mosaic_output_filename = f"{story_filename}_{model}.png"
            mosaic_output_path = os.path.join(OUTPUT_FOLDER, mosaic_output_filename)
            mosaic_image.save(mosaic_output_path, 'PNG')
            print(f"Mosaic saved to {mosaic_output_path}")

    print("Processing complete.")

if __name__ == "__main__":
    main()