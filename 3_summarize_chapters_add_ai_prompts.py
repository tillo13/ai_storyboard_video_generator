import os
import time
import json
import atexit
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

try:
    import GLOBAL_VARIABLES  # Import the global variables module
except ImportError:
    class GLOBAL_VARIABLES:  # A dummy class to act as a placeholder for missing GLOBAL_VARIABLES
        GLOBAL_MODEL_NAME = None
        DELETE_INITIAL_STORYLINE_JSON = False

# Define the model name with fallback
MODEL_NAME = getattr(GLOBAL_VARIABLES, 'GLOBAL_MODEL_NAME', 'llama3')

# Define the deletion flag for initial JSON with fallback
DELETE_INITIAL_STORYLINE_JSON = getattr(GLOBAL_VARIABLES, 'DELETE_INITIAL_STORYLINE_JSON', False)

DIRECTORY_PATH = 'storylines'  # Directory where the JSON file is created

# Constant to append to each prompt to avoid filler information
APPEND_TO_EACH = " Respond with only the response, nothing more."

# Updated Summary Request Template
SUMMARY_REQUEST_TEMPLATE = (
    "Using the overall synopsis: \"{synopsis}\" and the preceding chapter summary: \"{preceding_chapter_summary}\", summarize the following chapter content "
    "in a single sentence of 15 words or less with appropriate verbiage for a teenage audience. "
    "Do not include any introductions like 'Here is a summary'. Respond with the summary only: \"{line}\"" + APPEND_TO_EACH
)

CHAPTER_REQUEST_TEMPLATE = (
    "Summarize the following in 15 words or less, with a maximum of 100 characters, as a comma-separated list: \"{line}\"" + APPEND_TO_EACH
)

# Example of positive prompt - comma-separated, descriptive phrases
POSITIVE_EXAMPLES = (
    "sfw, clothed, raw photo, 6k HDR, f1.4, 24mm, cinematic shot, photorealistic:0.9"
)

# Example of negative prompt - comma-separated, things to avoid
NEGATIVE_EXAMPLES = (
    "extra hands, extra limbs, inappropriate"
)

POSITIVE_AI_PROMPT_TEMPLATE = (
    "Create a vivid, highly-detailed scene with a list of comma-separated visual descriptors for the following storyline: \"{line}\". "
    "Use a maximum of 20 words, focusing on impactful descriptions that bring the scene to life. "
    "Refer to the main character, and respond with a maximum of 100 characters. "
    "Use the given example list as inspiration: " + POSITIVE_EXAMPLES + APPEND_TO_EACH
)

NEGATIVE_AI_PROMPT_TEMPLATE = (
    "You are creating a movie scene. Generate a comma-separated list of things to avoid, specifically anything inappropriate like gore or anything inappropriate "
    "for younger audiences, primarily about the character, for the following storyline: \"{line}\". "
    "These elements and characteristics should not appear in the scene. "
    "Use the given example list as an inspiration for generating similar descriptors of things to avoid but do not copy them unless they are specifically relevant: "
    + NEGATIVE_EXAMPLES + APPEND_TO_EACH
)

KEYWORDS_REQUEST_TEMPLATE = "Generate up to 10 sfw keywords, comma-separated, that tell about the story: \"{summary}\". Always include the keyword 'kumori'. Respond with the keywords only." + APPEND_TO_EACH

# Additional prompts
GENDER_PROMPT = "Pick a gender from this list: male or female." + APPEND_TO_EACH
THEME_PROMPT = "Name a book or movie theme not romance related." + APPEND_TO_EACH
MOVIE_TYPE_PROMPT = "Name a movie genre not romance related." + APPEND_TO_EACH
NAME_PROMPT = "Name a suitable name for the main character." + APPEND_TO_EACH
NATIONALITY_PROMPT = "Name a nationality." + APPEND_TO_EACH
SUPERPOWER_PROMPT = "Name a single-word hobby, skill, or human superpower." + APPEND_TO_EACH
AGE_PROMPT = "Pick a suitable age between 6 and 80 for the main character." + APPEND_TO_EACH

def find_latest_non_summarized_json_file(directory_path):
    """Find the latest non-summarized JSON file in the specified directory."""
    json_files = [f for f in os.listdir(directory_path) if f.endswith('.json') and "_summaries" not in f]
    if not json_files:
        raise FileNotFoundError("No non-summarized JSON files found in the specified directory.")
    latest_file = max(json_files, key=lambda f: os.path.getmtime(os.path.join(directory_path, f)))
    return os.path.join(directory_path, latest_file)

# Update function to include synopsis and previous chapter summary
def get_single_sentence_summary(model_name, line, synopsis, preceding_chapter_summary):
    """Generate a single sentence summary for the JSON file with more context."""
    summary_prompt = SUMMARY_REQUEST_TEMPLATE.format(
        synopsis=synopsis,
        preceding_chapter_summary=preceding_chapter_summary,
        line=line
    )
    summary = get_story_response_from_model(model_name, summary_prompt).strip()
    return summary

def get_comma_separated_summary(model_name, line):
    """Generate a comma-separated summary for use in the positive AI prompt."""
    summary_prompt = CHAPTER_REQUEST_TEMPLATE.format(line=line)
    summary = get_story_response_from_model(model_name, summary_prompt).strip()
    return summary

def generate_main_character_summary(model_name, main_character_description):
    """Generate a maximum of 5 comma-separated single words describing the main character."""
    main_character_summary_prompt = (
        "Generate a maximum of 5 comma-separated single words describing the character: \"{description}\". "
        "Respond with only the 5 words, nothing more."
    ).format(description=main_character_description)
    main_character_summary = get_story_response_from_model(model_name, main_character_summary_prompt).strip()
    return main_character_summary

def generate_positive_ai_prompt(main_character_age, main_character_gender, main_character_superpower, main_character_summary, line_summary, model_name, line, previous_chapter_summary):
    """Generate a positive AI prompt by combining age, gender, superpower, character description, scene description, and previous chapter."""
    char_description = ""
    if main_character_age:
        char_description += f"{main_character_age}-year-old "
    if main_character_gender:
        char_description += f"{main_character_gender}, "
    if main_character_superpower:
        char_description += f"{main_character_superpower}, "
    
    scene_details = get_story_response_from_model(model_name, POSITIVE_AI_PROMPT_TEMPLATE.format(line=line)).strip()

    # Include details to connect with the previous chapter for continuity
    if previous_chapter_summary:
        continuity_detail = f", following the events of the previous chapter: {previous_chapter_summary}"
    else:
        continuity_detail = ""

    positive_prompt = f"{char_description}{main_character_summary}, {line_summary}, {scene_details}{continuity_detail}, {POSITIVE_EXAMPLES.strip()}"
    return positive_prompt.rstrip(', ')

def generate_negative_ai_prompt(model_name, line):
    """Generate a negative AI prompt for a single line using the model."""
    negative_prompt = NEGATIVE_AI_PROMPT_TEMPLATE.format(line=line)
    prompt_response = get_story_response_from_model(model_name, negative_prompt).strip()
    if len(prompt_response) > 300:
        prompt_response = prompt_response[:297] + "..."
    return prompt_response

def generate_keywords(model_name, summary):
    """Generate keywords based on the overall summary of the story."""
    keywords_prompt = KEYWORDS_REQUEST_TEMPLATE.format(summary=summary)
    keywords_response = get_story_response_from_model(model_name, keywords_prompt).strip()
    
    unintended_phrases = ["Here are the keywords:", "The keywords are:", "Keywords:", "Here are the top keywords:", "Generated keywords:"]
    
    for phrase in unintended_phrases:
        if keywords_response.startswith(phrase):
            keywords_response = keywords_response[len(phrase):].strip()
    
    keywords_list = keywords_response.split(", ")
    
    if 'kumori' not in keywords_list:
        keywords_list.insert(0, 'kumori')
    
    keywords_list = keywords_list[:10]
    
    return ", ".join(keywords_list)

def summarize_story_chapters(json_file_path, model_name):
    """Summarize each chapter in the story and save as summaries."""
    with open(json_file_path, 'r') as f:
        data = json.load(f)

    story_chapters = data.get("story_chapters", [])
    summarized_chapters = []

    main_character_name = data.get("main_character", "unknown character")
    main_character_gender = data.get("main_character_gender", "")
    main_character_age = data.get("main_character_age", None)
    main_character_description = data.get("main_character_description", "unspecified description")
    main_character_superpower = data.get("main_character_superpower", None)
    overall_synopsis = data.get("initial_prompt", "")

    previous_chapter_summary = None
    combined_chapters = ""

    for index, chapter in enumerate(story_chapters):
        if isinstance(chapter, str):
            print(f"Summarizing chapter {index + 1}/{len(story_chapters)}")
            line_summary_comma_separated = get_comma_separated_summary(model_name, chapter)
            main_character_summary = generate_main_character_summary(model_name, main_character_description)
            positive_ai_prompt = generate_positive_ai_prompt(main_character_age, main_character_gender, main_character_superpower, main_character_summary, line_summary_comma_separated, model_name, chapter, previous_chapter_summary)
            negative_ai_prompt = generate_negative_ai_prompt(model_name, chapter)
            line_summary_single_sentence = get_single_sentence_summary(model_name, chapter, overall_synopsis, previous_chapter_summary)
            summarized_chapters.append({
                "chapter": chapter,
                "chapter_summary": line_summary_single_sentence,
                "positive_ai_prompt": positive_ai_prompt,
                "negative_ai_prompt": negative_ai_prompt
            })
            previous_chapter_summary = line_summary_single_sentence
            combined_chapters += f"Chapter {index + 1}: {chapter}\n"
        else:
            print(f"Skipping invalid chapter data at index {index}")

    overall_summary = " ".join([chapter["chapter_summary"] for chapter in summarized_chapters])
    story_keywords = generate_keywords(model_name, overall_summary)

    data["story_chapters"] = summarized_chapters
    data["story_keywords"] = story_keywords
    data["chapters_combined"] = combined_chapters.strip()

    base_name = os.path.basename(json_file_path)
    summary_file_name = f"{base_name.split('.')[0]}_summaries.json"
    summary_output_path = os.path.join(os.path.dirname(json_file_path), summary_file_name)

    with open(summary_output_path, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Summaries and keywords saved to {summary_output_path}")

    if DELETE_INITIAL_STORYLINE_JSON:
        os.remove(json_file_path)
        print(f"Deleted original JSON file: {json_file_path}")

def main():
    global MODEL_NAME, DIRECTORY_PATH

    start_time = time.time()

    kill_existing_ollama_service()
    clear_gpu_memory()

    install_and_setup_ollama(MODEL_NAME)

    if is_windows():
        start_ollama_service_windows()
        time.sleep(10)

    latest_json_file = find_latest_non_summarized_json_file(DIRECTORY_PATH)
    print(f"Processing latest non-summarized JSON file: {latest_json_file}")

    summarize_story_chapters(latest_json_file, MODEL_NAME)

    stop_ollama_service()
    clear_gpu_memory()

    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"Total time taken: {elapsed_time:.2f} seconds")

if __name__ == "__main__":
    atexit.register(stop_ollama_service)
    atexit.register(clear_gpu_memory)
    main()