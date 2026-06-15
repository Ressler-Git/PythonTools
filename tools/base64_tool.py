import tkinter as tk
from tkinter import ttk
import base64
import re

def create_frame(parent):
    # Initialize container frame
    frame = ttk.Frame(parent, padding="10")

    ttk.Label(frame, text="Input Data:").pack(anchor='w')
    input_text = tk.Text(frame)
    input_text.pack(fill='both', expand=True, pady=5)

    ttk.Label(frame, text="Result:").pack(anchor='w')
    output_text = tk.Text(frame, state='disabled')
    output_text.pack(fill='both', expand=True, pady=5)

    def set_output(text):
        # Safely inject text into read-only widget
        output_text.config(state='normal')
        output_text.delete("1.0", tk.END)
        output_text.insert(tk.END, text)
        output_text.config(state='disabled')

    def is_likely_base64(s):
        # Validate format against Base64 and JWT standards
        clean_s = re.sub(r'[\s.]', '', s)
        return bool(re.match(r'^[A-Za-z0-9+/=_-]+$', clean_s))

    def process_input(event=None):
        # Auto-detect context and execute appropriate logic
        input_str = input_text.get("1.0", tk.END).strip()
        if not input_str:
            set_output("")
            return

        def decode_segment(segment):
            padded = segment + "=" * ((4 - len(segment) % 4) % 4)
            return base64.urlsafe_b64decode(padded).decode('utf-8')

        # Attempt decoding operations first
        if is_likely_base64(input_str):
            try:
                if "." in input_str:
                    parts = input_str.split(".")
                    decoded_parts = [decode_segment(p) for p in parts[:2]]
                    result = "\n***\n".join(decoded_parts)
                else:
                    result = decode_segment(input_str)
                set_output(f"Decoded:\n{result}")
                return
            except Exception:
                pass

        # Fallback to encoding sequence
        try:
            data = input_str.encode('utf-8')
            result = base64.b64encode(data).decode('utf-8')
            set_output(f"Encoded:\n{result}")
        except Exception as e:
            set_output(f"Error: {str(e)}")

    # Bind events for real-time automation
    input_text.bind("<KeyRelease>", process_input)

    btn_frame = ttk.Frame(frame)
    btn_frame.pack(fill='x', pady=5)
    ttk.Button(btn_frame, text="Process", command=process_input).pack(side='left')

    return frame