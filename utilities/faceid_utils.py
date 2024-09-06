import os
import requests
import cv2
import torch
from PIL import Image
from insightface.app import FaceAnalysis
from insightface.utils import face_align
import re
import numpy as np
import logging

# Initialize logging
logging.basicConfig(level=logging.DEBUG)

# Constants
GITHUB_REPO = "https://github.com/tencent-ailab/IP-Adapter"
REQUIRED_FILES = [
    "ip_adapter/__init__.py",
    "ip_adapter/attention_processor.py",
    "ip_adapter/attention_processor_faceid.py",
    "ip_adapter/custom_pipelines.py",
    "ip_adapter/ip_adapter.py",
    "ip_adapter/ip_adapter_faceid.py",
    "ip_adapter/ip_adapter_faceid_separate.py",
    "ip_adapter/resampler.py",
    "ip_adapter/test_resampler.py",
    "ip_adapter/utils.py"
]

# Download the required files from GitHub if they don't exist
def download_required_files():
    logging.info("[download_required_files] Checking for required files.")
    
    def download_file_from_github(repo_url, file_path, save_dir):
        file_url = f"{repo_url}/raw/main/{file_path}"
        local_path = os.path.join(save_dir, file_path.replace('/', os.sep))
        if not os.path.exists(local_path):
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            logging.info(f"[download_file_from_github] Downloading {file_path} from GitHub...")
            response = requests.get(file_url)
            if response.status_code == 200:
                with open(local_path, 'wb') as f:
                    f.write(response.content)
                logging.info(f"[download_file_from_github] Downloaded {file_path} to {local_path}")
            else:
                logging.error(f"[download_file_from_github] Error downloading {file_path}: {response.status_code}")
                raise Exception(f"Error downloading {file_path}: {response.status_code}")
        else:
            logging.info(f"[download_file_from_github] {file_path} already exists in {save_dir}. Skipping download.")
        return local_path

    # Ensure directories exist
    os.makedirs("ip_adapter", exist_ok=True)

    # Download required files from GitHub if they're missing
    for file in REQUIRED_FILES:
        download_file_from_github(GITHUB_REPO, file, ".")
    
    logging.info("[download_required_files] All required files have been downloaded or are already present.")

def add_padding(image, padding_factor=0.25):
    logging.info(f"[add_padding] Adding padding to the image with factor: {padding_factor}")
    width, height = image.size
    new_width = int(width * (1 + padding_factor))
    new_height = int(height * (1 + padding_factor))
    new_image = Image.new("RGB", (new_width, new_height), (255, 255, 255))
    new_image.paste(image, ((new_width - width) // 2, (new_height - height) // 2))
    logging.debug(f"[add_padding] Padding added. New dimensions: {new_width}x{new_height}")
    return new_image

def extract_face_embedding(image_path):
    logging.info(f"[extract_face_embedding] Extracting face embedding from {image_path}")
    
    app = FaceAnalysis(name="buffalo_l", providers=['CUDAExecutionProvider', 'CPUExecutionProvider'])
    app.prepare(ctx_id=0, det_size=(640, 640))
    logging.debug("[extract_face_embedding] FaceAnalysis app prepared.")

    for attempt in range(2):  # Try up to two times
        logging.debug(f"[extract_face_embedding] Attempt {attempt + 1} to extract face embedding.")
        
        try:
            image = cv2.imread(image_path)
            faces = app.get(image)
        except Exception as e:
            logging.error(f"[extract_face_embedding] Error during face extraction: {e}")
            return None, None
        
        if faces:
            logging.debug("[extract_face_embedding] Face detected.")
            face_embedding = torch.from_numpy(faces[0].normed_embedding).unsqueeze(0)
            aligned_face = face_align.norm_crop(image, landmark=faces[0].kps)
            return face_embedding, aligned_face

        if attempt == 0:
            logging.warning(f"[extract_face_embedding] No faces detected in {image_path}. Trying with padding.")
            pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
            padded_image = add_padding(pil_image)
            padded_image_cv = cv2.cvtColor(np.array(padded_image), cv2.COLOR_RGB2BGR)
            padded_image_path = os.path.join(os.path.dirname(image_path), f"padded_{os.path.basename(image_path)}")
            cv2.imwrite(padded_image_path, padded_image_cv)  # Save the padded image as a new file
            image_path = padded_image_path  # Update the image path to the padded image

    logging.error(f"[extract_face_embedding] No faces detected in {image_path} after padding.")
    return None, None

def sanitize_filename(filename):
    logging.debug(f"[sanitize_filename] Sanitizing filename: {filename}")
    sanitized = re.sub(r'[^\w\-_\. ]', '_', filename)
    logging.debug(f"[sanitize_filename] Sanitized filename: {sanitized}")
    return sanitized