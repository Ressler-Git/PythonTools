import importlib
import tkinter as tk
from tkinter import ttk

try:
    from tkinterdnd2 import TkinterDnD
except ImportError:
    TkinterDnD = None


TOOL_REGISTRY = [
    ("MD5", "tools.md5_tool"),
    ("SHA-256", "tools.hash_tool"),
    ("Base64", "tools.base64_tool"),
    ("Unlock", "tools.handle_tool"),
]


class ToolApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Python Tools")
        self.root.geometry("800x600")
        self.root.minsize(640, 480)

        # Escape closes the window cleanly.
        self.root.bind("<Escape>", lambda _event: self.root.destroy())

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self.load_tools()

    def load_tools(self):
        """Load each tool independently so one broken tool does not kill the app."""
        for title, module_name in TOOL_REGISTRY:
            try:
                module = importlib.import_module(module_name)
                frame = module.create_frame(self.notebook)
            except Exception as exc:
                frame = self._create_error_frame(title, module_name, exc)
            self.notebook.add(frame, text=title)

    def _create_error_frame(self, title, module_name, exc):
        frame = ttk.Frame(self.notebook, padding=20)
        message = (
            f"Failed to load {title}.\n\n"
            f"Module: {module_name}\n"
            f"{type(exc).__name__}: {exc}"
        )
        ttk.Label(frame, text=message, justify="left", wraplength=700).pack(anchor="w")
        return frame


if __name__ == "__main__":
    root = TkinterDnD.Tk() if TkinterDnD is not None else tk.Tk()
    ToolApp(root)
    root.mainloop()
