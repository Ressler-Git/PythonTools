import tkinter as tk
from tkinter import ttk
from tkinterdnd2 import DND_FILES
import hashlib
import os

def create_frame(parent):
    # Initialize container frame
    frame = ttk.Frame(parent, padding="10")

    ttk.Label(frame, text="Input Text or Drop Files Here:").pack(anchor='w')
    input_text = tk.Text(frame)
    input_text.pack(fill='both', expand=True, pady=5)

    ttk.Label(frame, text="MD5 Hash:").pack(anchor='w')
    output_text = tk.Text(frame, state='disabled')
    output_text.pack(fill='both', expand=True, pady=5)

    def set_output(text):
        # Safely inject text into read-only widget
        output_text.config(state='normal')
        output_text.delete("1.0", tk.END)
        output_text.insert(tk.END, text)
        output_text.config(state='disabled')

    def process_input(event=None):
        # Real-time text hashing
        data = input_text.get("1.0", tk.END).strip()
        if not data:
            set_output("")
            return
        result = hashlib.md5(data.encode('utf-8')).hexdigest()
        set_output(result)

    def handle_drop(event):
        # Process files received via drag and drop
        file_list = frame.tk.splitlist(event.data)
        results = []
        
        for filepath in file_list:
            if os.path.isfile(filepath):
                try:
                    md5_hash = hashlib.md5()
                    with open(filepath, "rb") as f:
                        for chunk in iter(lambda: f.read(4096), b""):
                            md5_hash.update(chunk)
                    results.append(f"{os.path.basename(filepath)}:\n{md5_hash.hexdigest()}")
                except Exception:
                    results.append(f"{os.path.basename(filepath)}:\nError reading file")
                    
        if results:
            set_output("\n\n".join(results))
            input_text.delete("1.0", tk.END)
            input_text.insert(tk.END, "\n".join(file_list))

    # Bind events for automation
    input_text.bind("<KeyRelease>", process_input)
    input_text.drop_target_register(DND_FILES)
    input_text.dnd_bind('<<Drop>>', handle_drop)

    btn_frame = ttk.Frame(frame)
    btn_frame.pack(fill='x', pady=5)
    ttk.Button(btn_frame, text="Calculate", command=process_input).pack(side='left')

    return frame