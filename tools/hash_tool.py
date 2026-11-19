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

    header_frame = ttk.Frame(frame)
    header_frame.pack(fill="x", pady=(0, 2))
    ttk.Label(header_frame, text=f"{display_name} result:").pack(side="left")
    compare_label = ttk.Label(header_frame, text="", font=("TkDefaultFont", 9, "bold"))
    compare_label.pack(side="right")

    output_text = tk.Text(frame, height=10, state="disabled", wrap="word")
    output_text.pack(fill="both", expand=True, pady=(5, 10))
    output_text.tag_configure("match", foreground="#2e7d32", font=("TkDefaultFont", 9, "bold"))
    output_text.tag_configure("mismatch", foreground="#d32f2f", font=("TkDefaultFont", 9, "bold"))

    def set_output(text, tag=None):
        output_text.configure(state="normal")
        output_text.delete("1.0", tk.END)
        output_text.insert("1.0", text)
        if tag:
            output_text.tag_add(tag, "1.0", "1.end")
        output_text.configure(state="disabled")

    def process_input(event=None):
        compare_label.configure(text="")
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
        valid_hashes = {}

        # Check if multiple files share the exact same basename
        basenames = [os.path.basename(p) for p in paths if os.path.isfile(p)]
        has_dup_names = len(basenames) != len(set(basenames))

        for filepath in paths:
            display_path = filepath if has_dup_names else (os.path.basename(filepath) or filepath)
            if not os.path.isfile(filepath):
                results.append(f"{display_path}:\nSkipped (not a file)")
                continue

            try:
                result = hash_file(filepath)
                valid_hashes[filepath] = result
                results.append(f"{display_path}:\n{result}")
            except OSError as exc:
                results.append(
                    f"{display_path}:\n"
                    f"Error reading file: {exc}"
                )

        tag = None
        if len(valid_hashes) >= 2:
            unique_hashes = set(valid_hashes.values())
            if len(unique_hashes) == 1:
                status_text = f"MATCH: All {len(valid_hashes)} files are identical"
                compare_label.configure(text=status_text, foreground="#2e7d32")
                header = f"[MATCH] All {len(valid_hashes)} files have IDENTICAL {display_name}."
                tag = "match"
            else:
                status_text = f"MISMATCH: {len(unique_hashes)} distinct hashes across {len(valid_hashes)} files"
                compare_label.configure(text=status_text, foreground="#d32f2f")
                header = f"[MISMATCH] Files have DIFFERENT {display_name} ({len(unique_hashes)} distinct hashes across {len(valid_hashes)} files)."
                tag = "mismatch"
            results.insert(0, header + "\n" + "-" * 50)
        else:
            compare_label.configure(text="")

        set_output("\n\n".join(results), tag=tag)

    def copy_output():
        text = output_text.get("1.0", "end-1c")
        if not text:
            return
        frame.clipboard_clear()
        frame.clipboard_append(text)

    def clear_all():
        input_text.delete("1.0", tk.END)
        compare_label.configure(text="")
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
