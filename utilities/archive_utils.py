import os
import shutil
import platform
from datetime import datetime

# Whitelist of directories that should never be deleted
WHITELIST_HUB_DIRECTORIES = [
    'models--h94--IP-Adapter-FaceID',
    'models--stabilityai--sd-vae-ft-mse',
    'models--laion--CLIP-ViT-H-14-laion2B-s32B-b79K'
]

def bytes_to_gb(bytes_val):
    """
    Convert bytes to gigabytes (GB) with 2 decimal precision.
    """
    return round(bytes_val / (1024 ** 3), 2)

def get_free_disk_space():
    """
    Get the free disk space in bytes.
    """
    if platform.system() == "Windows":
        _, _, free_bytes = shutil.disk_usage(os.path.expanduser("~"))
    else:
        st = os.statvfs(os.path.expanduser("~"))
        free_bytes = st.f_bavail * st.f_frsize
    return free_bytes

def delete_oldest_models_from_cache(num_models=3):
    """
    Delete the oldest `num_models` models in the cache directory,
    excluding those in the whitelist.
    """
    cache_base_path = os.path.join(os.path.expanduser('~'), '.cache', 'huggingface', 'hub')
    if os.path.exists(cache_base_path):
        try:
            # Get list of all model directories and their last modified times
            model_paths = [
                (os.path.join(cache_base_path, d), os.path.getmtime(os.path.join(cache_base_path, d)))
                for d in os.listdir(cache_base_path)
                if os.path.isdir(os.path.join(cache_base_path, d)) and d not in WHITELIST_HUB_DIRECTORIES
            ]
            # Sort by last modified time (ascending order)
            model_paths.sort(key=lambda x: x[1])

            # Delete the oldest `num_models` directories
            for i in range(min(num_models, len(model_paths))):
                print(f"Deleting model directory: {model_paths[i][0]}")
                shutil.rmtree(model_paths[i][0], ignore_errors=True)
        except Exception as cache_error:
            print(f"Error deleting old models: {cache_error}")

def clear_cache_if_disk_space_low(min_free_space_bytes):
    """
    Delete the 3 oldest models in the cache if the free disk space is lower than min_free_space_bytes.
    """
    free_space_before = get_free_disk_space()
    print(f"Free disk space before clearing: {bytes_to_gb(free_space_before)} GB.")
    
    if free_space_before < min_free_space_bytes:
        print(f"Free disk space ({bytes_to_gb(free_space_before)} GB) is lower than the limit ({bytes_to_gb(min_free_space_bytes)} GB). Deleting oldest models.")
        delete_oldest_models_from_cache(3)
        free_space_after = get_free_disk_space()
        print(f"Free disk space after deleting models: {bytes_to_gb(free_space_after)} GB.")
        freed_space = free_space_after - free_space_before
        print(f"Total space freed up: {bytes_to_gb(freed_space)} GB.")
    else:
        print(f"Free disk space ({bytes_to_gb(free_space_before)} GB) is within the limit ({bytes_to_gb(min_free_space_bytes)} GB). No action needed.")

def archive_previous_generations():
    """
    Archive various folders containing previous generations.
    """
    script_directory = os.path.dirname(os.path.abspath(__file__))
    base_directory = os.path.abspath(os.path.join(script_directory, os.pardir))

    folders_to_move = [
        'created_videos',
        'enhanced_images',
        'generated_images',
        'subtitled_images',
        'storylines',
        'temp_group_images',
        'temp_tts_creation',
        'comparisons',
        'temp_ffmpeg',
        'final_voiceover_video',
        'frames'
    ]
    destination_directory = 'archive'

    destination_directory_full_path = os.path.join(base_directory, destination_directory)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    archive_folder_name = f"{timestamp}_archive"
    archive_folder_path = os.path.join(destination_directory_full_path, archive_folder_name)

    folders_moved = False

    for folder in folders_to_move:
        folder_full_path = os.path.join(base_directory, folder)
        if os.path.exists(folder_full_path):
            try:
                if not os.path.exists(archive_folder_path):
                    os.makedirs(archive_folder_path)
                shutil.move(folder_full_path, os.path.join(archive_folder_path, folder))
                print(f"Moved {folder} to {archive_folder_path}")
                folders_moved = True
            except Exception as e:
                print(f"Failed to move {folder}. Reason: {e}")
        else:
            print(f"Folder {folder} does not exist.")

    if not folders_moved:
        print("No folders were moved. No archive folder was created.")
    else:
        print("Archiving process completed.")

if __name__ == '__main__':
    archive_previous_generations()