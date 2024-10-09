# AI Storyboard Generator featuring Ollama, Stablediffusion, Kumori

## Table of Contents
1. [Introduction](#introduction)
2. [Features](#features)
3. [Quick Start Guide](#quick-start-guide)
4. [Detailed Setup and Installation](#detailed-setup-and-installation)
5. [Usage Instructions](#usage-instructions)
6. [File Structure Overview](#file-structure-overview)
7. [AI Models and Tools](#ai-models-and-tools)
8. [Customization Options](#customization-options)
9. [FAQ](#faq)
10. [Contributing](#contributing)
11. [License](#license)
12. [Acknowledgements](#acknowledgements)

## Introduction
Welcome to the Kumori Story Generator! This groundbreaking application leverages state-of-the-art generative AI technologies to automate the creation of rich multimedia stories, making storytelling more accessible and engaging for everyone.

Harnessing the power of advanced natural language processing (NLP) models like **Ollama** (powered by `llama3`) and cutting-edge image generation models such as **Stable Diffusion**, the Kumori Story Generator crafts engaging narratives and vivid visual content based on user inputs. The application integrates facial recognition and voice synthesis technologies to enhance character consistency and narrative immersion. Once the content is generated, it is dynamically compiled into videos with embedded voiceovers and visual effects, all ready for publication. With a highly automated workflow, users need to manage only the global variables to create neat and fun storylines entirely from scratch.

## Features
- **Comprehensive Storyline Generation**: Automatically create detailed storylines using advanced NLP models from **Ollama**.
- **High-Quality Image Generation**: Generate stunning visuals for story chapters using **Stable Diffusion**.
- **Character Consistency**: Maintain visual consistency of characters with facial recognition techniques from **MTCNN**, **Dlib**, and **FaceAnalysis**.
- **Automated Voiceovers**: Convert text into natural-sounding voiceovers using **Google Text-to-Speech (gTTS)**.
- **Dynamic Video Creation**: Compile story chapters into cohesive videos with dynamic effects using **FFMPEG**.
- **Subtitle Integration**: Embed subtitles to enhance video accessibility.
- **YouTube Integration**: Schedule and upload videos to YouTube using the **YouTube Data API**.
- **User-Friendly Customization**: Easily modify story parameters and configurations via global variables.

## Quick Start Guide
Follow this guide to get started with the Kumori Story Generator.

### Prerequisites
- Python 3.x
- pip for Python package installations
- A YouTube account for API credentials

### Installation
1. Clone the repository:
    ```bash
    git clone https://github.com/tillo13/ai_storyboard_video_generator.git
    cd ai_storyboard_video_generator
    ```
2. Create and activate a virtual environment:
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```
3. Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
4. Set up OAuth 2.0 credentials for YouTube API:
    - Create a project in the Google API Console.
    - Enable the YouTube Data API.
    - Create OAuth 2.0 client ID credentials and download the `client_secrets.json` file.
    - Place the `client_secrets.json` file in the project directory.

5. Run the initial setup script:
    ```bash
    python gather_pythons.py
    ```

## Detailed Setup and Installation

### Dependencies
The project leverages a variety of Python libraries and models:
- Ollama for advanced NLP: `ollama`
- Stable Diffusion for image generation: `diffusers`
- FFMPEG for video processing: `ffmpeg-python`
- Google Text-to-Speech (gTTS) for voice synthesis: `gtts`
- MTCNN/Dlib/FaceAnalysis for facial recognition: `mtcnn`, `dlib`, `insightface`

### Configuration
Edit the `GLOBAL_VARIABLES.py` file to adjust parameters:
- Set paths for user-provided images, story themes, default video length, etc.
- Configure AI models and adjust settings for image generation, voice creation, video synthesis, and more.

### Running the Application
1. **Create a Story**
    ```bash
    python 1_dream_up_a_story.py
    ```
    
2. **Build Out the Chapters**
    ```bash
    python 2_build_out_chapters.py
    ```
    
3. **Summarize Chapters and Add AI Prompts**
    ```bash
    python 3_summarize_chapters_add_ai_prompts.py
    ```
    
4. **Generate Images from AI Prompts**
    ```bash
    python 4_create_images_from_ai_prompts.py
    ```
    
5. **Generate Unique Character Images**
    ```bash
    python 4b_unique_character.py
    ```

6. **Create the Movie**
    ```bash
    python 5_create_movie.py
    ```
    
7. **Create a Mosaic**
    ```bash
    python 6_create_mosaic.py
    ```
    
8. **Add Zoom Pan Effects**
    ```bash
    python 7_zoompan_movie.py
    ```
    
9. **Add Subtitles**
    ```bash
    python 8_add_ffmpeg_subtitles.py
    ```
    
10. **Create Voiceover**
    ```bash
    python 9_create_voiceover.py
    ```
    
11. **Upload to YouTube** (Review and adjust CSV log before running)
    ```bash
    python 0_preview_mosaics_then_upload_to_youtube.py
    ```

## File Structure Overview
Here is an overview of the project's directory structure:
```
.
│
├── ollama/
│   ├── ollama_runners/
│   │   ├── cpu/
│   │   ├── cpu_avx/
│   │   ├── cpu_avx2/
│   │   ├── cuda_v11.3/
│   │   ├── rocm_v6.1/
│
├── user_images/         # Store user-provided images 
│
├── utilities/           # Utility scripts and modules
│   ├── youtube/
│   │   └── youtube_scheduler_utils.py
│   ├── archive_utils.py
│   ├── enhance_image_via_import.py
│   ├── faceid_utils.py
│   ├── face_recogniton_utils.py
│   ├── ffmpeg_utils.py
│   ├── google_tts_utils.py
│   ├── main_character_generator_utils.py
│   ├── mosaic_validator_utils.py
│   ├── ollama_utils.py
│   ├── rfm_music_utils.py
│   ├── stablediffusion_utils.py
│   ├── youtube_csv_prep_utils.py
│   ├── youtube_utils.py
│   └── __init__.py
│
├── ip_adapter/          # IP-Adapter models and utilities [excluded from files_within.txt]
│   └── __pycache__/     # Cached modules [excluded from files_within.txt]
│
├── README.md            # This file
│
├── requirements.txt     # Project dependencies
│
├── GLOBAL_VARIABLES.py  # Main configuration file
│
├── gather_pythons.py    # Gathers all project files
│
├── 0_preview_mosaics_then_upload_to_youtube.py # Review and upload mosaics to YouTube
├── 1_dream_up_a_story.py       # Initial story generation
├── 2_build_out_chapters.py     # Chapter creation
├── 3_summarize_chapters_add_ai_prompts.py    # Summarizing chapters with AI
├── 4_create_images_from_ai_prompts.py   # AI image generation
├── 4b_unique_character.py          # Unique character image generation
├── 5_create_movie.py         # Video creation from chapters
├── 6_create_mosaic.py        # Mosaics creation
├── 7_zoompan_movie.py        # Add zoom and pan effects
├── 8_add_ffmpeg_subtitles.py # Add subtitles to the video
├── 9_create_voiceover.py     # Voice over generation
```

## AI Models and Tools
The Kumori Story Generator harnesses several advanced AI models and tools:
- **Ollama** (powered by Llama3): Generates and refines story content.
- **Stable Diffusion**: Produces high-quality images for story chapters.
- **Face Recognition Libraries**: MTCNN, Dlib, and FaceAnalysis for maintaining character consistency.
- **gTTS**: Converts text stories into natural-sounding voiceovers.
- **FFMPEG**: Synthesizes videos with sophisticated visual effects.

## Customization Options
Customize your story generation experience by modifying the `GLOBAL_VARIABLES.py` file:
- Adjust story parameters such as character descriptions, story themes, and artistic styles.
- Configure AI model settings including guidance scales, negative prompts, and safety check settings.
- Set default paths for user-provided content and custom scripts.

## FAQ
**Q1: Can I use my custom images and background music?**
- A1: Absolutely! Specify your paths in `GLOBAL_VARIABLES.py` for custom images and YouTube music URLs.

**Q2: How do I change the language for the text-to-speech?**
- A2: Modify the `DEFAULT_LANGUAGE` and `DEFAULT_TLD` parameters in `google_tts_utils.py`.

**Q3: How can I adjust the duration of videos?**
- A3: Set the desired duration in `GLOBAL_VARIABLES.py` under `DEFAULT_VIDEO_LENGTH`.

**Q4: Can I schedule uploads to YouTube?**
- A4: Yes, the application integrates the YouTube Data API for automated scheduling and uploading.

## Contributing
We welcome contributions! If you'd like to contribute, please follow these guidelines:
1. Fork the repository.
2. Create a new branch for your feature (`git checkout -b feature/NewFeature`).
3. Commit your changes (`git commit -m 'Add new feature'`).
4. Push to the branch (`git push origin feature/NewFeature`).
5. Open a Pull Request.

## License
This project is licensed under the MIT License. See the `LICENSE` file for details.

## Acknowledgements
- Ollama and Stable Diffusion for providing powerful AI models.
- Google Cloud Platform for API access and resources.
- Contributors and community for continuous support and improvements.

## Examples
Check out some of the results created using this generator:
- [Video 1](https://www.youtube.com/shorts/mfCbNrOxq0w)
- [Video 2](https://www.youtube.com/shorts/eJ8T6cfxADg)
- [Video 3](https://www.youtube.com/shorts/DefdXzCGNOY)

Explore the full collection: [Kumori AI on YouTube](https://www.youtube.com/@kumoriai/shorts)

Feel free to try out the generator and create your own stories! For any questions or additional features, please reach out or open an issue on GitHub. Happy storytelling!
