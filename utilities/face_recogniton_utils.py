import face_recognition
import sys

def find_face_coordinates(image_path):
    """
    Finds the coordinates of faces in the given image file.

    :param image_path: Path to the image file.
    :return: A list of tuples containing the coordinates of each face found.
    """
    # Load the image file
    image = face_recognition.load_image_file(image_path)

    # Find all face locations in the image
    face_locations = face_recognition.face_locations(image)

    return face_locations

def get_face_encodings(image_path):
    """
    Generates face encodings for each face detected in the image.

    :param image_path: Path to the image file.
    :return: A list of face encodings.
    """
    # Load the image file
    image = face_recognition.load_image_file(image_path)

    # Find face encodings in the image
    face_encodings = face_recognition.face_encodings(image)

    return face_encodings

def compare_faces(image_path_1, image_path_2):
    """
    Compares faces from two images and returns True if they match, False otherwise.

    :param image_path_1: Path to the first image file.
    :param image_path_2: Path to the second image file.
    :return: True if faces match, False otherwise.
    """
    # Generate face encodings for both images
    encodings_1 = get_face_encodings(image_path_1)
    encodings_2 = get_face_encodings(image_path_2)

    if not encodings_1 or not encodings_2:
        return False

    # Compare the first face found in both images
    match = face_recognition.compare_faces([encodings_1[0]], encodings_2[0])

    return match[0]

def detect_face_landmarks(image_path):
    """
    Detects facial landmarks in the given image.

    :param image_path: Path to the image file.
    :return: A list of dictionaries containing the facial landmarks for each face found.
    """
    # Load the image file
    image = face_recognition.load_image_file(image_path)

    # Find all face landmarks in the image
    face_landmarks_list = face_recognition.face_landmarks(image)

    return face_landmarks_list

def main():
    # Default image path
    image_path = "test.png"
    
    # Check if an image path is provided as an argument
    if len(sys.argv) > 1:
        image_path = sys.argv[1]

    # Find face coordinates
    face_locations = find_face_coordinates(image_path)

    # Print the coordinates of each face found
    for face_location in face_locations:
        top, right, bottom, left = face_location
        print(f"Face found at Top: {top}, Right: {right}, Bottom: {bottom}, Left: {left}")

if __name__ == "__main__":
    main()