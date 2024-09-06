import os
import json
import re
import time
import atexit
import random
from datetime import datetime
from utilities.ollama_utils import (
    install_and_setup_ollama, 
    kill_existing_ollama_service, 
    clear_gpu_memory, 
    start_ollama_service_windows, 
    stop_ollama_service, 
    is_windows, 
    get_story_response_from_model
)
from utilities.archive_utils import archive_previous_generations

try:
    import GLOBAL_VARIABLES  # Import everything in the global variables module
except ImportError:
    # A dummy class to act as a placeholder for missing GLOBAL_VARIABLES
    class GLOBAL_VARIABLES:
        USER_PROVIDED_NATIONALITY = ""
        USER_PROVIDED_GENDER = ""
        USER_PROVIDED_AGE = 0
        USER_PROVIDED_NAME = ""
        USER_PROVIDED_MAIN_CHARACTER_DESCRIPTION = ""
        USER_PROVIDED_IMAGE_PATH = ""
        USER_PROVIDED_MAIN_CHARACTER_SUPERPOWER = ""
        USER_PROVIDED_ARTISTIC_STYLE = ""
        USER_PROVIDED_TONE = ""
        GLOBAL_MODEL_NAME = 'llama3'
        ARCHIVE_ALL_PREVIOUS_GENERATIONS = False

MODEL_NAME = getattr(GLOBAL_VARIABLES, 'GLOBAL_MODEL_NAME', 'llama3')

if getattr(GLOBAL_VARIABLES, 'ARCHIVE_ALL_PREVIOUS_GENERATIONS', False):
    archive_previous_generations()

APPEND_TO_EACH = " Respond with only the response, nothing more, and do not add any quotes to anything"

GENDER_PROMPT = "Pick a gender from this list: male or female." + APPEND_TO_EACH
THEME_PROMPT = "Name a book or movie theme not romance related" + APPEND_TO_EACH
MOVIE_TYPE_PROMPT = "Name a movie genre not romance related." + APPEND_TO_EACH
NATIONALITY_PROMPT = "Name a nationality." + APPEND_TO_EACH
SUPERPOWER_PROMPT = "Name a single-word hobby, skill, or human superpower." + APPEND_TO_EACH
ARTISTIC_STYLE_PROMPT = "Generate the full name of a famous art painter whose first or last name starts with the letter {letter}. Respond with only the full name of the artist, nothing more, and do not add any quotes or extra text."
STORYLINE_TEMPLATE = (
    "Create a one-sentence storyline with the following details including naming the main character. "
    "Main Character: {main_character}, Gender: {gender}, Place: {place}, Nationality: {nationality}, Age: {age}, Superpower: {superpower}, Main Character Description: {main_character_description}, Theme: {theme}, Movie Genre: {movie_type}."
)

INITIAL_PROMPT_TEMPLATE = (
    "Create a succinct single-sentence initial prompt based on the following storyline: \"{storyline}\" "
    "involving the main character {main_character} who is {gender}. "
    "Ensure it sets the stage without giving away the entire story, and add no comment, your reply should ONLY be the prompt."
)

AUTHOR_TEMPLATE = (
    "Based on the storyline '{storyline}' and tone '{tone}', suggest just one author or movie director known for creating similar stories. "
    "Respond with only the name and the book or movie they are famous for, nothing filler or extra but the response, follow this format strictly."
)

output_dir = "storylines"
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
JSON_FILE = os.path.join(output_dir, f"{timestamp}_story.json")

def get_response_from_model(model_name, prompt):
    """ Wrapper function for getting a response from the model """
    response = get_story_response_from_model(model_name, prompt)
    return response.strip()

def clean_response(response):
    """ Clean the response to remove unwanted characters and phrases """
    patterns = [
        r"\n+",  # Remove new lines
        r"^Here\sis\syour\sresponse:\s*",  # Custom phrases that may be added by the model
        r"^Prompt:\s*",
        r"^Response:\s*",
    ]
    for pattern in patterns:
        response = re.sub(pattern, " ", response).strip()
    return response

def create_storyline(model_name, place, gender, nationality, age, superpower, theme, movie_type, main_character, main_character_description):
    """ Create a storyline based on the given inputs naming the main character. """
    storyline_prompt = STORYLINE_TEMPLATE.format(main_character=main_character, gender=gender, place=place, nationality=nationality, age=age, superpower=superpower, main_character_description=main_character_description, theme=theme, movie_type=movie_type)
    storyline = get_response_from_model(model_name, storyline_prompt)
    return clean_response(storyline), storyline_prompt

def suggest_author_or_director(model_name, storyline, tone):
    """ Suggest an author or movie director based on the storyline and tone """
    author_prompt = AUTHOR_TEMPLATE.format(storyline=storyline, tone=tone)
    author = get_response_from_model(model_name, author_prompt)
    return clean_response(author)

def select_random_letter():
    """ Select a random letter from the alphabet except X """
    return random.choice('ABCDEFGHIJKLMNOPQRSTUVWYZ')

def validate_response_starts_with_letter(response, letter):
    """ Validate that the response starts with the specified letter """
    return response.strip().upper().startswith(letter)

def get_valid_response(model_name, prompt_template, letter, max_attempts=3):
    """ Get a response that starts with the specified letter, retry up to max_attempts """
    for attempt in range(max_attempts):
        prompt = prompt_template.format(letter=letter) + APPEND_TO_EACH
        response = get_response_from_model(model_name, prompt)
        response = clean_response(response)
        if validate_response_starts_with_letter(response, letter):
            return response, attempt + 1
    return response, max_attempts  # Return the final attempt if none match

def generate_main_character_description(model_name, main_character, initial_prompt, age, nationality, gender, superpower):
    """ Generate a detailed main character description """
    description_prompt = (
        f"Using the main character named {main_character}, a {age}-year-old {gender} from {nationality}, who has {superpower}, "
        f"described in the story prompt \"{initial_prompt}\", please provide a detailed and engaging character description "
        "in less than 250 characters. Include characteristics such as appearance, personality, and background. Add no filler or intro, just respond ONLY with the description, nothing else."
    )
    description = get_response_from_model(model_name, description_prompt)
    return clean_response(description)

def get_name_prompt(nationality, letter, gender):
    if gender == "male":
        return f"Name a traditional male first name from {nationality} that starts with the letter {letter}. Respond with only the name, nothing more, and do not add any quotes."
    elif gender == "female":
        return f"Name a traditional female first name from {nationality} that starts with the letter {letter}. Respond with only the name, nothing more, and do not add any quotes."
    else:
        return f"Name a traditional first name from {nationality} that starts with the letter {letter}. Respond with only the name, nothing more, and do not add any quotes."


def main():
    kill_existing_ollama_service()
    clear_gpu_memory()

    install_and_setup_ollama(MODEL_NAME)

    if is_windows():
        service_started = start_ollama_service_windows()
        if not service_started:
            print("Ollama service failed to start. Exiting.")
            return
        time.sleep(10)  # Ensure time for the service to be fully up and running

    # Use the provided main character home directly, fallback to fetching if not provided.
    place = getattr(GLOBAL_VARIABLES, 'USER_PROVIDED_MAIN_CHARACTER_HOME', "").strip()
    place_attempts = 0
    if not place:
        random_letter_place = select_random_letter()
        place_prompt_template = "Name a place anywhere in the world that starts with the letter {letter}."
        place, place_attempts = get_valid_response(MODEL_NAME, place_prompt_template, random_letter_place)

    nationality = getattr(GLOBAL_VARIABLES, 'USER_PROVIDED_NATIONALITY', "").strip() or clean_response(get_response_from_model(MODEL_NAME, NATIONALITY_PROMPT))
    gender = getattr(GLOBAL_VARIABLES, 'USER_PROVIDED_GENDER', "").strip().lower() if getattr(GLOBAL_VARIABLES, 'USER_PROVIDED_GENDER', "").strip().lower() in ["male", "female"] else clean_response(get_response_from_model(MODEL_NAME, GENDER_PROMPT))

    # Use the provided age directly
    age = getattr(GLOBAL_VARIABLES, 'USER_PROVIDED_AGE', 0)
    if not (isinstance(age, int) and age > 0):
        age = random.randint(8, 25)  # Fallback to a random age if not valid

    # Use the provided story theme directly, fallback to fetching if not provided.
    theme = getattr(GLOBAL_VARIABLES, 'USER_PROVIDED_STORY_THEME', "").strip() or clean_response(get_response_from_model(MODEL_NAME, THEME_PROMPT))
    
    movie_type = clean_response(get_response_from_model(MODEL_NAME, MOVIE_TYPE_PROMPT))
    random_letter_main_character = select_random_letter()

    main_character = getattr(GLOBAL_VARIABLES, 'USER_PROVIDED_NAME', "").strip()
    main_character_name_attempts = 0
    if not main_character:
        name_prompt = get_name_prompt(nationality, random_letter_main_character, gender)
        main_character, main_character_name_attempts = get_valid_response(MODEL_NAME, name_prompt, random_letter_main_character)

    superpower = getattr(GLOBAL_VARIABLES, 'USER_PROVIDED_MAIN_CHARACTER_SUPERPOWER', "").strip() or clean_response(get_response_from_model(MODEL_NAME, SUPERPOWER_PROMPT))
    main_character_description = getattr(GLOBAL_VARIABLES, 'USER_PROVIDED_MAIN_CHARACTER_DESCRIPTION', "").strip() or generate_main_character_description(MODEL_NAME, main_character, "", age, nationality, gender, superpower)

    tone = getattr(GLOBAL_VARIABLES, 'USER_PROVIDED_TONE', "").strip()
    if not tone:
        tone_prompt = "Generate a suitable tone for the following storyline: \"{storyline}\". Only respond with the tone, nothing else."
        tone = clean_response(get_response_from_model(MODEL_NAME, tone_prompt.format(storyline="")))

    storyline, storyline_prompt = create_storyline(MODEL_NAME, place, gender, nationality, age, superpower, theme, movie_type, main_character, main_character_description)
    initial_prompt_raw = get_response_from_model(MODEL_NAME, INITIAL_PROMPT_TEMPLATE.format(storyline=storyline, main_character=main_character, gender=gender))
    initial_prompt = clean_response(initial_prompt_raw)
    author_or_director = suggest_author_or_director(MODEL_NAME, storyline, tone)

    # Generate artistic style if not provided
    if getattr(GLOBAL_VARIABLES, 'USER_PROVIDED_ARTISTIC_STYLE', "").strip():
        artistic_style = GLOBAL_VARIABLES.USER_PROVIDED_ARTISTIC_STYLE
        artistic_style_attempts = 0
    else:
        random_letter_artistic_style = select_random_letter()
        artistic_style_prompt = ARTISTIC_STYLE_PROMPT.format(letter=random_letter_artistic_style)
        artistic_style, artistic_style_attempts = get_valid_response(MODEL_NAME, artistic_style_prompt, random_letter_artistic_style)

    initial_data = {
        "author": author_or_director,
        "initial_prompt": initial_prompt,
        "main_character_gender": gender,
        "main_character": main_character,
        "main_character_age": age,
        "main_character_nationality": nationality,
        "main_character_superpower": superpower,
        "main_character_description": main_character_description,
        "main_character_home": place,
        "story_theme": theme,
        "story_movie_genre": movie_type,
        "story_tone": tone,
        "storyline": storyline,
        "storyline_prompt": storyline_prompt,
        "home_random_letter_chosen": random_letter_place if 'random_letter_place' in locals() else None,
        "home_attempts_to_generate_match": place_attempts,
        "main_character_random_letter_chosen": random_letter_main_character,
        "main_character_attempts_to_generate_match": main_character_name_attempts,
        "artistic_style": artistic_style,
        "artistic_style_random_letter_chosen": random_letter_artistic_style if 'random_letter_artistic_style' in locals() else None,
        "artistic_style_attempts_to_generate_match": artistic_style_attempts,
        "story_chapters": [initial_prompt],  # Initialize with initial prompt as the first chapter
        "story_summary": "",  # Summary will be added later
        "user_image_path": getattr(GLOBAL_VARIABLES, 'USER_PROVIDED_IMAGE_PATH', None)  # Optional user image path, default to None if not provided
    }

    with open(JSON_FILE, 'w') as f:
        json.dump(initial_data, f, indent=2)

    print(f"Generated initial JSON file: {JSON_FILE}")
    print(f"\nHere is the storyline template used:\n{storyline_prompt}")
    print(f"\nHere is your storyline:\n{storyline}")
    print(f"\nMain Character's Name:\n{main_character}")
    print(f"\nHere is the author or movie director that can help you write this story:\n{author_or_director}")
    if 'random_letter_place' in locals():
        print(f"\nRandom letter chosen for place: {random_letter_place}, Attempts taken: {place_attempts}")
    if 'random_letter_main_character' in locals():
        print(f"\nRandom letter chosen for main character's name: {random_letter_main_character}, Attempts taken: {main_character_name_attempts}")
    print(f"\nFinal selected age: {age}")
    print(f"\nMain character's superpower: {superpower}")
    if 'random_letter_artistic_style' in locals():
        print(f"\nRandom letter chosen for artistic style: {random_letter_artistic_style}, Attempts taken: {artistic_style_attempts}")
    if 'artistic_style' in locals():
        print(f"\nArtistic Style generated: {artistic_style}")

    stop_ollama_service()
    clear_gpu_memory()

if __name__ == "__main__":
    atexit.register(stop_ollama_service)
    atexit.register(clear_gpu_memory)
    main()