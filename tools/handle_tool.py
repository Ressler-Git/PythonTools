import ctypes
from ctypes import wintypes
import os
import re
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    from tkinterdnd2 import DND_FILES
except ImportError:
    DND_FILES = None


# ---------------------------------------------------------------------------
# 1. Windows Restart Manager (rstrtmgr.dll) 内核调用封装
# ---------------------------------------------------------------------------
class RM_UNIQUE_PROCESS(ctypes.Structure):
    _fields_ = [
        ("dwProcessId", wintypes.DWORD),
        ("ProcessStartTime", wintypes.FILETIME),
    ]


CCH_RM_MAX_APP_NAME = 255
CCH_RM_MAX_SVC_NAME = 63


class RM_PROCESS_INFO(ctypes.Structure):
    _fields_ = [
        ("Process", RM_UNIQUE_PROCESS),
        ("strAppName", wintypes.WCHAR * (CCH_RM_MAX_APP_NAME + 1)),
        ("strServiceShortName", wintypes.WCHAR * (CCH_RM_MAX_SVC_NAME + 1)),
        ("ApplicationType", wintypes.DWORD),
        ("AppStatus", wintypes.DWORD),
        ("TSSessionId", wintypes.DWORD),
        ("bRestartable", wintypes.BOOL),
    ]


try:
    _rstrtmgr = ctypes.WinDLL("rstrtmgr")
    _rstrtmgr.RmStartSession.argtypes = [
        ctypes.POINTER(wintypes.DWORD),
        wintypes.DWORD,
        wintypes.LPWSTR,
    ]
    _rstrtmgr.RmStartSession.restype = wintypes.DWORD

    _rstrtmgr.RmRegisterResources.argtypes = [
        wintypes.DWORD,
        wintypes.UINT,
        ctypes.POINTER(wintypes.LPCWSTR),
        wintypes.UINT,
        ctypes.c_void_p,
        wintypes.UINT,
        ctypes.c_void_p,
    ]
    _rstrtmgr.RmRegisterResources.restype = wintypes.DWORD

    _rstrtmgr.RmGetList.argtypes = [
        wintypes.DWORD,
        ctypes.POINTER(wintypes.UINT),
        ctypes.POINTER(wintypes.UINT),
        ctypes.POINTER(RM_PROCESS_INFO),
        ctypes.POINTER(wintypes.DWORD),
    ]
    _rstrtmgr.RmGetList.restype = wintypes.DWORD

    _rstrtmgr.RmEndSession.argtypes = [wintypes.DWORD]
    _rstrtmgr.RmEndSession.restype = wintypes.DWORD
    _RSTRTMGR_AVAILABLE = True
except Exception:
    _RSTRTMGR_AVAILABLE = False


def _query_restart_manager(target_path):
    """使用 Restart Manager API 查询占用，特别擅长检测已载入内存的 DLL/PYD 模块"""
    if not _RSTRTMGR_AVAILABLE or not os.path.exists(target_path):
        return []

    target_path = os.path.abspath(target_path)
    paths_to_check = [target_path]
    if os.path.isdir(target_path):
        for root, _dirs, files in os.walk(target_path):
            for file in files:
                paths_to_check.append(os.path.join(root, file))
                if len(paths_to_check) >= 500:
                    break
            if len(paths_to_check) >= 500:
                break

    session_handle = wintypes.DWORD()
    session_key = (wintypes.WCHAR * 33)()
    res = _rstrtmgr.RmStartSession(ctypes.byref(session_handle), 0, session_key)
    if res != 0:
        return []

    try:
        arr_type = wintypes.LPCWSTR * len(paths_to_check)
        c_paths = arr_type(*paths_to_check)
        res = _rstrtmgr.RmRegisterResources(
            session_handle, len(paths_to_check), c_paths, 0, None, 0, None
        )
        if res != 0:
            return []

        n_proc_needed = wintypes.UINT(0)
        n_proc = wintypes.UINT(0)
        reboot_reasons = wintypes.DWORD(0)

        res = _rstrtmgr.RmGetList(
            session_handle,
            ctypes.byref(n_proc_needed),
            ctypes.byref(n_proc),
            None,
            ctypes.byref(reboot_reasons),
        )
        if res not in (0, 234) or n_proc_needed.value == 0:
            return []

        n_proc.value = n_proc_needed.value
        proc_infos = (RM_PROCESS_INFO * n_proc_needed.value)()
        res = _rstrtmgr.RmGetList(
            session_handle,
            ctypes.byref(n_proc_needed),
            ctypes.byref(n_proc),
            proc_infos,
            ctypes.byref(reboot_reasons),
        )
        if res != 0:
            return []

        results = []
        for i in range(n_proc.value):
            pid = proc_infos[i].Process.dwProcessId
            app_name = proc_infos[i].strAppName or "Unknown"
            results.append(
                {
                    "pid": str(pid),
                    "process": app_name,
                    "type": "Module/File",
                    "handle_id": "-",
                    "path": target_path,
                }
            )
        return results
    finally:
        _rstrtmgr.RmEndSession(session_handle)


# ---------------------------------------------------------------------------
# 2. 定位 handle64.exe 路径与解析
# ---------------------------------------------------------------------------
def _get_handle_exe():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "res"))
    p64 = os.path.join(base_dir, "handle64.exe")
    if os.path.exists(p64):
        return p64
    p = os.path.join(base_dir, "handle.exe")
    if os.path.exists(p):
        return p
    return None


_HANDLE_LINE_PATTERN = re.compile(
    r"^(.*?)\s+pid:\s*(\d+)\s+type:\s*(\S+)\s+([0-9A-Fa-f]+):\s*(.*)$"
)


def _clean_path(obj_path, target_path, rm_results=None):
    """
    解决 handle64.exe 在输出非 ASCII（如中文）时被转换为 '?' 的经典问题。
    通过多重策略精准还原真实 Unicode 路径。
    """
    # 1. 如果用户查询的目标本身就是文件，直接返回用户原装 Unicode 路径
    if os.path.isfile(target_path):
        return target_path

    # 2. 如果路径中不包含问号，直接返回
    if "?" not in obj_path:
        return obj_path

    # 3. 如果 Restart Manager 抓到了同目录且扩展名匹配的真实文件，直接替换
    if rm_results:
        obj_ext = os.path.splitext(obj_path)[1].lower()
        for rm_item in rm_results:
            rm_p = rm_item.get("path", "")
            if os.path.splitext(rm_p)[1].lower() == obj_ext:
                return rm_p

    # 4. 尝试在对应目录下通过模糊匹配反查真实文件名
    dirname, basename = os.path.split(obj_path)
    if os.path.isdir(dirname):
        pat = "^" + re.escape(basename).replace(r"\?", ".+?") + "$"
        try:
            rx = re.compile(pat, re.IGNORECASE)
            matches = [f for f in os.listdir(dirname) if rx.match(f)]
            if len(matches) == 1:
                return os.path.join(dirname, matches[0])
        except Exception:
            pass

    return obj_path


def _query_handle_exe(handle_exe, target_path):
    """调用 handle64.exe 获取详细句柄（包括句柄 ID）"""
    if not handle_exe or not os.path.exists(handle_exe):
        return []

    target_path = target_path.rstrip("\\")
    cmd = [handle_exe, "-accepteula", "-nobanner", "-a", target_path]

    try:
        startupinfo = None
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            startupinfo=startupinfo,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            timeout=10,
        )
        output = proc.stdout
    except Exception:
        return []

    results = []
    for line in output.splitlines():
        line = line.strip()
        m = _HANDLE_LINE_PATTERN.match(line)
        if m:
            proc_name, pid, h_type, handle_id, obj_path = m.groups()
            results.append(
                {
                    "pid": pid,
                    "process": proc_name,
                    "type": h_type,
                    "handle_id": handle_id,
                    "path": obj_path,
                }
            )
    return results


# ---------------------------------------------------------------------------
# 3. 创建 UI Frame
# ---------------------------------------------------------------------------
def create_frame(parent):
    frame = ttk.Frame(parent, padding=10)
    handle_exe = _get_handle_exe()

    # --- Top input bar ---
    top_frame = ttk.Frame(frame)
    top_frame.pack(fill="x", pady=(0, 8))

    ttk.Label(
        top_frame,
        text="Target file or directory path (drop files or folders here):",
    ).pack(anchor="w", pady=(0, 4))

    path_bar = ttk.Frame(top_frame)
    path_bar.pack(fill="x")

    path_var = tk.StringVar()
    entry = ttk.Entry(path_bar, textvariable=path_var)
    entry.pack(side="left", fill="x", expand=True, padx=(0, 6))

    def browse_file():
        f = filedialog.askopenfilename()
        if f:
            path_var.set(os.path.normpath(f))
            run_query()

    def browse_folder():
        d = filedialog.askdirectory()
        if d:
            path_var.set(os.path.normpath(d))
            run_query()

    def clear_all():
        path_var.set("")
        for item in tree.get_children():
            tree.delete(item)
        status_var.set("Ready")

    ttk.Button(path_bar, text="Browse File", command=browse_file).pack(
        side="left", padx=(0, 4)
    )
    ttk.Button(path_bar, text="Browse Folder", command=browse_folder).pack(
        side="left", padx=(0, 4)
    )
    ttk.Button(path_bar, text="Clear", command=clear_all).pack(side="left")

    # --- Middle Treeview table ---
    table_frame = ttk.Frame(frame)
    table_frame.pack(fill="both", expand=True, pady=(0, 8))

    columns = ("pid", "process", "type", "handle_id", "path")
    tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")

    tree.heading("pid", text="PID")
    tree.heading("process", text="Process")
    tree.heading("type", text="Type")
    tree.heading("handle_id", text="Handle ID")
    tree.heading("path", text="Path / Details")

    tree.column("pid", width=70, anchor="center")
    tree.column("process", width=140, anchor="w")
    tree.column("type", width=100, anchor="center")
    tree.column("handle_id", width=80, anchor="center")
    tree.column("path", width=340, anchor="w")

    vsb = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
    hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

    tree.grid(row=0, column=0, sticky="nsew")
    vsb.grid(row=0, column=1, sticky="ns")
    hsb.grid(row=1, column=0, sticky="ew")

    table_frame.grid_rowconfigure(0, weight=1)
    table_frame.grid_columnconfigure(0, weight=1)

    # --- Bottom action bar & status bar ---
    status_var = tk.StringVar(value="Ready")

    def run_query():
        target = path_var.get().strip().strip("\"'")
        if not target:
            messagebox.showwarning("Notice", "Please specify or drop a target path first.")
            return

        if not os.path.exists(target):
            messagebox.showwarning("Notice", f"Path does not exist:\n{target}")
            return

        for item in tree.get_children():
            tree.delete(item)

        status_var.set("Scanning for locking processes...")
        frame.update_idletasks()

        # 1. Primary: handle64.exe for kernel handles
        results = _query_handle_exe(handle_exe, target)
        found_pids = {r["pid"] for r in results}

        # 2. Collaborative: Windows Restart Manager for modules & memory mappings
        rm_results = _query_restart_manager(target)

        # 3. Clean and restore any '?' non-ASCII paths
        for r in results:
            r["path"] = _clean_path(r["path"], target, rm_results)

        for r in rm_results:
            if r["pid"] not in found_pids:
                results.append(r)
                found_pids.add(r["pid"])

        # Populate tree
        for r in results:
            tree.insert(
                "",
                "end",
                values=(r["pid"], r["process"], r["type"], r["handle_id"], r["path"]),
            )

        if results:
            status_var.set(f"Scan complete: Found {len(results)} locking item(s).")
        else:
            status_var.set("Scan complete: No processes locking this path.")

    def kill_selected():
        selected = tree.selection()
        if not selected:
            messagebox.showinfo("Notice", "Please select a process from the list first.")
            return
        item = tree.item(selected[0])
        pid, proc_name = item["values"][0], item["values"][1]

        if not messagebox.askyesno(
            "Confirm Kill Process",
            f"Are you sure you want to forcibly terminate this process?\n\nProcess: {proc_name}\nPID: {pid}\n\nWarning: Unsaved data in this application may be lost.",
        ):
            return

        try:
            res = subprocess.run(
                ["taskkill", "/F", "/PID", str(pid)],
                capture_output=True,
                text=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if res.returncode == 0:
                messagebox.showinfo(
                    "Success", f"Process {proc_name} (PID: {pid}) terminated successfully."
                )
                run_query()
            else:
                err = res.stderr.strip() or res.stdout.strip()
                messagebox.showerror("Error", f"Failed to terminate process:\n{err}")
        except Exception as exc:
            messagebox.showerror("Error", f"Exception while killing process: {exc}")

    def close_handle_selected():
        selected = tree.selection()
        if not selected:
            messagebox.showinfo("Notice", "Please select an item from the list first.")
            return
        item = tree.item(selected[0])
        pid = str(item["values"][0])
        proc_name = item["values"][1]
        handle_id = str(item["values"][3])

        if handle_id == "-" or not handle_id:
            messagebox.showinfo(
                "Notice",
                "This item is a loaded module or memory section. Please use 'Kill Process' instead.",
            )
            return

        if not handle_exe:
            messagebox.showerror("Error", "handle64.exe not found. Cannot close handle.")
            return

        if not messagebox.askyesno(
            "Confirm Close Handle",
            f"Are you sure you want to forcibly close this handle?\n\nProcess: {proc_name} (PID: {pid})\nHandle ID: {handle_id}\n\nWarning: Forcibly closing handles may cause the application to crash.",
        ):
            return

        try:
            res = subprocess.run(
                [handle_exe, "-c", handle_id, "-p", pid, "-y"],
                capture_output=True,
                text=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            messagebox.showinfo(
                "Done", f"Close handle command executed.\nOutput: {res.stdout.strip() or 'OK'}"
            )
            run_query()
        except Exception as exc:
            messagebox.showerror("Error", f"Exception while closing handle: {exc}")

    def copy_selected():
        selected = tree.selection()
        if not selected:
            lines = ["PID\tProcess\tType\tHandle\tPath"]
            for child in tree.get_children():
                vals = [str(v) for v in tree.item(child)["values"]]
                lines.append("\t".join(vals))
            text = "\n".join(lines)
        else:
            item = tree.item(selected[0])
            text = "\t".join(str(v) for v in item["values"])

        frame.clipboard_clear()
        frame.clipboard_append(text)
        messagebox.showinfo("Copied", "Information copied to clipboard.")

    action_bar = ttk.Frame(frame)
    action_bar.pack(fill="x", pady=(0, 6))

    ttk.Button(action_bar, text="Query", command=run_query).pack(
        side="left", padx=(0, 6)
    )
    ttk.Button(action_bar, text="Kill Process", command=kill_selected).pack(
        side="left", padx=(0, 6)
    )
    ttk.Button(action_bar, text="Close Handle", command=close_handle_selected).pack(
        side="left", padx=(0, 6)
    )
    ttk.Button(action_bar, text="Copy", command=copy_selected).pack(
        side="left", padx=(0, 6)
    )

    status_label = ttk.Label(
        frame, textvariable=status_var, relief="sunken", anchor="w", padding=(6, 3)
    )
    status_label.pack(fill="x")

    # --- Drag and drop support ---
    def handle_drop(event):
        paths = frame.tk.splitlist(event.data)
        if paths:
            first_path = os.path.normpath(paths[0])
            path_var.set(first_path)
            run_query()

    if DND_FILES is not None:
        for widget in (frame, entry, tree):
            if hasattr(widget, "drop_target_register"):
                widget.drop_target_register(DND_FILES)
                widget.dnd_bind("<<Drop>>", handle_drop)

    # Press Enter in input box to trigger search
    entry.bind("<Return>", lambda _event: run_query())

    return frame
