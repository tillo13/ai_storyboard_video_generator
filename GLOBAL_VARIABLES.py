# GLOBAL_VARIABLES.py

# Used in 1_dream_up_a_story.py, 2_build_out_chapters.py, and 3_summarize_chapters_add_ai_prompts.py
GLOBAL_MODEL_NAME = 'llama3'
# Used in run_all.ps1 to specify the number of times to loop through the process
NUMBER_OF_RUNS = 5
# Used in 2_build_out_chapters.py to decide how many chapters to make per model
NUMBER_OF_CHAPTERS_PER_STORY = 8

# Used in 6_create_movie.py for the default length of the video in seconds
DEFAULT_VIDEO_LENGTH = 55

#Used in 4_create_images_from ai_prompts.py for specifying sdxl1.5 (ONLY SD15) models
TOP_MODELS = [
    "stablediffusionapi/disney-pixal-cartoon",
    "Lykon/DreamShaper"
]

# Flag to indicate whether to archive all previous generations at the start of each script
ARCHIVE_ALL_PREVIOUS_GENERATIONS = True

ADD_COMPARISONS_TO_ENHANCED_VS_GENERATED = True #this will show a side by side comparison of the enhanced image versus the regular generated image from the model
NUM_SAMPLES = 1  # Number of images to generate per prompt.
GUIDANCE_SCALE = 6.5  # Higher values increase adherence to the prompt for more consistent image generation.
#NUM_INFERENCE_STEPS = 30  # Number of forward steps taken during the generation process, affecting image quality and detail.

DEFAULT_WIDTH = 768  # Default width in pixels for the generated images.
DEFAULT_HEIGHT = 1024  # Default height in pixels for the generated images.

#if you have too many duplicate heads in your images, try smaller output images and upscale later.  The modesl tend to try to fill space with too much.
DEFAULT_WIDTH = 576  # Default width in pixels for the generated images.
DEFAULT_HEIGHT = 768  # Default height in pixels for the generated images.

SEED = 1060  # Seed value for random number generation to ensure reproducibility.
CFG_SCALE = 1.13  # Configuration scaling factor that adjusts the influence of certain model elements on the final image.
NUMBER_OF_STEPS = 21  # The number of denoising steps used during image generation, which can impact the final image quality.
RANDOMIZE_SEED_VALUE = True  # Set to True for varied image generation, creating different outputs on each run with the same prompt.
DISABLE_SAFETY_CHECKER = True  # If false, will block anything over G rating.
# Added variable for deleting the initial JSON file via 3_summarize_chapters_add_ai_prompts.py
DELETE_INITIAL_STORYLINE_JSON = True

#USER_PROVIDED_IMAGE_PATH = "user_images/andy.png"  # Default to an empty string, meaning no user-provided image by default

#set this if there is a character you think a StableDiff model above knows well and it will just create the image without need for default. 
USER_PROVIDED_EXACT_CHARACTER = "Wolverine"

USER_PROVIDED_MAIN_CHARACTER_DESCRIPTION = "Marvel comic superhero"
USER_PROVIDED_MAIN_CHARACTER_SUPERPOWER = "claws"
USER_PROVIDED_GENDER = "male"  
USER_PROVIDED_NAME = "Wolverine"
USER_PROVIDED_AGE = 50
USER_PROVIDED_NATIONALITY = "USA"
USER_PROVIDED_MAIN_CHARACTER_HOME = "Helena, Montana"
USER_PROVIDED_STORY_THEME = "Superhero saving planet from aliens"

#USER_PROVIDED_YOUTUBE_MUSIC = "https://www.youtube.com/watch?v=rWulO_gttCI"
USER_PROVIDED_ARTISTIC_STYLE = "Marvel"
