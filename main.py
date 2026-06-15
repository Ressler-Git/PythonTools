import tkinter as tk
from tkinter import ttk
from tkinterdnd2 import TkinterDnD
import tools.md5_tool
import tools.base64_tool

class ToolApp:
    def __init__(self, root):
        # Configure application window
        self.root = root
        self.root.title("Python Tools")
        self.root.geometry("800x600")

        # Bind Escape key for immediate exit
        self.root.bind('<Escape>', lambda e: self.root.quit())

        # Utilize Notebook for modular tabs
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)

        # Register tools with concise titles
        self.add_tool("MD5", tools.md5_tool.create_frame(self.notebook))
        self.add_tool("Base64", tools.base64_tool.create_frame(self.notebook))

    def add_tool(self, title, frame):
        self.notebook.add(frame, text=title)

if __name__ == "__main__":
    # Initialize main loop with drag and drop support
    root = TkinterDnD.Tk()
    app = ToolApp(root)
    root.mainloop()