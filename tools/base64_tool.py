import base64
import binascii
import json
import tkinter as tk
from tkinter import ttk


def create_frame(parent):
    frame = ttk.Frame(parent, padding=10)

    ttk.Label(frame, text="Input data:").pack(anchor="w")
    input_text = tk.Text(frame, height=10, undo=True, wrap="word")
    input_text.pack(fill="both", expand=True, pady=(5, 10))

    ttk.Label(frame, text="Result:").pack(anchor="w")
    output_text = tk.Text(frame, height=10, state="disabled", wrap="word")
    output_text.pack(fill="both", expand=True, pady=(5, 10))

    def set_output(text):
        output_text.configure(state="normal")
        output_text.delete("1.0", tk.END)
        output_text.insert("1.0", text)
        output_text.configure(state="disabled")

    def get_input():
        # Preserve the user's text exactly, except Tk's implicit final newline.
        return input_text.get("1.0", "end-1c")

    def decode_segment(segment):
        compact = "".join(segment.split())
        if not compact:
            return b""

        padded = compact + "=" * ((4 - len(compact) % 4) % 4)
        return base64.b64decode(
            padded.encode("ascii"),
            altchars=b"-_",
            validate=True,
        )

    def format_decoded(data):
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            return f"Binary data ({len(data)} bytes)\nHex:\n{data.hex()}"

        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            return text
        return json.dumps(obj, ensure_ascii=False, indent=2)

    def encode_input():
        data = get_input()
        encoded = base64.b64encode(data.encode("utf-8")).decode("ascii")
        set_output(encoded)

    def decode_input():
        data = get_input()
        if not data:
            set_output("")
            return

        try:
            decoded = decode_segment(data)
            set_output(format_decoded(decoded))
        except (binascii.Error, ValueError, UnicodeEncodeError) as exc:
            set_output(f"Invalid Base64 input:\n{exc}")

    def decode_jwt():
        token = get_input().strip()
        parts = token.split(".")
        if len(parts) < 2:
            set_output("Invalid JWT: expected at least header.payload")
            return

        try:
            header = format_decoded(decode_segment(parts[0]))
            payload = format_decoded(decode_segment(parts[1]))
            set_output(f"Header:\n{header}\n\nPayload:\n{payload}")
        except (binascii.Error, ValueError, UnicodeEncodeError) as exc:
            set_output(f"Invalid JWT/Base64URL input:\n{exc}")

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

    button_frame = ttk.Frame(frame)
    button_frame.pack(fill="x")
    ttk.Button(button_frame, text="Encode", command=encode_input).pack(side="left")
    ttk.Button(button_frame, text="Decode", command=decode_input).pack(side="left", padx=(8, 0))
    ttk.Button(button_frame, text="Decode JWT", command=decode_jwt).pack(side="left", padx=(8, 0))
    ttk.Button(button_frame, text="Copy", command=copy_output).pack(side="left", padx=(8, 0))
    ttk.Button(button_frame, text="Clear", command=clear_all).pack(side="left", padx=(8, 0))

    return frame
