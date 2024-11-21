import queue

# Initialize logging queue
log_queue = queue.Queue()

def save_api_key(api_key, file_path):
    """Save the API key to a file"""
    try:
        with open(file_path, 'w') as file:
            file.write(api_key)
    except IOError as e:
        log(f"Error saving API key: {e}")

def load_api_key(file_path):
    """Load the API key from a file"""
    try:
        with open(file_path, 'r') as file:
            return file.read().strip()
    except FileNotFoundError:
        return ""

def log(message):
    """Thread-safe logging function"""
    log_queue.put(message)
