import tkinter as tk
from tkinter import messagebox
import random
import winsound  # Only for Windows
import platform

class CelebrationPopup(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("🎉 Congratulations! 🎉")
        self.geometry("300x200")
        self.configure(bg='yellow')

        label = tk.Label(self, text="Refactoring Completed!", font=("Arial", 14), bg='yellow')
        label.pack(pady=20)

        # Confetti animation simulation
        self.confetti_frame = tk.Canvas(self, width=300, height=100, bg='yellow')
        self.confetti_frame.pack(pady=10)
        self.confetti_items = []
        self.create_confetti()

        self.animate_confetti()

        # Close the celebration window after a few seconds
        self.after(4000, self.destroy)

    def create_confetti(self):
        colors = ['red', 'green', 'blue', 'orange', 'purple', 'pink']
        for _ in range(50):
            x = random.randint(0, 300)
            y = random.randint(0, 100)
            confetti_item = self.confetti_frame.create_oval(x, y, x+5, y+5, fill=random.choice(colors))
            self.confetti_items.append(confetti_item)

    def animate_confetti(self):
        for item in self.confetti_items:
            self.confetti_frame.move(item, 0, 5)
        self.after(100, self.animate_confetti)

def play_victory_sound():
    # Plays a victory sound using winsound, works on Windows
    if platform.system() == 'Windows':
        try:
            winsound.Beep(1000, 500)  # Simple beep for 500ms
        except:
            pass  # Beep only works on Windows, we can ignore if unavailable

def show_celebration_popup(root):
    # Show a popup with celebration
    popup = CelebrationPopup(root)
    play_victory_sound()

def refactoring_completed_callback(root):
    # Call this when the refactoring process is finished
    show_celebration_popup(root)
