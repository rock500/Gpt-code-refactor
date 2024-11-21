import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter.ttk import Progressbar, Style
import asyncio
from concurrent.futures import ThreadPoolExecutor
from refactor import RefactorHandler
from utils import save_api_key, load_api_key, log_queue
import os
import queue

class RefactorApp:
    def __init__(self, root):
        """Initialize the GUI and set up the layout"""
        self.root = root
        self.root.title("Python Refactor Tool")
        self.api_key_file = "api_key.txt"
        self.api_key = tk.StringVar(value=load_api_key(self.api_key_file))

        # Set a prettier style for the progress bar
        self.style = Style()
        self.style.configure("TProgressbar", thickness=20)

        # Set the overall background color
        root.configure(bg="#f0f0f5")

        # Add a frame to organize the layout
        frame = tk.Frame(root, bg="#f0f0f5")
        frame.pack(padx=10, pady=10)

        # API Key input
        self.create_label_entry(frame, "OpenAI API Key:", self.api_key, row=0)
        tk.Button(frame, text="Save API Key", command=self.save_api_key, bg="#87CEFA", fg="black", activebackground="#4682B4", bd=0, highlightthickness=0).grid(row=0, column=2, padx=5)

        # Input and output directory and file selection
        self.input_dir = tk.StringVar()
        self.output_dir = tk.StringVar()
        self.output_mode = tk.StringVar(value="folder")  # Either 'folder' or 'file'
        self.create_label_entry(frame, "Input Directory or File:", self.input_dir, row=1)
        tk.Button(frame, text="Browse Folder", command=self.select_input_directory, bg="#87CEFA", fg="black", activebackground="#4682B4", bd=0, highlightthickness=0).grid(row=1, column=2, padx=5)
        tk.Button(frame, text="Select File", command=self.select_single_file, bg="#87CEFA", fg="black", activebackground="#4682B4", bd=0, highlightthickness=0).grid(row=1, column=3, padx=5)

        self.create_label_entry(frame, "Output Directory:", self.output_dir, row=2)
        tk.Button(frame, text="Browse", command=self.select_output_directory, bg="#87CEFA", fg="black", activebackground="#4682B4", bd=0, highlightthickness=0).grid(row=2, column=2, padx=5)

        # Toggle between single output file or folder
        tk.Label(frame, text="Output Mode (folder/file):", font=("Arial", 10), bg="#f0f0f5").grid(row=3, column=0, sticky=tk.W)
        tk.Radiobutton(frame, text="Folder", variable=self.output_mode, value="folder", bg="#f0f0f5").grid(row=3, column=1)
        tk.Radiobutton(frame, text="Single File", variable=self.output_mode, value="file", bg="#f0f0f5").grid(row=3, column=2)

        # Checkbox to allow output folder creation
        self.create_output_folder = tk.BooleanVar(value=False)
        tk.Checkbutton(frame, text="Create Output Folder if it Doesn't Exist", variable=self.create_output_folder, bg="#f0f0f5").grid(row=4, column=0, columnspan=2, sticky=tk.W)

        # Ignored folders/files input
        self.ignored_folders = tk.StringVar()
        self.create_label_entry(frame, "Ignored Folders/Files (comma-separated):", self.ignored_folders, row=5)
        tk.Button(frame, text="Select Ignored Folders/Files", command=self.select_ignored_folders_files, bg="#87CEFA", fg="black", activebackground="#4682B4", bd=0, highlightthickness=0).grid(row=5, column=2, padx=5)

        # Buttons for actions
        self.start_button = tk.Button(frame, text="Start Refactoring", command=self.start_refactoring, bg="#32CD32", fg="white", activebackground="#228B22", bd=0, highlightthickness=0)
        self.start_button.grid(row=6, column=0, pady=10)

        self.stop_button = tk.Button(frame, text="Stop Refactoring", command=self.stop_refactoring, bg="#FFA500", fg="white", activebackground="#FF8C00", bd=0, highlightthickness=0)
        self.stop_button.grid(row=6, column=1, pady=10)

        self.quit_button = tk.Button(frame, text="Quit", command=self.on_closing, bg="#DC143C", fg="white", activebackground="#B22222", bd=0, highlightthickness=0)
        self.quit_button.grid(row=6, column=2, pady=10)

        # Progress bars
        tk.Label(frame, text="Overall Progress:", font=("Arial", 10), bg="#f0f0f5").grid(row=7, column=0, sticky=tk.W)
        self.total_progress_var = tk.IntVar()
        self.total_progress_bar = Progressbar(frame, variable=self.total_progress_var, maximum=100, style="TProgressbar")
        self.total_progress_bar.grid(row=7, column=1, columnspan=3, pady=5)

        tk.Label(frame, text="Folder Progress:", font=("Arial", 10), bg="#f0f0f5").grid(row=8, column=0, sticky=tk.W)
        self.folder_progress_var = tk.IntVar()
        self.folder_progress_bar = Progressbar(frame, variable=self.folder_progress_var, maximum=100, style="TProgressbar")
        self.folder_progress_bar.grid(row=8, column=1, columnspan=3, pady=5)

        # Log area for displaying progress
        self.log_area = tk.Text(root, height=10, state=tk.DISABLED, wrap="word", font=("Arial", 10), bg="#E6E6FA", fg="black")
        self.log_area.pack(fill=tk.BOTH, expand=True, pady=10)

        # Periodic log updates
        self.update_log_area()

        # Graceful shutdown on window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Initialize refactor handler and thread executor
        self.refactor_handler = RefactorHandler(self)
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.refactoring_task = None

    def create_label_entry(self, parent, label_text, variable, row):
        """Helper to create label-entry pairs for input fields"""
        tk.Label(parent, text=label_text, font=("Arial", 10), bg="#f0f0f5").grid(row=row, column=0, sticky=tk.W)
        tk.Entry(parent, textvariable=variable, width=50, bd=2, relief="flat").grid(row=row, column=1, pady=5)

    def log(self, message):
        """Thread-safe logging function"""
        log_queue.put(message)

    def update_log_area(self):
        """Periodically update the log area with queued log messages"""
        try:
            while not log_queue.empty():
                message = log_queue.get_nowait()
                self.log_area.config(state=tk.NORMAL)
                self.log_area.insert(tk.END, message + "\n")
                self.log_area.config(state=tk.DISABLED)
                self.log_area.yview(tk.END)
        except queue.Empty:
            pass
        self.root.after(100, self.update_log_area)

    def select_input_directory(self):
        """Select an input directory"""
        self.input_dir.set(filedialog.askdirectory())

    def select_single_file(self):
        """Select a single Python file for refactoring"""
        self.input_dir.set(filedialog.askopenfilename(filetypes=[("Python files", "*.py")]))

    def select_output_directory(self):
        """Select the output directory or file"""
        if self.output_mode.get() == "folder":
            self.output_dir.set(filedialog.askdirectory())
        else:
            self.output_dir.set(filedialog.asksaveasfilename(filetypes=[("Python files", "*.py")]))

    def select_ignored_folders_files(self):
        """Allow users to manually enter multiple folders and files to ignore"""
        folders = filedialog.askdirectory(title="Select a Folder to Ignore")
        if folders:
            existing = self.ignored_folders.get().split(",") if self.ignored_folders.get() else []
            existing.append(folders)
            self.ignored_folders.set(",".join(existing))

    def save_api_key(self):
        """Save the OpenAI API key to a file"""
        if not self.api_key.get():
            messagebox.showerror("Error", "API key cannot be empty!")
            return
        save_api_key(self.api_key.get(), self.api_key_file)
        messagebox.showinfo("Success", "API key saved successfully!")

    def start_refactoring(self):
        """Start the refactoring process in a separate thread"""
        if not self.api_key.get() or not self.input_dir.get() or not self.output_dir.get():
            messagebox.showerror("Error", "Please provide the API key and select both input/output directories.")
            return

        self.log("Starting refactoring process...")
        save_api_key(self.api_key.get(), self.api_key_file)  # Save API key

        # Create output directory if requested
        if self.create_output_folder.get() and not os.path.exists(self.output_dir.get()):
            os.makedirs(self.output_dir.get())

        # Convert ignored folders/files to a list
        ignored_folders_list = [folder.strip() for folder in self.ignored_folders.get().split(",")]

        # Reset the progress bars
        self.total_progress_var.set(0)
        self.folder_progress_var.set(0)

        # Start refactoring in a separate thread
        async def start_refactoring_task():
            await self.refactor_handler.run_refactoring(self.input_dir.get(), ignored_folders_list)

        self.refactoring_task = self.executor.submit(asyncio.run, start_refactoring_task())

    def stop_refactoring(self):
        """Stop the refactoring process"""
        if self.refactoring_task:
            self.refactoring_task.cancel()
            self.log("Refactoring process stopped.")

    def on_closing(self):
        """Handle graceful shutdown on window close"""
        if self.refactoring_task:
            self.refactoring_task.cancel()  # Stop the refactoring if running
        self.executor.shutdown(wait=False)
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = RefactorApp(root)
    root.mainloop()
