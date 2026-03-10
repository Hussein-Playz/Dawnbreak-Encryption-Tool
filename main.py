import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import platform
import re
import shutil
import subprocess
import encrypter
import os
import threading
from datetime import datetime

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    HAS_DND = True
except ImportError:
    HAS_DND = False

# --- Paths for config and log ---
APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(APP_DIR, "config.json")
LOG_FILE = os.path.join(APP_DIR, "dawnbreak.log")

# --- Load custom fonts (cross-platform) ---
FONT_DIR = os.path.join(APP_DIR, "fonts")

def _load_fonts():
    """Load .ttf fonts from the fonts directory for the current platform."""
    if not os.path.isdir(FONT_DIR):
        return
    system = platform.system()
    ttf_files = [f for f in os.listdir(FONT_DIR) if f.lower().endswith(".ttf")]
    if not ttf_files:
        return

    if system == "Windows":
        import ctypes
        gdi32 = ctypes.windll.gdi32
        for fname in ttf_files:
            path = os.path.join(FONT_DIR, fname)
            gdi32.AddFontResourceExW(path, 0x10, 0)  # FR_PRIVATE
    elif system == "Darwin":
        user_font_dir = os.path.expanduser("~/Library/Fonts")
        os.makedirs(user_font_dir, exist_ok=True)
        for fname in ttf_files:
            dst = os.path.join(user_font_dir, fname)
            if not os.path.exists(dst):
                shutil.copy2(os.path.join(FONT_DIR, fname), dst)
    else:
        user_font_dir = os.path.expanduser("~/.local/share/fonts")
        os.makedirs(user_font_dir, exist_ok=True)
        copied = False
        for fname in ttf_files:
            dst = os.path.join(user_font_dir, fname)
            if not os.path.exists(dst):
                shutil.copy2(os.path.join(FONT_DIR, fname), dst)
                copied = True
        if copied:
            subprocess.run(["fc-cache", "-f"], capture_output=True)

_load_fonts()

# Font shortcuts — Cinzel family
FONT_TITLE = ("Cinzel", 15, "bold")
FONT_SECTION = ("Cinzel", 10)
FONT_BUTTON = ("Cinzel SemiBold", 9)
FONT_ACTION = ("Cinzel", 11, "bold")
FONT_BODY = ("Cinzel", 9)
FONT_HINT = ("Cinzel", 8)
FONT_LIST = ("Cinzel", 9)
FONT_ENTRY = ("Cinzel", 10)

# --- Theme colors ---
DARK = {
    "bg": "#1e1e2e",
    "fg": "#cdd6f4",
    "accent": "#89b4fa",
    "entry_bg": "#313244",
    "button_bg": "#45475a",
    "button_fg": "#cdd6f4",
    "list_bg": "#313244",
    "list_fg": "#cdd6f4",
    "list_sel_bg": "#585b70",
    "success": "#a6e3a1",
    "error": "#f38ba8",
    "drop_bg": "#2a2a3c",
    "drop_border": "#585b70",
}

LIGHT = {
    "bg": "#eff1f5",
    "fg": "#4c4f69",
    "accent": "#1e66f5",
    "entry_bg": "#ffffff",
    "button_bg": "#ccd0da",
    "button_fg": "#4c4f69",
    "list_bg": "#ffffff",
    "list_fg": "#4c4f69",
    "list_sel_bg": "#bcc0cc",
    "success": "#40a02b",
    "error": "#d20f39",
    "drop_bg": "#e6e9ef",
    "drop_border": "#9ca0b0",
}

# --- Config helpers ---
def _load_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def _save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

# --- Log helper ---
def _write_log(operation, paths, success, error_msg=None):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        for path in paths:
            status = "OK" if success else f"FAILED: {error_msg}"
            f.write(f"[{timestamp}] {operation} | {os.path.basename(path)} | {status}\n")

# --- Password strength ---
def _password_strength(password):
    """Return (score 0-4, label, color_key)."""
    if not password:
        return 0, "", "#666666"
    score = 0
    if len(password) >= 8:
        score += 1
    if len(password) >= 14:
        score += 1
    if re.search(r"[A-Z]", password) and re.search(r"[a-z]", password):
        score += 1
    if re.search(r"\d", password) and re.search(r"[^A-Za-z0-9]", password):
        score += 1
    labels = ["Weak", "Fair", "Good", "Strong"]
    colors = ["#f38ba8", "#fab387", "#f9e2af", "#a6e3a1"]
    idx = max(0, min(score - 1, 3))
    if score == 0:
        return 0, "Weak", "#f38ba8"
    return score, labels[idx], colors[idx]


BaseClass = TkinterDnD.Tk if HAS_DND else tk.Tk


class App(BaseClass):
    def __init__(self):
        super().__init__()
        self.title("Dawnbreak Encryption Tool")
        self.geometry("620x740")
        self.resizable(False, False)
        self.dark_mode = True
        self.theme = DARK
        self.paths = []
        self.is_running = False
        self.config = _load_config()
        self._build_ui()
        self._apply_theme()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        self.main_frame = tk.Frame(self)
        self.main_frame.pack(fill="both", expand=True, padx=16, pady=10)

        # -- Theme toggle row
        top_row = tk.Frame(self.main_frame)
        top_row.pack(fill="x", pady=(0, 6))
        self.theme_btn = tk.Button(top_row, text="Light Mode", width=12,
                                   command=self._toggle_theme, relief="flat",
                                   cursor="hand2", font=FONT_BUTTON)
        self.theme_btn.pack(side="right")
        tk.Label(top_row, text="Dawnbreak Encryption Tool",
                 font=FONT_TITLE).pack(side="left")

        # -- Drop zone / file list
        drop_frame = tk.LabelFrame(self.main_frame, text=" Files / Folders ",
                                   font=FONT_SECTION)
        drop_frame.pack(fill="both", expand=True, pady=(0, 6))

        self.file_listbox = tk.Listbox(drop_frame, height=7, selectmode="extended",
                                       font=FONT_LIST, activestyle="none")
        self.file_listbox.pack(fill="both", expand=True, padx=6, pady=6)

        # Enable drag-and-drop if available
        if HAS_DND:
            self.file_listbox.drop_target_register(DND_FILES)
            self.file_listbox.dnd_bind("<<Drop>>", self._on_drop)
            drop_hint = "Drag & drop files/folders here, or use the buttons below"
        else:
            drop_hint = "Use the buttons below to add files/folders"
        self.drop_hint_label = tk.Label(drop_frame, text=drop_hint,
                                        font=FONT_HINT)
        self.drop_hint_label.pack(pady=(0, 4))

        # -- Browse buttons row
        btn_row = tk.Frame(self.main_frame)
        btn_row.pack(fill="x", pady=(0, 6))
        self.add_file_btn = tk.Button(btn_row, text="+ Add Files", width=14,
                                      command=self._browse_files, relief="flat",
                                      cursor="hand2", font=FONT_BUTTON)
        self.add_file_btn.pack(side="left", padx=(0, 6))
        self.add_folder_btn = tk.Button(btn_row, text="+ Add Folder", width=14,
                                        command=self._browse_folder, relief="flat",
                                        cursor="hand2", font=FONT_BUTTON)
        self.add_folder_btn.pack(side="left", padx=(0, 6))
        self.remove_btn = tk.Button(btn_row, text="Remove Selected", width=14,
                                    command=self._remove_selected, relief="flat",
                                    cursor="hand2", font=FONT_BUTTON)
        self.remove_btn.pack(side="left", padx=(0, 6))
        self.clear_btn = tk.Button(btn_row, text="Clear All", width=10,
                                   command=self._clear_list, relief="flat",
                                   cursor="hand2", font=FONT_BUTTON)
        self.clear_btn.pack(side="left")

        # -- Password section
        pw_frame = tk.LabelFrame(self.main_frame, text=" Password ",
                                 font=FONT_SECTION)
        pw_frame.pack(fill="x", pady=(0, 6))
        inner = tk.Frame(pw_frame)
        inner.pack(fill="x", padx=8, pady=6)

        tk.Label(inner, text="Password:", font=FONT_BODY).grid(
            row=0, column=0, sticky="w", pady=2)
        self.password_var = tk.StringVar()
        self.pw_entry = tk.Entry(inner, textvariable=self.password_var,
                                 show="\u2022", width=42, font=FONT_ENTRY)
        self.pw_entry.grid(row=0, column=1, padx=(8, 0), pady=2)

        tk.Label(inner, text="Confirm:", font=FONT_BODY).grid(
            row=1, column=0, sticky="w", pady=2)
        self.confirm_password_var = tk.StringVar()
        self.cpw_entry = tk.Entry(inner, textvariable=self.confirm_password_var,
                                  show="\u2022", width=42, font=FONT_ENTRY)
        self.cpw_entry.grid(row=1, column=1, padx=(8, 0), pady=2)

        # -- Password strength meter
        strength_frame = tk.Frame(pw_frame)
        strength_frame.pack(fill="x", padx=8, pady=(0, 6))
        tk.Label(strength_frame, text="Strength:", font=FONT_HINT).pack(side="left")
        self.strength_canvas = tk.Canvas(strength_frame, height=14, width=200,
                                         highlightthickness=0)
        self.strength_canvas.pack(side="left", padx=(6, 6))
        self.strength_label = tk.Label(strength_frame, text="", font=FONT_HINT)
        self.strength_label.pack(side="left")

        self.password_var.trace_add("write", self._update_strength)

        # -- Options row
        opt_frame = tk.Frame(self.main_frame)
        opt_frame.pack(fill="x", pady=(0, 6))
        self.secure_delete_var = tk.BooleanVar(value=False)
        self.sd_check = tk.Checkbutton(opt_frame, text="Secure delete originals after encryption/decryption",
                                       variable=self.secure_delete_var,
                                       font=FONT_BODY)
        self.sd_check.pack(side="left")

        # -- Action buttons
        action_frame = tk.Frame(self.main_frame)
        action_frame.pack(fill="x", pady=(0, 6))
        self.encrypt_btn = tk.Button(action_frame, text="Encrypt", width=14,
                                     font=FONT_ACTION,
                                     command=self._encrypt, relief="flat", cursor="hand2")
        self.encrypt_btn.pack(side="left", padx=(0, 8))
        self.decrypt_btn = tk.Button(action_frame, text="Decrypt", width=14,
                                     font=FONT_ACTION,
                                     command=self._decrypt, relief="flat", cursor="hand2")
        self.decrypt_btn.pack(side="left", padx=(0, 8))
        self.verify_btn = tk.Button(action_frame, text="Verify", width=14,
                                    font=FONT_ACTION,
                                    command=self._verify, relief="flat", cursor="hand2")
        self.verify_btn.pack(side="left")

        # -- Progress bar
        self.progress_var = tk.IntVar(value=0)
        self.progress_bar = ttk.Progressbar(self.main_frame, variable=self.progress_var,
                                            maximum=100, length=580)
        self.progress_bar.pack(fill="x", pady=(0, 4))

        # -- Status label
        self.status_var = tk.StringVar(value="Ready")
        self.status_label = tk.Label(self.main_frame, textvariable=self.status_var,
                                     font=FONT_BODY, anchor="w")
        self.status_label.pack(fill="x")

    # ------------------------------------------------------ Password strength
    def _update_strength(self, *_args):
        pw = self.password_var.get()
        score, label, color = _password_strength(pw)
        t = self.theme
        self.strength_canvas.delete("all")
        # Draw background trough
        self.strength_canvas.configure(bg=t["entry_bg"])
        # Draw filled bar
        bar_width = int(score / 4 * 200)
        if bar_width > 0:
            self.strength_canvas.create_rectangle(0, 0, bar_width, 14,
                                                   fill=color, outline="")
        self.strength_label.configure(text=label, fg=color)

    # --------------------------------------------------------- Theme
    def _apply_theme(self):
        t = self.theme
        self.configure(bg=t["bg"])
        self._style_frame(self.main_frame, t)

        # Style all child widgets recursively
        for widget in self._all_children(self.main_frame):
            wtype = widget.winfo_class()
            if wtype == "Frame" or wtype == "Labelframe":
                widget.configure(bg=t["bg"])
                if wtype == "Labelframe":
                    widget.configure(fg=t["fg"])
            elif wtype == "Label":
                widget.configure(bg=t["bg"], fg=t["fg"])
            elif wtype == "Button":
                widget.configure(bg=t["button_bg"], fg=t["button_fg"],
                                 activebackground=t["accent"],
                                 activeforeground="#ffffff")
            elif wtype == "Entry":
                widget.configure(bg=t["entry_bg"], fg=t["fg"],
                                 insertbackground=t["fg"],
                                 relief="flat", highlightthickness=1,
                                 highlightcolor=t["accent"],
                                 highlightbackground=t["drop_border"])
            elif wtype == "Checkbutton":
                widget.configure(bg=t["bg"], fg=t["fg"],
                                 selectcolor=t["entry_bg"],
                                 activebackground=t["bg"],
                                 activeforeground=t["fg"])
            elif wtype == "Listbox":
                widget.configure(bg=t["list_bg"], fg=t["list_fg"],
                                 selectbackground=t["list_sel_bg"],
                                 selectforeground=t["fg"],
                                 relief="flat", highlightthickness=1,
                                 highlightcolor=t["accent"],
                                 highlightbackground=t["drop_border"])
            elif wtype == "Canvas":
                widget.configure(bg=t["entry_bg"])

        # Accent colors for action buttons
        self.encrypt_btn.configure(bg=t["accent"], fg="#ffffff",
                                   activebackground=t["success"])
        self.decrypt_btn.configure(bg=t["accent"], fg="#ffffff",
                                   activebackground=t["success"])
        self.verify_btn.configure(bg=t["button_bg"], fg=t["button_fg"],
                                  activebackground=t["accent"])

        # Theme toggle button text
        self.theme_btn.configure(text="Light Mode" if self.dark_mode else "Dark Mode")

        # ttk progressbar styling
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Custom.Horizontal.TProgressbar",
                        troughcolor=t["entry_bg"],
                        background=t["accent"],
                        thickness=18)
        self.progress_bar.configure(style="Custom.Horizontal.TProgressbar")

        # Re-draw strength meter with new theme
        self._update_strength()

    def _toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self.theme = DARK if self.dark_mode else LIGHT
        self._apply_theme()

    @staticmethod
    def _style_frame(frame, t):
        frame.configure(bg=t["bg"])

    def _all_children(self, widget):
        children = widget.winfo_children()
        result = list(children)
        for child in children:
            result.extend(self._all_children(child))
        return result

    # -------------------------------------------------- File management
    def _last_dir(self):
        """Get the last used directory, or home."""
        d = self.config.get("last_dir", "")
        if d and os.path.isdir(d):
            return d
        return os.path.expanduser("~")

    def _save_last_dir(self, path):
        """Remember the directory of the given path."""
        d = os.path.dirname(path) if os.path.isfile(path) else path
        self.config["last_dir"] = d
        _save_config(self.config)

    def _browse_files(self):
        paths = filedialog.askopenfilenames(initialdir=self._last_dir())
        for p in paths:
            self._add_path(p)
        if paths:
            self._save_last_dir(paths[0])

    def _browse_folder(self):
        path = filedialog.askdirectory(initialdir=self._last_dir())
        if path:
            self._add_path(path)
            self._save_last_dir(path)

    def _add_path(self, path):
        path = path.strip().strip("{}")  # tkinterdnd2 may wrap in braces
        if path and path not in self.paths:
            self.paths.append(path)
            self.file_listbox.insert("end", path)

    def _remove_selected(self):
        selected = list(self.file_listbox.curselection())
        for idx in reversed(selected):
            self.file_listbox.delete(idx)
            del self.paths[idx]

    def _clear_list(self):
        self.file_listbox.delete(0, "end")
        self.paths.clear()

    def _on_drop(self, event):
        raw = event.data
        items = self._parse_dnd_data(raw)
        for item in items:
            self._add_path(item)
        if items:
            self._save_last_dir(items[0])

    @staticmethod
    def _parse_dnd_data(data):
        result = []
        i = 0
        while i < len(data):
            if data[i] == "{":
                end = data.index("}", i)
                result.append(data[i + 1:end])
                i = end + 2
            elif data[i] == " ":
                i += 1
            else:
                end = data.find(" ", i)
                if end == -1:
                    end = len(data)
                result.append(data[i:end])
                i = end + 1
        return result

    # -------------------------------------------------- Actions
    def _set_running(self, running):
        self.is_running = running
        state = "disabled" if running else "normal"
        self.encrypt_btn.configure(state=state)
        self.decrypt_btn.configure(state=state)
        self.verify_btn.configure(state=state)
        self.add_file_btn.configure(state=state)
        self.add_folder_btn.configure(state=state)
        self.remove_btn.configure(state=state)
        self.clear_btn.configure(state=state)

    def _progress(self, value, message):
        self.after(0, lambda: self.progress_var.set(value))
        self.after(0, lambda: self.status_var.set(message))

    def _reset_fields(self):
        self.password_var.set("")
        self.confirm_password_var.set("")
        self._clear_list()
        self.progress_var.set(0)

    # -- Encrypt
    def _encrypt(self):
        if self.is_running:
            return
        paths = list(self.paths)
        password = self.password_var.get()
        confirm = self.confirm_password_var.get()
        do_sd = self.secure_delete_var.get()

        if not paths:
            messagebox.showerror("Error", "Please add at least one file or folder.")
            return
        if not password or not confirm:
            messagebox.showerror("Error", "Please enter and confirm your password.")
            return
        if password != confirm:
            messagebox.showerror("Error", "Passwords do not match!")
            return
        if do_sd:
            if not messagebox.askyesno("Confirm Secure Delete",
                                       "Original files will be permanently destroyed after encryption.\n"
                                       "This cannot be undone. Continue?"):
                return

        self._set_running(True)
        threading.Thread(target=self._run_encrypt, args=(paths, password, do_sd),
                         daemon=True).start()

    def _run_encrypt(self, paths, password, do_sd):
        total = len(paths)
        errors = []
        for idx, path in enumerate(paths):
            base_pct = int(idx / total * 100)

            def cb(pct, msg, _base=base_pct, _total=total):
                overall = _base + int(pct / _total)
                self._progress(overall, msg)

            try:
                if os.path.isfile(path):
                    encrypter.encrypt_file(path, password,
                                           progress_callback=cb,
                                           do_secure_delete=do_sd)
                elif os.path.isdir(path):
                    encrypter.encrypt_folder(path, password,
                                             progress_callback=cb,
                                             do_secure_delete=do_sd)
                else:
                    errors.append(f"{path}: not found")
                    continue
                _write_log("ENCRYPT", [path], True)
            except Exception as e:
                errors.append(f"{os.path.basename(path)}: {e}")
                _write_log("ENCRYPT", [path], False, str(e))

        self._progress(100, "Encryption complete")
        self.after(0, lambda: self._finish("Encryption", errors))

    # -- Decrypt
    def _decrypt(self):
        if self.is_running:
            return
        paths = list(self.paths)
        password = self.password_var.get()
        do_sd = self.secure_delete_var.get()

        if not paths:
            messagebox.showerror("Error", "Please add at least one file or folder.")
            return
        if not password:
            messagebox.showerror("Error", "Please enter your password.")
            return

        not_locked = [p for p in paths if not p.endswith(".locked")]
        if not_locked:
            messagebox.showerror("Error",
                                 "These files don't appear to be encrypted (.locked):\n" +
                                 "\n".join(os.path.basename(p) for p in not_locked))
            return

        self._set_running(True)
        threading.Thread(target=self._run_decrypt, args=(paths, password, do_sd),
                         daemon=True).start()

    def _run_decrypt(self, paths, password, do_sd):
        total = len(paths)
        errors = []
        for idx, path in enumerate(paths):
            base_pct = int(idx / total * 100)

            def cb(pct, msg, _base=base_pct, _total=total):
                overall = _base + int(pct / _total)
                self._progress(overall, msg)

            try:
                original = path.replace(".locked", "")
                if "." in os.path.basename(original):
                    encrypter.decrypt_file(path, password,
                                           progress_callback=cb,
                                           do_secure_delete=do_sd)
                else:
                    encrypter.decrypt_folder(path, password,
                                             progress_callback=cb,
                                             do_secure_delete=do_sd)
                _write_log("DECRYPT", [path], True)
            except Exception as e:
                errors.append(f"{os.path.basename(path)}: {e}")
                _write_log("DECRYPT", [path], False, str(e))

        self._progress(100, "Decryption complete")
        self.after(0, lambda: self._finish("Decryption", errors))

    # -- Verify
    def _verify(self):
        if self.is_running:
            return
        paths = list(self.paths)
        password = self.password_var.get()

        if not paths:
            messagebox.showerror("Error", "Please add at least one .locked file.")
            return
        if not password:
            messagebox.showerror("Error", "Please enter your password.")
            return

        not_locked = [p for p in paths if not p.endswith(".locked")]
        if not_locked:
            messagebox.showerror("Error",
                                 "These files don't appear to be encrypted (.locked):\n" +
                                 "\n".join(os.path.basename(p) for p in not_locked))
            return

        self._set_running(True)
        threading.Thread(target=self._run_verify, args=(paths, password),
                         daemon=True).start()

    def _run_verify(self, paths, password):
        total = len(paths)
        results = []
        for idx, path in enumerate(paths):
            pct = int((idx + 1) / total * 100)
            self._progress(pct, f"Verifying {os.path.basename(path)}...")
            ok, msg = encrypter.verify_file(path, password)
            results.append((os.path.basename(path), ok, msg))
            _write_log("VERIFY", [path], ok, None if ok else msg)

        self._progress(100, "Verification complete")

        lines = []
        for name, ok, msg in results:
            icon = "PASS" if ok else "FAIL"
            lines.append(f"[{icon}] {name}: {msg}")
        summary = "\n".join(lines)

        all_ok = all(ok for _, ok, _ in results)
        self.after(0, lambda: (
            messagebox.showinfo("Verification Results", summary) if all_ok
            else messagebox.showwarning("Verification Results", summary)
        ))
        self.after(0, lambda: self._set_running(False))
        self.after(0, lambda: self.status_var.set("Ready"))

    # -- Finish
    def _finish(self, operation, errors):
        self._set_running(False)
        if errors:
            messagebox.showwarning(f"{operation} Complete",
                                   f"{operation} finished with errors:\n\n" +
                                   "\n".join(errors))
        else:
            messagebox.showinfo("Success", f"{operation} completed successfully!")
        self._reset_fields()
        self.status_var.set("Ready")


if __name__ == "__main__":
    app = App()
    app.mainloop()
