import os
import cv2
import requests
from PIL import Image, ImageEnhance, ExifTags
import numpy as np
import shutil
from datetime import datetime
from mtcnn import MTCNN
import dlib
import psutil

# Global enhancement settings for regular faces
TARGET_SIZE = 2048
DENOISE_STRENGTH = (3, 3, 7, 21)
SHARPEN_AMOUNT = 0.5
SHARPEN_SIGMA = 1.0
SHARPEN_KERNEL_SIZE = (5, 5)
SHARPNESS_ENHANCE = 1.01
CONTRAST_ENHANCE = 1.05
COLOR_ENHANCE = 1.05

# Global enhancement settings for regular Ghibli style
GHIBLI_DENOISE_STRENGTH = (3, 3, 7, 21)  # You can adjust these based on specific needs
GHIBLI_SHARPEN_AMOUNT = 0.3
GHIBLI_SHARPEN_SIGMA = 1.0
GHIBLI_SHARPEN_KERNEL_SIZE = (3, 3)
GHIBLI_SHARPNESS_ENHANCE = 1.05
GHIBLI_CONTRAST_ENHANCE = 1.1
GHIBLI_COLOR_ENHANCE = 1.1

# Add Comparisons: Turn on/off image comparison functionality
ADD_COMPARISONS = False  # Set to False to turn off comparison images
print(f"ADD_COMPARISONS is set to: {ADD_COMPARISONS}")

def memory_available():
    return psutil.virtual_memory().available

def download_file(url, local_path):
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(local_path, 'wb') as file:
            shutil.copyfileobj(response.raw, file)
        print(f'Downloaded {local_path}')
    else:
        print(f'Failed to download {url}')

def denoise_image(img_cv):
    h, hForColorComponents, templateWindowSize, searchWindowSize = DENOISE_STRENGTH
    return cv2.fastNlMeansDenoisingColored(img_cv, None, h, hForColorComponents, templateWindowSize, searchWindowSize)

def unsharp_mask(img_cv, kernel_size=SHARPEN_KERNEL_SIZE, sigma=SHARPEN_SIGMA, amount=SHARPEN_AMOUNT, threshold=0):
    blurred = cv2.GaussianBlur(img_cv, kernel_size, sigma)
    sharpened = float(amount + 1) * img_cv - float(amount) * blurred
    sharpened = np.maximum(sharpened, 0)
    sharpened = np.minimum(sharpened, 255)
    sharpened = sharpened.round().astype(np.uint8)
    if threshold > 0:
        low_contrast_mask = np.absolute(img_cv - blurred) < threshold
        np.copyto(sharpened, img_cv, where=low_contrast_mask)
    return sharpened

def safe_save(filepath, img):
    """Save the image ensuring no overwrites and correct extensions."""
    accepted_extensions = ['.png', '.jpg', '.jpeg']
    base, ext = os.path.splitext(filepath)
    if ext.lower() not in accepted_extensions:
        filepath = base + '.png'  # Default to PNG if unknown extension

    if os.path.exists(filepath):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        new_base = f"{timestamp}_{os.path.basename(base)}"
        filepath = os.path.join(os.path.dirname(base), new_base + ext)

    img.save(filepath)
    print(f'Saved: {filepath}')

def enhance_image(input_image_path, output_dir):
    face_predictor_path = 'shape_predictor_68_face_landmarks.dat'
    
    if not os.path.exists(face_predictor_path):
        download_url = "https://github.com/italojs/facial-landmarks-recognition/raw/master/shape_predictor_68_face_landmarks.dat"
        print(f"{face_predictor_path} not found. Downloading from {download_url}...")
        download_file(download_url, face_predictor_path)
    
    landmark_predictor = dlib.shape_predictor(face_predictor_path)
    face_detector = MTCNN()

    try:
        print(f'Opening image: {input_image_path}')
        base_name = os.path.splitext(os.path.basename(input_image_path))[0]
        with Image.open(input_image_path) as img:
            try:
                print('Checking for EXIF orientation data...')
                for orientation in ExifTags.TAGS.keys():
                    if ExifTags.TAGS[orientation] == 'Orientation':
                        break
                exif = img._getexif()
                if exif is not None:
                    exif = dict(exif.items())
                    orientation_value = exif.get(orientation)
                    if orientation_value == 3:
                        print('Rotating image 180 degrees due to EXIF orientation...')
                        img = img.rotate(180, expand=True)
                    elif orientation_value == 6:
                        print('Rotating image 270 degrees due to EXIF orientation...')
                        img = img.rotate(270, expand=True)
                    elif orientation_value == 8:
                        print('Rotating image 90 degrees due to EXIF orientation...')
                        img = img.rotate(90, expand=True)
            except (AttributeError, KeyError, IndexError):
                print('No EXIF orientation data found or error reading EXIF data.')
                pass

            orig_size = img.size
            print(f'Original size: {orig_size} ({os.path.getsize(input_image_path) / (1024 * 1024):.2f} MB)')

            img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            print('Converted image to OpenCV (BGR) format.')

            print('Detecting faces using MTCNN...')
            faces = face_detector.detect_faces(cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB))
            print(f'Number of faces detected: {len(faces)}')

            for face in faces:
                x, y, w, h = face['box']
                face_img = img_cv[y:y+h, x:x+w]
                print(f'Processing face region: x={x}, y={y}, width={w}, height={h}')

                face_img = denoise_image(face_img)
                
                gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
                rect = dlib.rectangle(0, 0, face_img.shape[1], face_img.shape[0])
                landmarks = landmark_predictor(gray, rect)

                face_img = unsharp_mask(face_img)

                img_cv[y:y+h, x:x+w] = face_img

            img = Image.fromarray(cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB))
            print('Converted image back to PIL format.')

            img = ImageEnhance.Sharpness(img).enhance(SHARPNESS_ENHANCE)
            print('Applied general subtle sharpness enhancement.')
            img = ImageEnhance.Contrast(img).enhance(CONTRAST_ENHANCE)
            print('Applied general subtle contrast enhancement.')
            img = ImageEnhance.Color(img).enhance(COLOR_ENHANCE)
            print('Applied general subtle color enhancement.')

            if max(img.size) > TARGET_SIZE:
                scale_factor = TARGET_SIZE / max(img.size)
                new_dimensions = (int(img.size[0] * scale_factor), int(img.size[1] * scale_factor))
                img = img.resize(new_dimensions, Image.LANCZOS)
                print(f'Resized final image to ensure longest side is at most {TARGET_SIZE}: {img.size}')

            enhanced_image_name = f"{base_name}_enhanced.png"
            enhanced_image_path = os.path.join(output_dir, enhanced_image_name)
            safe_save(enhanced_image_path, img)

            if ADD_COMPARISONS:
                print("Creating comparison image...")
                comparison_dir = 'comparisons'
                os.makedirs(comparison_dir, exist_ok=True)
                with Image.open(input_image_path) as orig_img:
                    common_height = min(orig_img.height, img.height)
                    orig_img_resized = orig_img.resize((int(orig_img.width * common_height / orig_img.height), common_height), Image.LANCZOS)
                    processed_img_resized = img.resize((int(img.width * common_height / img.height), common_height), Image.LANCZOS)

                    comparison_img = Image.new('RGB', (orig_img_resized.width + processed_img_resized.width, common_height))
                    comparison_img.paste(orig_img_resized, (0, 0))
                    comparison_img.paste(processed_img_resized, (orig_img_resized.width, 0))

                    comparison_filepath = os.path.join(comparison_dir, f"{base_name}_comparison.png")
                    safe_save(comparison_filepath, comparison_img)
                    print(f"Comparison image saved at: {comparison_filepath}")

            print(f"Enhanced image saved at: {enhanced_image_path}")
            print("\nGlobal enhancement settings used:")
            print(f"TARGET_SIZE = {TARGET_SIZE}")
            print(f"DENOISE_STRENGTH = {DENOISE_STRENGTH}")
            print(f"SHARPEN_AMOUNT = {SHARPEN_AMOUNT}")
            print(f"SHARPEN_SIGMA = {SHARPEN_SIGMA}")
            print(f"SHARPEN_KERNEL_SIZE = {SHARPEN_KERNEL_SIZE}")
            print(f"SHARPNESS_ENHANCE = {SHARPNESS_ENHANCE}")
            print(f"CONTRAST_ENHANCE = {CONTRAST_ENHANCE}")
            print(f"COLOR_ENHANCE = {COLOR_ENHANCE}")
            print(f"ADD_COMPARISONS = {ADD_COMPARISONS}")

            return img

    except IOError as e:
        print(f"Error processing file {input_image_path}: {e}, skipping...")
        return None

if __name__ == '__main__':
    enhance_image('path/to/input_image.png', 'path/to/output_dir')