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
import time
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
FONT_SUBTITLE = ("Cinzel", 9)
FONT_SECTION = ("Cinzel", 10)
FONT_BUTTON = ("Cinzel SemiBold", 9)
FONT_ACTION = ("Cinzel", 11, "bold")
FONT_BODY = ("Cinzel", 9)
FONT_HINT = ("Cinzel", 8)
FONT_LIST = ("Cinzel", 9)
FONT_ENTRY = ("Cinzel", 10)
FONT_TREE_HEAD = ("Cinzel SemiBold", 9)

# --- Theme colors ---
DARK = {
    "bg": "#1e1e2e",
    "fg": "#cdd6f4",
    "accent": "#89b4fa",
    "accent_hover": "#a6c8ff",
    "entry_bg": "#313244",
    "button_bg": "#45475a",
    "button_fg": "#cdd6f4",
    "button_hover": "#585b70",
    "list_bg": "#313244",
    "list_fg": "#cdd6f4",
    "list_sel_bg": "#585b70",
    "success": "#a6e3a1",
    "error": "#f38ba8",
    "warning": "#fab387",
    "drop_bg": "#2a2a3c",
    "drop_border": "#585b70",
    "separator": "#45475a",
}

LIGHT = {
    "bg": "#eff1f5",
    "fg": "#4c4f69",
    "accent": "#1e66f5",
    "accent_hover": "#3578f7",
    "entry_bg": "#ffffff",
    "button_bg": "#ccd0da",
    "button_fg": "#4c4f69",
    "button_hover": "#bcc0cc",
    "list_bg": "#ffffff",
    "list_fg": "#4c4f69",
    "list_sel_bg": "#bcc0cc",
    "success": "#40a02b",
    "error": "#d20f39",
    "warning": "#df8e1d",
    "drop_bg": "#e6e9ef",
    "drop_border": "#9ca0b0",
    "separator": "#ccd0da",
}

# --- Common password set for strength penalty ---
COMMON_PASSWORDS = {
    "password", "123456", "12345678", "qwerty", "abc123", "monkey", "1234567",
    "letmein", "trustno1", "dragon", "baseball", "iloveyou", "master", "sunshine",
    "ashley", "michael", "shadow", "123123", "654321", "superman", "qazwsx",
    "michael", "football", "password1", "password123", "welcome", "jesus",
    "ninja", "mustang", "password1!", "admin", "admin123", "root", "toor",
    "pass", "test", "guest", "master123", "changeme", "hello", "charlie",
    "donald", "passw0rd", "p@ssword", "p@ssw0rd", "qwerty123", "1q2w3e4r",
    "zaq1xsw2", "1qaz2wsx",
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

# --- Password strength (enhanced, 0-5 scale) ---
def _password_strength(password):
    """Return (score 0-5, label, color_key)."""
    if not password:
        return 0, "", "#666666"

    score = 0

    # Length scoring
    if len(password) >= 8:
        score += 1
    if len(password) >= 12:
        score += 1
    if len(password) >= 16:
        score += 1

    # Mixed case
    if re.search(r"[A-Z]", password) and re.search(r"[a-z]", password):
        score += 1

    # Digits + special chars
    if re.search(r"\d", password) and re.search(r"[^A-Za-z0-9]", password):
        score += 1

    # Penalties
    if password.lower() in COMMON_PASSWORDS:
        score = min(score, 1)

    # Repeated characters (e.g., "aaaaaa")
    if re.search(r"(.)\1{3,}", password):
        score = max(0, score - 1)

    # Sequential patterns (e.g., "abcdef", "123456")
    sequential = 0
    for i in range(len(password) - 1):
        if ord(password[i + 1]) == ord(password[i]) + 1:
            sequential += 1
    if sequential >= 4:
        score = max(0, score - 1)

    labels = ["Weak", "Weak", "Fair", "Good", "Strong", "Very Strong"]
    colors = ["#f38ba8", "#f38ba8", "#fab387", "#f9e2af", "#a6e3a1", "#40a02b"]
    score = max(0, min(score, 5))
    return score, labels[score], colors[score]


# --- Human-readable file size ---
def _human_size(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


BaseClass = TkinterDnD.Tk if HAS_DND else tk.Tk


class App(BaseClass):
    def __init__(self):
        super().__init__()
        self.title("Dawnbreak Encryption Tool")
        self.geometry("700x780")
        self.minsize(620, 700)
        self.resizable(True, True)
        self.dark_mode = True
        self.theme = DARK
        self.paths = []
        self.is_running = False
        self.config = _load_config()
        self._elapsed_start = None
        self._elapsed_after_id = None
        self._status_flash_id = None
        self._pw_visible = False
        self._cpw_visible = False
        self._build_ui()
        self._apply_theme()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        self.main_frame = tk.Frame(self)
        self.main_frame.pack(fill="both", expand=True, padx=16, pady=10)

        # Configure grid weights for resizable layout
        self.main_frame.columnconfigure(0, weight=1)
        # Row indices:
        # 0: title row
        # 1: subtitle
        # 2: separator
        # 3: file list (expandable)
        # 4: drop hint
        # 5: browse buttons
        # 6: separator
        # 7: password section
        # 8: separator
        # 9: options
        # 10: action buttons
        # 11: progress bar + elapsed
        # 12: status label
        self.main_frame.rowconfigure(3, weight=1)

        row = 0

        # -- Theme toggle row + Title
        top_row = tk.Frame(self.main_frame)
        top_row.grid(row=row, column=0, sticky="ew", pady=(0, 2))
        self.theme_btn = tk.Button(top_row, text="Light Mode", width=12,
                                   command=self._toggle_theme, relief="flat",
                                   cursor="hand2", font=FONT_BUTTON)
        self.theme_btn.pack(side="right")
        self.title_label = tk.Label(top_row, text="Dawnbreak Encryption Tool",
                                    font=FONT_TITLE)
        self.title_label.pack(side="left")
        row += 1

        # -- Subtitle
        self.subtitle_label = tk.Label(self.main_frame, text="Secure File Encryption",
                                       font=FONT_SUBTITLE)
        self.subtitle_label.grid(row=row, column=0, sticky="w", pady=(0, 6))
        row += 1

        # -- Separator
        self.sep1 = ttk.Separator(self.main_frame, orient="horizontal")
        self.sep1.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        row += 1

        # -- Drop zone / file list (Treeview)
        tree_frame = tk.Frame(self.main_frame)
        tree_frame.grid(row=row, column=0, sticky="nsew", pady=(0, 4))
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        columns = ("status", "name", "size", "path")
        self.file_tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                                      selectmode="extended", height=8)
        self.file_tree.heading("status", text="Status")
        self.file_tree.heading("name", text="Name")
        self.file_tree.heading("size", text="Size")
        self.file_tree.heading("path", text="Path")
        self.file_tree.column("status", width=60, minwidth=50, anchor="center")
        self.file_tree.column("name", width=180, minwidth=100)
        self.file_tree.column("size", width=80, minwidth=60, anchor="e")
        self.file_tree.column("path", width=300, minwidth=100)

        self.tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical",
                                         command=self.file_tree.yview)
        self.file_tree.configure(yscrollcommand=self.tree_scroll.set)
        self.file_tree.grid(row=0, column=0, sticky="nsew")
        self.tree_scroll.grid(row=0, column=1, sticky="ns")

        # Enable drag-and-drop if available
        if HAS_DND:
            self.file_tree.drop_target_register(DND_FILES)
            self.file_tree.dnd_bind("<<Drop>>", self._on_drop)
            drop_hint = "Drag & drop files/folders here, or use the buttons below"
        else:
            drop_hint = "Use the buttons below to add files/folders"

        row += 1
        self.drop_hint_label = tk.Label(self.main_frame, text=drop_hint,
                                        font=FONT_HINT)
        self.drop_hint_label.grid(row=row, column=0, sticky="w", pady=(0, 6))
        row += 1

        # -- Browse buttons row
        btn_row = tk.Frame(self.main_frame)
        btn_row.grid(row=row, column=0, sticky="ew", pady=(0, 10))
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
        row += 1

        # -- Separator
        self.sep2 = ttk.Separator(self.main_frame, orient="horizontal")
        self.sep2.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        row += 1

        # -- Password section
        pw_frame = tk.LabelFrame(self.main_frame, text=" Password ",
                                 font=FONT_SECTION)
        pw_frame.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        inner = tk.Frame(pw_frame)
        inner.pack(fill="x", padx=8, pady=6)
        inner.columnconfigure(1, weight=1)

        tk.Label(inner, text="Password:", font=FONT_BODY).grid(
            row=0, column=0, sticky="w", pady=2)
        self.password_var = tk.StringVar()
        self.pw_entry = tk.Entry(inner, textvariable=self.password_var,
                                 show="\u2022", width=42, font=FONT_ENTRY)
        self.pw_entry.grid(row=0, column=1, padx=(8, 4), pady=2, sticky="ew")
        self.pw_show_btn = tk.Button(inner, text="Show", width=5,
                                     command=self._toggle_pw_visibility,
                                     relief="flat", cursor="hand2", font=FONT_HINT)
        self.pw_show_btn.grid(row=0, column=2, pady=2)

        tk.Label(inner, text="Confirm:", font=FONT_BODY).grid(
            row=1, column=0, sticky="w", pady=2)
        self.confirm_password_var = tk.StringVar()
        self.cpw_entry = tk.Entry(inner, textvariable=self.confirm_password_var,
                                  show="\u2022", width=42, font=FONT_ENTRY)
        self.cpw_entry.grid(row=1, column=1, padx=(8, 4), pady=2, sticky="ew")
        self.cpw_show_btn = tk.Button(inner, text="Show", width=5,
                                      command=self._toggle_cpw_visibility,
                                      relief="flat", cursor="hand2", font=FONT_HINT)
        self.cpw_show_btn.grid(row=1, column=2, pady=2)

        # -- Password strength meter (5-segment)
        strength_frame = tk.Frame(pw_frame)
        strength_frame.pack(fill="x", padx=8, pady=(0, 6))
        tk.Label(strength_frame, text="Strength:", font=FONT_HINT).pack(side="left")
        self.strength_canvas = tk.Canvas(strength_frame, height=14, width=200,
                                         highlightthickness=0)
        self.strength_canvas.pack(side="left", padx=(6, 6))
        self.strength_label = tk.Label(strength_frame, text="", font=FONT_HINT)
        self.strength_label.pack(side="left")

        self.password_var.trace_add("write", self._update_strength)
        row += 1

        # -- Separator
        self.sep3 = ttk.Separator(self.main_frame, orient="horizontal")
        self.sep3.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        row += 1

        # -- Options row
        opt_frame = tk.Frame(self.main_frame)
        opt_frame.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        self.secure_delete_var = tk.BooleanVar(value=False)
        self.sd_check = tk.Checkbutton(opt_frame, text="Secure delete originals after encryption/decryption",
                                       variable=self.secure_delete_var,
                                       font=FONT_BODY)
        self.sd_check.pack(side="left")
        row += 1

        # -- Action buttons
        action_frame = tk.Frame(self.main_frame)
        action_frame.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        self.encrypt_btn = tk.Button(action_frame, text="\U0001f512 Encrypt", width=16,
                                     font=FONT_ACTION,
                                     command=self._encrypt, relief="flat", cursor="hand2")
        self.encrypt_btn.pack(side="left", padx=(0, 8))
        self.decrypt_btn = tk.Button(action_frame, text="\U0001f513 Decrypt", width=16,
                                     font=FONT_ACTION,
                                     command=self._decrypt, relief="flat", cursor="hand2")
        self.decrypt_btn.pack(side="left", padx=(0, 8))
        self.verify_btn = tk.Button(action_frame, text="\u2713 Verify", width=16,
                                    font=FONT_ACTION,
                                    command=self._verify, relief="flat", cursor="hand2")
        self.verify_btn.pack(side="left")
        row += 1

        # -- Progress bar + elapsed time
        progress_row = tk.Frame(self.main_frame)
        progress_row.grid(row=row, column=0, sticky="ew", pady=(0, 4))
        progress_row.columnconfigure(0, weight=1)
        self.progress_var = tk.IntVar(value=0)
        self.progress_bar = ttk.Progressbar(progress_row, variable=self.progress_var,
                                            maximum=100)
        self.progress_bar.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.elapsed_var = tk.StringVar(value="")
        self.elapsed_label = tk.Label(progress_row, textvariable=self.elapsed_var,
                                      font=FONT_HINT, width=10, anchor="e")
        self.elapsed_label.grid(row=0, column=1)
        row += 1

        # -- Status label
        self.status_var = tk.StringVar(value="Ready")
        self.status_label = tk.Label(self.main_frame, textvariable=self.status_var,
                                     font=FONT_BODY, anchor="w")
        self.status_label.grid(row=row, column=0, sticky="ew")

        # -- Collect all standard buttons for hover binding
        self._std_buttons = [
            self.add_file_btn, self.add_folder_btn, self.remove_btn,
            self.clear_btn, self.theme_btn, self.pw_show_btn, self.cpw_show_btn,
        ]
        self._accent_buttons = [self.encrypt_btn, self.decrypt_btn]
        self._other_buttons = [self.verify_btn]

    # ------------------------------------------------------ Password visibility
    def _toggle_pw_visibility(self):
        self._pw_visible = not self._pw_visible
        self.pw_entry.configure(show="" if self._pw_visible else "\u2022")
        self.pw_show_btn.configure(text="Hide" if self._pw_visible else "Show")

    def _toggle_cpw_visibility(self):
        self._cpw_visible = not self._cpw_visible
        self.cpw_entry.configure(show="" if self._cpw_visible else "\u2022")
        self.cpw_show_btn.configure(text="Hide" if self._cpw_visible else "Show")

    # ------------------------------------------------------ Password strength
    def _update_strength(self, *_args):
        pw = self.password_var.get()
        score, label, color = _password_strength(pw)
        t = self.theme
        self.strength_canvas.delete("all")
        self.strength_canvas.configure(bg=t["entry_bg"])
        # Draw 5-segment bar
        seg_width = 200 / 5
        seg_gap = 3
        segment_colors = ["#f38ba8", "#fab387", "#f9e2af", "#a6e3a1", "#40a02b"]
        for i in range(5):
            x0 = i * seg_width + (seg_gap if i > 0 else 0)
            x1 = (i + 1) * seg_width - seg_gap
            if i < score:
                fill = segment_colors[i]
            else:
                fill = t["entry_bg"]
            self.strength_canvas.create_rectangle(x0, 2, x1, 12,
                                                   fill=fill, outline="")
        self.strength_label.configure(text=label, fg=color)

    # --------------------------------------------------------- Hover effects
    def _bind_hover(self, btn, normal_bg, hover_bg):
        btn.bind("<Enter>", lambda e, b=btn, c=hover_bg: b.configure(bg=c))
        btn.bind("<Leave>", lambda e, b=btn, c=normal_bg: b.configure(bg=c))

    def _setup_hover_bindings(self):
        t = self.theme
        for btn in self._std_buttons:
            self._bind_hover(btn, t["button_bg"], t["button_hover"])
        for btn in self._accent_buttons:
            self._bind_hover(btn, t["accent"], t["accent_hover"])
        for btn in self._other_buttons:
            self._bind_hover(btn, t["button_bg"], t["button_hover"])

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

        # ttk styling
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Custom.Horizontal.TProgressbar",
                        troughcolor=t["entry_bg"],
                        background=t["accent"],
                        thickness=18)
        self.progress_bar.configure(style="Custom.Horizontal.TProgressbar")

        # Treeview styling
        style.configure("Custom.Treeview",
                        background=t["list_bg"],
                        foreground=t["list_fg"],
                        fieldbackground=t["list_bg"],
                        font=FONT_LIST,
                        rowheight=24)
        style.configure("Custom.Treeview.Heading",
                        background=t["button_bg"],
                        foreground=t["button_fg"],
                        font=FONT_TREE_HEAD)
        style.map("Custom.Treeview",
                  background=[("selected", t["list_sel_bg"])],
                  foreground=[("selected", t["fg"])])
        self.file_tree.configure(style="Custom.Treeview")

        # Separator styling
        style.configure("Custom.TSeparator", background=t["separator"])
        self.sep1.configure(style="Custom.TSeparator")
        self.sep2.configure(style="Custom.TSeparator")
        self.sep3.configure(style="Custom.TSeparator")

        # Scrollbar styling
        style.configure("Custom.Vertical.TScrollbar",
                        background=t["button_bg"],
                        troughcolor=t["entry_bg"],
                        arrowcolor=t["fg"])
        self.tree_scroll.configure(style="Custom.Vertical.TScrollbar")

        # Setup hover bindings
        self._setup_hover_bindings()

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

    # -------------------------------------------------------- Status flash
    def _flash_status(self, color):
        """Briefly highlight the status label background, then fade back."""
        if self._status_flash_id:
            self.after_cancel(self._status_flash_id)
        self.status_label.configure(bg=color)
        self._status_flash_id = self.after(800, lambda: self.status_label.configure(
            bg=self.theme["bg"]))

    # -------------------------------------------------- File management
    def _last_dir(self):
        d = self.config.get("last_dir", "")
        if d and os.path.isdir(d):
            return d
        return os.path.expanduser("~")

    def _save_last_dir(self, path):
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
        path = path.strip().strip("{}")
        if path and path not in self.paths:
            self.paths.append(path)
            # Determine status, name, size
            name = os.path.basename(path)
            if os.path.isdir(path):
                status = "[DIR]"
                size_str = ""
            elif path.endswith(".locked"):
                status = "[ENC]"
                try:
                    size_str = _human_size(os.path.getsize(path))
                except OSError:
                    size_str = "?"
            else:
                status = "[FILE]"
                try:
                    size_str = _human_size(os.path.getsize(path))
                except OSError:
                    size_str = "?"
            self.file_tree.insert("", "end", iid=path,
                                  values=(status, name, size_str, path))

    def _remove_selected(self):
        selected = self.file_tree.selection()
        for item_id in selected:
            self.file_tree.delete(item_id)
            if item_id in self.paths:
                self.paths.remove(item_id)

    def _clear_list(self):
        for item in self.file_tree.get_children():
            self.file_tree.delete(item)
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

    # -------------------------------------------------- Elapsed time
    def _start_elapsed(self):
        self._elapsed_start = time.time()
        self._update_elapsed()

    def _update_elapsed(self):
        if self._elapsed_start is None:
            return
        elapsed = time.time() - self._elapsed_start
        mins, secs = divmod(int(elapsed), 60)
        self.elapsed_var.set(f"{mins:02d}:{secs:02d}")
        self._elapsed_after_id = self.after(500, self._update_elapsed)

    def _stop_elapsed(self):
        self._elapsed_start = None
        if self._elapsed_after_id:
            self.after_cancel(self._elapsed_after_id)
            self._elapsed_after_id = None

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
        # Disable/enable password fields during operations
        pw_state = "disabled" if running else "normal"
        self.pw_entry.configure(state=pw_state)
        self.cpw_entry.configure(state=pw_state)
        self.pw_show_btn.configure(state=state)
        self.cpw_show_btn.configure(state=state)
        if running:
            self._start_elapsed()
        else:
            self._stop_elapsed()

    def _progress(self, value, message):
        self.after(0, lambda: self.progress_var.set(value))
        self.after(0, lambda: self.status_var.set(message))

    def _reset_fields(self):
        self.password_var.set("")
        self.confirm_password_var.set("")
        self._clear_list()
        self.progress_var.set(0)
        self.elapsed_var.set("")

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
        self._flash_status(self.theme["accent"])
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
        self._flash_status(self.theme["accent"])
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
        self._flash_status(self.theme["accent"])
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
        self.after(0, lambda: self._flash_status(
            self.theme["success"] if all_ok else self.theme["error"]))

    # -- Finish
    def _finish(self, operation, errors):
        self._set_running(False)
        if errors:
            self._flash_status(self.theme["error"])
            messagebox.showwarning(f"{operation} Complete",
                                   f"{operation} finished with errors:\n\n" +
                                   "\n".join(errors))
        else:
            self._flash_status(self.theme["success"])
            messagebox.showinfo("Success", f"{operation} completed successfully!")
        self._reset_fields()
        self.status_var.set("Ready")


if __name__ == "__main__":
    app = App()
    app.mainloop()
