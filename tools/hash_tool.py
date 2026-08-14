import hashlib
import os
import tkinter as tk
from tkinter import ttk

try:
    from tkinterdnd2 import DND_FILES
except ImportError:
    DND_FILES = None


FILE_CHUNK_SIZE = 1024 * 1024  # 1 MiB


def create_frame(parent):
    """Default hash tab: SHA-256."""
    return create_hash_frame(parent, algorithm="sha256", display_name="SHA-256")


def create_hash_frame(parent, algorithm, display_name):
    """Create a reusable text/file hashing UI for any hashlib algorithm."""
    if algorithm not in hashlib.algorithms_available:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")

    frame = ttk.Frame(parent, padding=10)

    ttk.Label(frame, text="Input text or drop files here:").pack(anchor="w")
    input_text = tk.Text(frame, height=10, undo=True, wrap="word")
    input_text.pack(fill="both", expand=True, pady=(5, 10))

    ttk.Label(frame, text=f"{display_name} result:").pack(anchor="w")
    output_text = tk.Text(frame, height=10, state="disabled", wrap="word")
    output_text.pack(fill="both", expand=True, pady=(5, 10))

    def set_output(text):
        output_text.configure(state="normal")
        output_text.delete("1.0", tk.END)
        output_text.insert("1.0", text)
        output_text.configure(state="disabled")

    def process_input(event=None):
        # Tk Text always has an implicit trailing newline; end-1c avoids hashing it.
        # Do not strip() here: spaces and line breaks can be meaningful hash input.
        data = input_text.get("1.0", "end-1c")
        if data == "":
            set_output("")
            return

        digest = hashlib.new(algorithm, data.encode("utf-8")).hexdigest()
        set_output(digest)

    def hash_file(filepath):
        digest = hashlib.new(algorithm)
        with open(filepath, "rb") as file_obj:
            for chunk in iter(lambda: file_obj.read(FILE_CHUNK_SIZE), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def handle_drop(event):
        paths = frame.tk.splitlist(event.data)
        results = []

        for filepath in paths:
            if not os.path.isfile(filepath):
                results.append(f"{os.path.basename(filepath) or filepath}:\nSkipped (not a file)")
                continue

            try:
                result = hash_file(filepath)
                results.append(f"{os.path.basename(filepath)}:\n{result}")
            except OSError as exc:
                results.append(
                    f"{os.path.basename(filepath)}:\n"
                    f"Error reading file: {exc}"
                )

        set_output("\n\n".join(results))

    def copy_output():
        text = output_text.get("1.0", "end-1c")
        if not text:
            return
        frame.clipboard_clear()
        frame.clipboard_append(text)

    def clear_all():
        input_text.delete("1.0", tk.END)
        set_output("")
        input_text.focus_set()

    # Real-time hashing for typed text.
    input_text.bind("<KeyRelease>", process_input)
    if DND_FILES is not None and hasattr(input_text, "drop_target_register"):
        input_text.drop_target_register(DND_FILES)
        input_text.dnd_bind("<<Drop>>", handle_drop)

    button_frame = ttk.Frame(frame)
    button_frame.pack(fill="x")
    ttk.Button(button_frame, text="Calculate", command=process_input).pack(side="left")
    ttk.Button(button_frame, text="Copy", command=copy_output).pack(side="left", padx=(8, 0))
    ttk.Button(button_frame, text="Clear", command=clear_all).pack(side="left", padx=(8, 0))

    return frame
