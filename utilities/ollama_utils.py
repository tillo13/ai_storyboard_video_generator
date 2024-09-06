import os
import subprocess
import shutil
import platform
import psutil
import requests
import time
import socket

OLLAMA_EXE_PATH = os.path.join(os.getcwd(), "ollama.exe")
OLLAMA_RUNNERS_DIR = os.path.join(os.getcwd(), "ollama", "ollama_runners")
OLLAMA_TEMP_DIR = os.path.join(os.getcwd(), "ollama_temp")
OLLAMA_ZIP_PATH = os.path.join(os.getcwd(), "ollama-windows.zip")
OLLAMA_PROCESS = None
OLLAMA_PORT = 11434  # Define the port used by Ollama

DEFAULT_MODELS_DIR = os.path.join(os.path.expanduser("~"), ".ollama", "models")

def is_windows():
    """Check if the current OS is Windows."""
    return platform.system() == "Windows"

def is_ollama_installed(ollama_path):
    """Check if the Ollama executable is available."""
    return os.path.isfile(ollama_path)

def is_model_downloaded(model_name, model_dir=DEFAULT_MODELS_DIR):
    """Check if the specified model is already downloaded."""
    model_path = os.path.join(model_dir, model_name)
    if os.path.isdir(model_path) and os.listdir(model_path):
        print(f"Model directory for {model_name} found: {model_path}")
        return True
    print(f"Model directory for {model_name} not found or empty: {model_path}")
    return False

def download_file(url, local_path):
    """Download a file from a URL to a local path."""
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(local_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    return local_path

def install_ollama_windows():
    """Install the Ollama software on Windows."""
    print("Ollama not found. Installing now...")

    url = "https://ollama.com/download/ollama-windows-amd64.zip"
    download_file(url, OLLAMA_ZIP_PATH)
    shutil.unpack_archive(OLLAMA_ZIP_PATH, OLLAMA_TEMP_DIR)

    final_path = shutil.move(os.path.join(OLLAMA_TEMP_DIR, "ollama.exe"), OLLAMA_EXE_PATH)
    
    runners_src_dir = os.path.join(OLLAMA_TEMP_DIR, "ollama_runners")
    shutil.move(runners_src_dir, OLLAMA_RUNNERS_DIR)
    
    shutil.rmtree(OLLAMA_TEMP_DIR)
    os.remove(OLLAMA_ZIP_PATH)
    print("Ollama installed successfully.")
    return final_path

def pull_model(model_name):
    """Pull the specified model using the Ollama pull command."""
    print(f"Pulling model '{model_name}'... This may take a while.")
    
    # Ensure the environment variable is set
    os.environ['OLLAMA_RUNNERS_DIR'] = OLLAMA_RUNNERS_DIR
    
    try:
        subprocess.run([OLLAMA_EXE_PATH, 'pull', model_name], check=True)
        print(f"Model '{model_name}' pulled successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to pull model '{model_name}': {e}")
        raise

def install_ollama_pkg():
    """Install the ollama Python package."""
    try:
        import ollama
    except ImportError:
        subprocess.check_call(['pip', "install", "ollama"])

def kill_existing_ollama_service():
    """Kill any existing Ollama service instances to free up the port."""
    for process in psutil.process_iter(['pid', 'name', 'username']):
        try:
            if process.info['name'] == 'ollama.exe' and process.info['username'] == os.getlogin():
                process.terminate()
                process.wait(timeout=5)
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            print(f"Skipping process {process.info['name']} (PID: {process.info['pid']}): {e}")

    # Ensure there are no remaining processes
    for process in psutil.process_iter(['pid', 'name', 'username']):
        try:
            if "ollama" in process.info['name'].lower() and process.info['username'] == os.getlogin():
                process.terminate()
                process.wait(timeout=5)
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            print(f"Skipping process {process.info['name']} (PID: {process.info['pid']}): {e}")

def clear_gpu_memory():
    """Clear the GPU memory by killing processes using GPU."""
    try:
        result = subprocess.run(["nvidia-smi", "--query-compute-apps=pid", "--format=csv,noheader"], capture_output=True, text=True, check=True)
        pids = result.stdout.strip().split("\n")
        for pid in pids:
            if pid:
                try:
                    proc = psutil.Process(int(pid))
                    if proc.username() == os.getlogin():
                        proc.terminate()
                        proc.wait(timeout=5)
                except (psutil.NoSuchProcess, psutil.AccessDenied, PermissionError) as e:
                    print(f"Skipping PID {pid}: {e}")

        # Additional checks to ensure processes are terminated
        remaining_pids = [pid for pid in pids if psutil.pid_exists(int(pid))]
        for pid in remaining_pids:
            try:
                proc = psutil.Process(int(pid))
                proc.kill()  # Force kill if terminate didn't work
            except (psutil.NoSuchProcess, psutil.AccessDenied, PermissionError) as e:
                print(f"Skipping PID {pid}: {e}")

        print("GPU memory cleared.")
    except Exception as e:
        print(f"Failed to clear GPU memory: {e}")

def is_port_in_use(port):
    """Check if the specified port is in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def start_ollama_service_windows():
    """Start Ollama service on Windows."""
    global OLLAMA_PROCESS
    print("Starting Ollama service...")

    retries = 3
    while retries > 0:
        if is_port_in_use(OLLAMA_PORT):
            print(f"Port {OLLAMA_PORT} is already in use. Assuming Ollama service is running.")
            return True  # Treat it as success if the port is already in use

        os.environ['OLLAMA_RUNNERS_DIR'] = OLLAMA_RUNNERS_DIR
        OLLAMA_PROCESS = subprocess.Popen([OLLAMA_EXE_PATH, "serve"], env=os.environ)

        # Wait and check if the service starts properly
        time.sleep(10)
        if is_port_in_use(OLLAMA_PORT):
            print("Ollama service started successfully.")
            return True
        
        retries -= 1
        print("Retrying Ollama service start...")

    print("Failed to start Ollama service. Please check and try again.")
    return False

def stop_ollama_service():
    """Stop Ollama service if it was started by this script."""
    global OLLAMA_PROCESS
    if OLLAMA_PROCESS is not None:
        OLLAMA_PROCESS.terminate()
        OLLAMA_PROCESS.wait()
        OLLAMA_PROCESS = None
        print("Ollama service has been stopped.")

def install_and_setup_ollama(model_name):
    """Install and set up Ollama, including pulling the required model."""
    if not is_ollama_installed(OLLAMA_EXE_PATH):
        if is_windows():
            install_ollama_windows()
        else:
            raise NotImplementedError("Install logic for non-Windows platforms is not implemented.")
    
    install_ollama_pkg()

    # Start the Ollama service before pulling the model
    if is_windows():
        kill_existing_ollama_service()  # Ensure no leftover processes are running

        if not start_ollama_service_windows():
            print("Error: Failed to start Ollama service. Exiting.")
            return

    # Check if model is already downloaded, if not then pull the model
    if is_model_downloaded(model_name, DEFAULT_MODELS_DIR):
        print(f"Model '{model_name}' is already downloaded in {DEFAULT_MODELS_DIR}.")
    else:
        try:
            print(f"Attempting to pull the model '{model_name}'...")
            pull_model(model_name)
        except subprocess.CalledProcessError as e:
            print(f"Error occurred while pulling the model: {e}")
            raise
        except Exception as e:
            print(f"Unexpected error occurred: {e}")
            raise

def get_story_response_from_model(model_name, user_message):
    """Get response content from the model specifically for story writing."""
    user_messages = [{'role': 'user', 'content': user_message}]
    import ollama
    try:
        responses = ollama.chat(model=model_name, messages=user_messages, stream=True)
        return ''.join(chunk['message']['content'] for chunk in responses if 'message' in chunk and 'content' in chunk['message'])
    except Exception as e:
        print(f"An error occurred while retrieving the model's response: {e}")
        return None