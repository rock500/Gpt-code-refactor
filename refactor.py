import asyncio
import aiofiles
import openai
import time
from pathlib import Path
from utils import log
from celebration import refactoring_completed_callback
import os


def split_code_into_chunks(code, max_tokens=1500):
    """
    Split code into smaller chunks by functions or classes to fit within the token limit.
    :param code: The original Python code as a string.
    :param max_tokens: Maximum number of tokens per chunk.
    :return: A list of code chunks.
    """
    chunks = []
    current_chunk = []
    token_count = 0

    # Split code by lines
    for line in code.splitlines():
        token_count += len(line.split())  # Rough approximation of tokens
        if token_count > max_tokens:
            # Add the current chunk and reset
            chunks.append("\n".join(current_chunk))
            current_chunk = []
            token_count = len(line.split())  # Start with the new line's token count
        current_chunk.append(line)

    # Add any remaining chunk
    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks


class RefactorHandler:
    def __init__(self, app):
        self.app = app
        self.api_key = app.api_key.get()
        self.is_running = True
        self.output_mode = app.output_mode.get()

    def set_openai_api_key(self):
        """Set the OpenAI API key globally before making requests"""
        if self.api_key:
            openai.api_key = self.api_key
            log("OpenAI API key set.")
        else:
            log("OpenAI API key is missing. Please enter a valid key.")

    async def run_refactoring(self, input_path, ignored_folders=[]):
        """Run the refactoring process on a folder or a single file"""
        self.set_openai_api_key()

        # Convert ignored folders to paths for better handling
        ignored_paths = [Path(folder).resolve() for folder in ignored_folders]

        if Path(input_path).is_file():
            # Single file refactoring
            await self.refactor_file(Path(input_path))
        else:
            # Count all the Python files to initialize the total progress bar
            total_python_files = self.count_python_files(input_path, ignored_paths)
            self.app.total_progress_var.set(0)  # Reset total progress

            # Directory refactoring with recursive traversal, ignoring specified folders/files
            await self.refactor_directory(Path(input_path), ignored_paths, total_python_files)

        self.trigger_celebration()

    def count_python_files(self, directory, ignored_paths):
        """Count total Python files recursively for progress tracking."""
        file_count = 0
        for root, dirs, files in os.walk(directory):
            root_path = Path(root).resolve()

            if any(ignored_path in root_path.parents or root_path == ignored_path for ignored_path in ignored_paths):
                continue

            file_count += sum(1 for file in files if file.endswith('.py'))
        return file_count

    async def refactor_directory(self, directory, ignored_paths, total_python_files):
        """Recursively refactor all Python files in a directory, ignoring specified paths."""
        processed_files = 0

        for root, dirs, files in os.walk(directory):
            root_path = Path(root).resolve()

            if any(ignored_path in root_path.parents or root_path == ignored_path for ignored_path in ignored_paths):
                log(f"Skipping ignored folder: {root_path}")
                continue

            python_files = [Path(root) / file for file in files if file.endswith('.py')]
            total_files_in_folder = len(python_files)

            if total_files_in_folder == 0:
                continue

            # Reset folder progress bar
            self.app.folder_progress_var.set(0)

            for idx, file_path in enumerate(python_files, start=1):
                await self.refactor_file(file_path, idx, total_files_in_folder)

                processed_files += 1
                overall_progress = int((processed_files / total_python_files) * 100)
                self.app.total_progress_var.set(overall_progress)

    async def refactor_file(self, file_path, idx=None, total_files=None):
        """
        Refactor a single Python file, splitting it into chunks if needed.
        :param file_path: Path to the Python file to be refactored.
        :param idx: Index of the current file for progress tracking.
        :param total_files: Total number of files to process.
        """
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                code = await f.read()

            # Split code into smaller chunks if necessary
            code_chunks = split_code_into_chunks(code)

            refactored_chunks = []
            for chunk in code_chunks:
                refactored_chunk = await self.gpt_refactor_code_with_retry(chunk)
                if refactored_chunk:
                    # Remove backtick formatting from the response
                    refactored_chunk = refactored_chunk.replace("```python", "").replace("```", "").strip()
                    refactored_chunks.append(refactored_chunk)
                else:
                    log(f"Failed to refactor chunk in {file_path}")
            
            # Recombine the refactored chunks
            refactored_code = "\n".join(refactored_chunks)

            # Determine the output path
            if self.output_mode == "file":
                output_file_path = Path(self.app.output_dir.get())
            else:
                output_file_path = Path(self.app.output_dir.get()) / file_path.relative_to(self.app.input_dir.get())
                output_file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write the refactored code back to the file
            async with aiofiles.open(output_file_path, 'w', encoding='utf-8') as f:
                await f.write(refactored_code)

            # Update folder-specific progress bar
            if total_files:
                folder_progress = int((idx / total_files) * 100)
                self.app.folder_progress_var.set(folder_progress)

            log(f"Processed {file_path}")
        except Exception as e:
            log(f"Error processing {file_path}: {e}")

    def trigger_celebration(self):
        """Trigger a celebration after refactoring is complete"""
        refactoring_completed_callback(self.app.root)

    async def gpt_refactor_code_with_retry(self, code, retries=3, delay=2):
        """
        Send the code to GPT-4 mini and get the refactored code with retry logic.
        :param code: The code to be refactored.
        :param retries: Number of retry attempts in case of failure.
        :param delay: Delay between retries.
        :return: Refactored code.
        """
        if not openai.api_key:
            log("OpenAI API key is not set. Aborting API call.")
            return None

        for attempt in range(retries):
            try:
                prompt = (
                    "You are an expert Python programmer. Refactor the following Python code while ensuring it adheres to the following instructions:"
                    "1. Maintain the full functionality of the code."
                    "2. Improve the code's efficiency, ensuring it follows PEP 8 standards."
                    "3. Do **not** remove or replace any non-empty class or function bodies with 'pass'. Ensure that all classes and functions contain meaningful, functional code."
                    "4. Preserve all existing docstrings. Add missing docstrings where necessary, and update them if needed to reflect the current behavior of the code."
                    "5. Refactor the entire code file, identifying areas where optimizations can be made."
                    "6. Implement optimizations based on your findings, ensuring that no errors are introduced during the refactoring process."
                    "7. Proofread the code for potential errors or issues that might arise after refactoring."
                    "8. Lastly, ensure the code is clean, readable, and aesthetically pleasing according to Python best practices."

                    "Additionally, if the code is lengthy or exceeds token limits, split it into smaller chunks, process those chunks individually, and recombine them after refactoring."

                    "Provide only the refactored code, without any comments or explanations unless they are part of docstrings."
                )
                response = await openai.ChatCompletion.acreate(
                    model="gpt-4o-mini",  # Use GPT-4o mini
                    messages=[
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": code}
                    ],
                    max_tokens=1500  # Set a lower token limit if needed
                )
                return response['choices'][0]['message']['content'].strip()  # Extract the refactored code
            except Exception as e:
                log(f"OpenAI API error (attempt {attempt+1}/{retries}): {e}")
                if attempt < retries - 1:
                    time.sleep(delay ** (attempt + 1))  # Exponential backoff
        return None
