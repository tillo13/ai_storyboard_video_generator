import os
import time
import json
import random
import atexit
import re
from datetime import datetime
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
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
    import GLOBAL_VARIABLES  # Import everything in the global variables module
except ImportError:
    class GLOBAL_VARIABLES:  # A dummy class to act as a placeholder for missing GLOBAL_VARIABLES
        GLOBAL_MODEL_NAME = None
        NUMBER_OF_CHAPTERS_PER_STORY = 4
        USER_PROVIDED_TONE = None

# Define the model name with fallback
MODEL_NAME = getattr(GLOBAL_VARIABLES, 'GLOBAL_MODEL_NAME', 'llama3')

# Define the number of loops for story generation with fallback
LOOPS = getattr(GLOBAL_VARIABLES, 'NUMBER_OF_CHAPTERS_PER_STORY', 4)

# Define the tone of the story with fallback
USER_PROVIDED_TONE = getattr(GLOBAL_VARIABLES, 'USER_PROVIDED_TONE', None)

# Constants
MAX_RETRIES = 5
COSINE_SIMILARITY_THRESHOLD = 0.8
SUMMARY_COSINE_SIMILARITY_THRESHOLD = 0.6
CONSTRAINT_REMINDER = "Remember, the response should be only 2 or 3 sentences with a maximum of 100 words in total."
APPEND_TO_EACH = " Respond with only the response, nothing more, and do not add any quotes to anything."
PHASE_INSTRUCTIONS = {
    "beginning": "Establish characters and setting subtly. End with a captivating moment.",
    "middle": "Develop the plot and raise stakes without giving everything away. End with an uneasy anticipation.",
    "end": "Subtly wrap up the narrative while leaving thematic elements open to interpretation."
}

# Define user message template
USER_MESSAGE_TEMPLATE = (
    "We are writing a story together in the style of {persona}. "
    "The tone of the chapter should be '{tone}'. "
    "Continue the following story creatively, making bold assumptions about what could happen next. "
    "Include references to the main character, {main_character_name}, described as {main_character_description}. "
    "Extract the essence of the main character's superpower ({main_character_superpower}) and incorporate it into the narrative in a positive and uplifting manner. "
    "Ensure the narrative builds seamlessly from the previous chapter, keeping the story cohesive and well-aligned. "
    "Smoothly address core story issues and transition to the next scene. "
    "Maintain an imaginative style fitting {persona}'s narrative while keeping responses "
    "3 to 5 sentences and a maximum of 150 words. "
    "Each response should imply {ending}. The current story is: {current_story}. "
    "Here is a summary of the story so far: {summary}. "
    "{phase_instructions} "
    + CONSTRAINT_REMINDER
    + " " + APPEND_TO_EACH
)

# Templates for various prompts
get_tone_prompt = lambda synopsis: f"Generate a suitable tone for a story with this synopsis: \"{synopsis}\". Only respond with the tone, nothing else."
SUMMARY_UPDATE_TEMPLATE = (
    "Here is the current summary of the story: \"{current_summary}\". "
    "The latest addition to the story is: \"{latest_addition}\". "
    "Can you enhance the overall summary with it without changing and limiting the overall summary to 4-5 sentences "
    "and 750 characters? Ensure the summary encourages someone to read more. "
    "If the new addition adds no value, don't change it. Only return the revised summary in your response, nothing else."
    + " " + APPEND_TO_EACH
)
COMPLETE_SYNOPSIS_TEMPLATE = (
    "Please read the following lines from the story: \"{selected_lines}\" and the following summary: \"{summary}\". "
    "Using these, create a captivating synopsis that reads like the cover of a book, enticing someone to read the entire story. "
    "Keep the synopsis limited to 6-7 sentences and less than 900 characters. Return only the synopsis, nothing else."
    + " " + APPEND_TO_EACH
)
CHARACTER_DESCRIPTION_TEMPLATE = (
    "Create a main character description in 250 characters or less, containing ONLY the description and "
    "not a single extra character or introductory phrase. "
    "Provide an engaging and detailed character description within the character limit. "
    "Here is a complete synopsis: {complete_synopsis}. "
    "Here is the initial prompt: {initial_prompt}. "
    "Reply with ONLY the description itself and do not preface your response with anything, just the description."
    + " " + APPEND_TO_EACH
)
MOVIE_TITLE_TEMPLATE = (
    "Given the following summary: \"{summary}\" and the main character description: \"{character_description}\", "
    "generate a captivating movie title. Only respond with the movie title and nothing else."
    + " " + APPEND_TO_EACH
)
MAIN_CHARACTER_GENDER_TEMPLATE = (
    "From the following main character description: \"{character_description}\" "
    "determine the gender of the main character based on pronouns and masculine or feminine names if available. "
    "Reply with ONLY the word male or female, and nothing else."
    + " " + APPEND_TO_EACH
)

# Ensure the directory for saving JSON files exists
output_dir = "storylines"

def get_latest_json_file(directory):
    """ Get the latest modified JSON file from the directory """
    files = [f for f in os.listdir(directory) if f.endswith('.json')]
    if not files:
        return None
    latest_file = max(files, key=lambda f: os.path.getmtime(os.path.join(directory, f)))
    return os.path.join(directory, latest_file)

def get_story_context(current_story, initial_prompt, retry_count):
    """ Generate context for the story based on retry count. """
    if retry_count == 0:
        return " ".join([initial_prompt, *current_story[-2:]])
    elif retry_count == 1:
        return " ".join([initial_prompt, *current_story[-3:]])
    elif retry_count == 2:
        return " ".join(current_story[-1:])
    elif retry_count == 3:
        return " ".join([initial_prompt, current_story[-1]])
    return None

def generate_summary(current_story):
    """ Generate a summary of the current story in 2-3 sentences. """
    full_text = " ".join(current_story)
    sentences = full_text.split(". ")
    summary = ". ".join(sentences[:3]).strip()
    if not summary.endswith("."):
        summary += "."
    summary = summary if len(summary) <= 750 else summary[:747] + "..."
    return ensure_proper_ending(summary)

def ensure_proper_ending(summary):
    """ Ensure the summary ends correctly with common abbreviations and exactly three ellipses. """
    abbreviations = ["Dr.", "Mr.", "Ms.", "Mrs.", "Jr.", "Sr.", "St.", "etc."]
    for abbr in abbreviations:
        if summary.endswith(abbr):
            return summary + "..."
    return summary.rstrip(".") + "..."

def get_phase(loop_index, total_loops):
    """ Determine the phase of the story based on the current loop index. """
    if loop_index < total_loops * 0.25:
        return "beginning"
    elif loop_index < total_loops * 0.9:
        return "middle"
    else:
        return "end"

def calculate_cosine_similarity(text1, text2):
    """ Calculate the cosine similarity between two texts. """
    vectorizer = TfidfVectorizer().fit_transform([text1, text2])
    vectors = vectorizer.toarray()
    return cosine_similarity(vectors)[0, 1]

def enhance_summary(current_summary, latest_addition):
    """ Enhance the overall summary with the latest story addition. """
    summary_prompt = SUMMARY_UPDATE_TEMPLATE.format(current_summary=current_summary, latest_addition=latest_addition)
    enhanced_summary = get_story_response_from_model(MODEL_NAME, summary_prompt).strip()

    # Remove any introductory phrases
    unintended_phrases = [
        "Here is the revised summary:", 
        "Updated summary:", 
        "Revised summary:", 
        "Here is the new summary:"
    ]
    for phrase in unintended_phrases:
        if enhanced_summary.startswith(phrase):
            enhanced_summary = enhanced_summary[len(phrase):].strip()

    return enhanced_summary

def generate_complete_synopsis(current_story, final_summary):
    """ Generate a complete synopsis from selected lines in the story. """
    if len(current_story) < 8:
        selected_lines = current_story
    else:
        selected_lines = []
        selected_lines.extend(current_story[:3])  # First 3 lines
        selected_lines.extend(current_story[-3:])  # Last 3 lines
        remaining_indexes = list(range(3, len(current_story) - 3))
        random.shuffle(remaining_indexes)
        selected_lines.extend([
            current_story[remaining_indexes[0]],
            current_story[remaining_indexes[1]]
        ])  # 2 random lines in the middle

    selected_lines_text = " ".join(selected_lines)
    synopsis_prompt = COMPLETE_SYNOPSIS_TEMPLATE.format(selected_lines=selected_lines_text, summary=final_summary)
    complete_synopsis = get_story_response_from_model(MODEL_NAME, synopsis_prompt).strip()

    return complete_synopsis

def generate_main_character_description(model_name, complete_synopsis, initial_prompt, retries=3):
    """ Generate the main character description ensuring it is under 250 characters. """
    main_character_prompt = CHARACTER_DESCRIPTION_TEMPLATE.format(complete_synopsis=complete_synopsis, initial_prompt=initial_prompt)
    character_description = get_story_response_from_model(model_name, main_character_prompt).strip()

    # Improved clean-up to ensure only the description is returned
    def clean_character_description(text):
        # Remove everything prior to a double newline \n\n
        if "\n\n" in text:
            text = text.split("\n\n", 1)[1].strip()
        patterns = [
            r"^(Here is the simplified character description in 250 characters or less:)", # Remove specific unwanted text
            r"^(Here is a simplified version of the character description:)",
            r"^(Here is the character description:)",
            r"^Character description:",
            r"Character description:",  
        ]
        for pattern in patterns:
            text = re.sub(pattern, "", text).strip()
        return text

    character_description = clean_character_description(character_description)

    attempts = 0
    while len(character_description) > 250 and attempts < retries:
        reprompt = f"Simplify this character description to 250 characters or less without losing key information: \"{character_description}\""
        character_description = get_story_response_from_model(model_name, reprompt).strip()
        character_description = clean_character_description(character_description)
        attempts += 1

    if len(character_description) > 250:  # Fallback if it still exceeds 250 characters
        character_description = character_description[:247] + "..."

    return character_description

def determine_main_character_gender(model_name, character_description, retries=3):
    """ Determine the main character's gender based on the character description. """
    gender_prompt = MAIN_CHARACTER_GENDER_TEMPLATE.format(character_description=character_description)
    valid_responses = ['male', 'female']
    
    attempts = 0
    while attempts < retries:
        gender_response = get_story_response_from_model(model_name, gender_prompt).strip().lower()
        if gender_response in valid_responses:
            return gender_response
        attempts += 1
    
    # If retries are exhausted, infer gender from common pronouns or default to 'male'
    return 'male'

def generate_movie_title(model_name, summary, character_description):
    """ Generate a movie title based on the story summary and main character description. """
    movie_title_prompt = MOVIE_TITLE_TEMPLATE.format(summary=summary, character_description=character_description)
    movie_title = get_story_response_from_model(model_name, movie_title_prompt).strip()
    return movie_title

def generate_tone_if_absent(model_name, synopsis):
    """ Generate the tone if it is not provided. """
    if USER_PROVIDED_TONE:
        return USER_PROVIDED_TONE
    tone_prompt = get_tone_prompt(synopsis)
    tone_response = get_story_response_from_model(model_name, tone_prompt).strip()
    return tone_response

def write_story_segment(model_name, prompt, persona, main_character, main_character_superpower, loops, json_file, tone=None):
    """ Generate story segments and save them to a file, updating JSON real-time. """
    current_story = [prompt]  # Initialize story with the prompt
    overall_summary = generate_summary(current_story)

    # Ensure a tone
    if not tone:
        tone = generate_tone_if_absent(model_name, overall_summary)

    for loop_index in range(loops):
        with open(json_file, 'r') as f:
            data = json.load(f)
            current_story = data["story_chapters"]
            overall_summary = data["story_summary"]
            user_image_path = data.get("user_image_path")
            user_main_character_description = data.get("main_character_description")
            main_character_age = data.get("main_character_age")
            main_character_nationality = data.get("main_character_nationality")
            main_character_name = data.get("main_character", main_character)  # Retrieve main character name when available

            # Extract the main character's superpower
            main_character_superpower = data.get("main_character_superpower")

        retry_count = 0
        phase = get_phase(loop_index, loops)

        if phase == "beginning":
            ending = "an intriguing moment"
        elif phase == "middle":
            ending = "an insight into what might unfold"
        else:  # phase == "end"
            ending = "a resolution with a lingering question"

        phase_instructions = PHASE_INSTRUCTIONS[phase]

        while retry_count <= MAX_RETRIES:
            current_story_text = get_story_context(current_story, prompt, retry_count)
            if current_story_text is None:
                return current_story

            user_message = USER_MESSAGE_TEMPLATE.format(
                current_story=current_story_text, persona=persona,
                summary=overall_summary, ending=ending,
                phase_instructions=phase_instructions,
                main_character_name=main_character_name,
                main_character_description=user_main_character_description,
                main_character_superpower=main_character_superpower,  # Add superpower here
                tone=tone  # Add tone here
            )

            response = get_story_response_from_model(model_name, user_message)
            if response:
                next_line = response.strip()

                # Check for duplicates using cosine similarity with the last 3 entries
                is_duplicate = False
                for previous_line in current_story[-3:]:
                    similarity_score = calculate_cosine_similarity(next_line, previous_line)
                    if similarity_score > COSINE_SIMILARITY_THRESHOLD:
                        is_duplicate = True
                        break

                if not is_duplicate:
                    current_story.append(next_line)
                    previous_summary = overall_summary
                    overall_summary = enhance_summary(overall_summary, next_line)

                    # Write the updated story and summary back to the JSON file after each API call
                    data["story_chapters"] = current_story
                    data["story_summary"] = overall_summary

                    with open(json_file, 'w') as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)

                    break
                else:
                    retry_count += 1
                    time.sleep(1)
            else:
                break

    complete_synopsis = generate_complete_synopsis(current_story, overall_summary)

    # Generate the main character description based on the complete synopsis and initial prompt
    with open(json_file, 'r') as f:
        data = json.load(f)
        initial_prompt = data["initial_prompt"]

    character_description = user_main_character_description if user_main_character_description else generate_main_character_description(model_name, complete_synopsis, initial_prompt, retries=3)

    # Determine the main character's gender
    main_character_gender = determine_main_character_gender(model_name, character_description, retries=3)

    # Generate the main character description based on the complete synopsis and initial prompt
    with open(json_file, 'r') as f:
        data = json.load(f)
        initial_prompt = data["initial_prompt"]

    character_description = user_main_character_description if user_main_character_description else generate_main_character_description(model_name, complete_synopsis, initial_prompt, retries=3)

    # Determine the main character's gender
    main_character_gender = determine_main_character_gender(model_name, character_description, retries=3)

    # Generate the movie title based on the overall summary and main character description
    movie_title = generate_movie_title(model_name, overall_summary, character_description)

    # Save all the final details to JSON
    with open(json_file, 'r') as f:
        data = json.load(f)
    data.update({
        "complete_synopsis": complete_synopsis,
        "main_character_description": character_description,
        "main_character_gender": main_character_gender,
        "movie_title": movie_title,
        "main_character_age": main_character_age,  # Add the age here
        "main_character_nationality": main_character_nationality,  # Add the nationality here
        "main_character_superpower": main_character_superpower,  # Add superpower to final details
        "tone": tone  # Add the tone here
    })

    with open(json_file, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return current_story

def main():
    global MODEL_NAME, LOOPS, JSON_FILE, USER_PROVIDED_TONE

    start_time = time.time()

    kill_existing_ollama_service()
    clear_gpu_memory()

    install_and_setup_ollama(MODEL_NAME)

    if is_windows():
        start_ollama_service_windows()
        time.sleep(10)

    # Pick the latest JSON file generated by initial script
    json_file = get_latest_json_file(output_dir)

    if not json_file:
        print("No JSON file found in the directory.")
        return

    with open(json_file, 'r') as f:
        data = json.load(f)
        initial_prompt = data["initial_prompt"]
        persona = data["author"]
        main_character = data["main_character"]  # Retrieve main character name
        main_character_superpower = data.get("main_character_superpower")

    tone = USER_PROVIDED_TONE if USER_PROVIDED_TONE else generate_tone_if_absent(MODEL_NAME, generate_summary([initial_prompt]))

    write_story_segment(MODEL_NAME, initial_prompt, persona, main_character, main_character_superpower, LOOPS, json_file, tone)

    stop_ollama_service()
    clear_gpu_memory()

    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"Total time taken: {elapsed_time:.2f} seconds")

if __name__ == "__main__":
    atexit.register(stop_ollama_service)
    atexit.register(clear_gpu_memory)
    main()