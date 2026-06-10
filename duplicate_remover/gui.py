import os
import csv
import json
import queue
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import time
from datetime import datetime
import winreg
from typing import Optional

from PIL import Image, ImageTk, ImageDraw

try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False

import duplicate_remover.utils as utils
from duplicate_remover.duplicate_finder import DuplicateFinderEngine

# ── Color Palettes ─────────────────────────────────────────────────────────────
DARK_THEME = {
    'bg':               '#1e1e1e',
    'card_bg':          '#2d2d2d',
    'text':             '#ffffff',
    'muted_text':       '#aaaaaa',
    'border':           '#3f3f3f',
    'accent':           '#0078d4',
    'accent_hover':     '#106ebe',
    'success':          '#107c41',
    'danger':           '#a80000',
    'select_bg':        '#0078d4',
    'select_fg':        '#ffffff',
    'checked_bg':       '#2a3a4e',
    'group_header_bg':  '#252525',
}

LIGHT_THEME = {
    'bg':               '#f3f3f3',
    'card_bg':          '#ffffff',
    'text':             '#000000',
    'muted_text':       '#666666',
    'border':           '#d2d2d2',
    'accent':           '#0078d4',
    'accent_hover':     '#106ebe',
    'success':          '#107c41',
    'danger':           '#a80000',
    'select_bg':        '#0078d4',
    'select_fg':        '#ffffff',
    'checked_bg':       '#e0f2fe',
    'group_header_bg':  '#e5e5e5',
}

# ── File-type icon map ─────────────────────────────────────────────────────────
FILE_TYPE_ICONS = {
    # Images
    '.jpg': '🖼', '.jpeg': '🖼', '.png': '🖼', '.gif': '🖼', '.bmp': '🖼',
    '.webp': '🖼', '.tiff': '🖼', '.tif': '🖼', '.svg': '🖼', '.ico': '🖼',
    '.heic': '🖼', '.raw': '🖼', '.cr2': '🖼', '.nef': '🖼', '.arw': '🖼',
    '.psd': '🖼', '.xcf': '🖼',
    # Videos
    '.mp4': '🎬', '.mkv': '🎬', '.avi': '🎬', '.mov': '🎬', '.wmv': '🎬',
    '.flv': '🎬', '.webm': '🎬', '.m4v': '🎬', '.3gp': '🎬', '.ts': '🎬',
    '.mts': '🎬', '.m2ts': '🎬', '.vob': '🎬', '.mpg': '🎬', '.mpeg': '🎬',
    # Audio
    '.mp3': '🎵', '.wav': '🎵', '.flac': '🎵', '.aac': '🎵', '.ogg': '🎵',
    '.m4a': '🎵', '.wma': '🎵', '.opus': '🎵', '.aiff': '🎵', '.mid': '🎵',
    '.midi': '🎵',
    # Documents
    '.pdf': '📋', '.doc': '📝', '.docx': '📝', '.odt': '📝', '.rtf': '📝',
    '.txt': '📄', '.md': '📄', '.rst': '📄', '.log': '📄',
    '.ppt': '📋', '.pptx': '📋', '.odp': '📋',
    # Spreadsheets / Data
    '.csv': '📊', '.xls': '📊', '.xlsx': '📊', '.ods': '📊', '.tsv': '📊',
    # Code / Config
    '.py': '🐍', '.js': '📜', '.ts': '📜', '.jsx': '📜', '.tsx': '📜',
    '.html': '🌐', '.htm': '🌐', '.css': '🎨', '.scss': '🎨', '.sass': '🎨',
    '.json': '📜', '.xml': '📜', '.yaml': '📜', '.yml': '📜',
    '.ini': '⚙', '.cfg': '⚙', '.conf': '⚙', '.toml': '⚙', '.env': '⚙',
    '.sh': '💻', '.bat': '💻', '.cmd': '💻', '.ps1': '💻',
    '.c': '💻', '.cpp': '💻', '.h': '💻', '.java': '💻', '.go': '💻',
    '.rs': '💻', '.rb': '💻', '.php': '💻', '.swift': '💻', '.kt': '💻',
    # Archives
    '.zip': '🗜', '.rar': '🗜', '.7z': '🗜', '.tar': '🗜', '.gz': '🗜',
    '.bz2': '🗜', '.xz': '🗜', '.lz4': '🗜', '.zst': '🗜',
    # Executables / Installers
    '.exe': '💾', '.dll': '💾', '.msi': '💾', '.apk': '💾', '.deb': '💾',
    '.rpm': '💾', '.dmg': '💾', '.iso': '💾', '.img': '💾',
    # Databases
    '.db': '🗃', '.sqlite': '🗃', '.sqlite3': '🗃', '.sql': '🗃', '.mdb': '🗃',
    # Fonts
    '.ttf': '🔤', '.otf': '🔤', '.woff': '🔤', '.woff2': '🔤', '.eot': '🔤',
}

def get_file_type_str(filepath: str) -> str:
    """Return an emoji icon + lowercase extension string for display."""
    _, ext = os.path.splitext(filepath)
    ext = ext.lower()
    icon = FILE_TYPE_ICONS.get(ext, '📦')
    return f"{icon} {ext}" if ext else "📦"


# ── ScrollableFrame ────────────────────────────────────────────────────────────
class ScrollableFrame(ttk.Frame):
    """Canvas-backed scrollable container for the details pane."""

    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)

        self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.canvas.bind('<Configure>', self._on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        bbox = self.canvas.bbox("all")
        if bbox and bbox[3] - bbox[1] > self.canvas.winfo_height():
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


# ── MainWindow ─────────────────────────────────────────────────────────────────
class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Duplicate File Remover")
        self.geometry("1150x730")
        self.configure(bg=DARK_THEME['bg'])
        self.minsize(1050, 660)

        self.eval('tk::PlaceWindow . center')

        # Core state
        self.event_queue = queue.Queue()
        self.finder = None
        self.scanning = False
        self.scan_results = []
        self.selected_files = set()
        self.current_theme = "system"
        self.palette = DARK_THEME
        self._scan_start_time = 0.0
        self._elapsed_timer_id = None

        # Checkbox images (PIL-drawn, kept alive as instance attrs)
        self.unchecked_img = None
        self.checked_img = None
        self._generate_checkbox_images()

        self._create_header_bar()

        self.container = tk.Frame(self, bg=DARK_THEME['bg'])
        self.container.pack(fill="both", expand=True, padx=20, pady=(5, 20))

        self.screens = {}
        for F in (SetupScreen, ProgressScreen, ResultsScreen):
            name = F.__name__
            screen = F(parent=self.container, controller=self)
            self.screens[name] = screen
            screen.grid(row=0, column=0, sticky="nsew")

        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        self.apply_theme("system")
        self.show_screen("SetupScreen")

    # ── Checkbox images ────────────────────────────────────────────────────────

    def _generate_checkbox_images(self):
        img_un = Image.new("RGBA", (14, 14), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img_un)
        draw.rounded_rectangle([0, 0, 13, 13], radius=2, outline=(140, 140, 140), width=1, fill=(255, 255, 255, 0))
        self.unchecked_img = ImageTk.PhotoImage(img_un)

        img_ch = Image.new("RGBA", (14, 14), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img_ch)
        draw.rounded_rectangle([0, 0, 13, 13], radius=2, outline=(0, 120, 212), width=1, fill=(0, 120, 212))
        draw.line([(3, 6), (6, 9), (10, 3)], fill=(255, 255, 255), width=2)
        self.checked_img = ImageTk.PhotoImage(img_ch)

    # ── Header bar ────────────────────────────────────────────────────────────

    def _create_header_bar(self):
        self.header_frame = tk.Frame(self, bg=DARK_THEME['bg'], height=45)
        self.header_frame.pack(fill="x", padx=20, pady=(15, 5))

        tk.Label(self.header_frame, text="📁 Windows Duplicate Remover",
                 font=("Segoe UI", 12, "bold"),
                 fg=DARK_THEME['text'], bg=DARK_THEME['bg']).pack(side="left")

        toggle_wrapper = tk.Frame(self.header_frame, bg=DARK_THEME['bg'])
        toggle_wrapper.pack(side="right")

        tk.Label(toggle_wrapper, text="Theme:", font=("Segoe UI", 9),
                 fg=DARK_THEME['muted_text'], bg=DARK_THEME['bg']).pack(side="left", padx=(0, 8))

        self.toggle_frame = tk.Frame(toggle_wrapper, bd=1, relief="solid")
        self.toggle_frame.pack(side="left")

        self.toggle_btns = {}
        for opt in ["Light", "Dark", "System"]:
            btn = tk.Button(self.toggle_frame, text=opt, font=("Segoe UI", 8, "bold"),
                            relief="flat", bd=0, padx=8, pady=3, cursor="hand2",
                            command=lambda t=opt: self.apply_theme(t.lower()))
            btn.pack(side="left")
            self.toggle_btns[opt.lower()] = btn

    # ── Theming ───────────────────────────────────────────────────────────────

    def apply_theme(self, theme_name: str):
        self.current_theme = theme_name
        if theme_name == "system":
            self.palette = DARK_THEME if utils.get_windows_system_theme() == "dark" else LIGHT_THEME
        else:
            self.palette = DARK_THEME if theme_name == "dark" else LIGHT_THEME

        self._update_ttk_styles(self.palette)
        self.configure(bg=self.palette['bg'])

        self.toggle_frame.configure(bg=self.palette['border'])
        for key, btn in self.toggle_btns.items():
            if key == theme_name:
                btn.configure(bg=self.palette['accent'], fg=self.palette['select_fg'],
                              activebackground=self.palette['accent_hover'],
                              activeforeground=self.palette['select_fg'])
            else:
                btn.configure(bg=self.palette['card_bg'], fg=self.palette['muted_text'],
                              activebackground=self.palette['card_bg'],
                              activeforeground=self.palette['text'])

        self._apply_theme_to_widget_tree(self, self.palette)
        if "ResultsScreen" in self.screens:
            self.screens["ResultsScreen"].update_theme(self.palette)

    def _update_ttk_styles(self, p):
        s = ttk.Style()
        s.theme_use("clam")

        s.configure("TFrame", background=p['bg'])
        s.configure("Card.TFrame", background=p['card_bg'], borderwidth=1,
                    relief="solid", bordercolor=p['border'])
        s.configure("TLabel", background=p['bg'], foreground=p['text'])

        s.configure("TButton", font=("Segoe UI", 10, "bold"), background=p['accent'],
                    foreground=p['select_fg'], borderwidth=0, padding=8)
        s.map("TButton",
              background=[("active", p['accent_hover']), ("disabled", p['border'])],
              foreground=[("disabled", p['muted_text'])])

        s.configure("Primary.TButton",   background=p['success'], foreground=p['select_fg'])
        s.map("Primary.TButton",   background=[("active", "#059669")])
        s.configure("Danger.TButton",    background=p['danger'],  foreground=p['select_fg'])
        s.map("Danger.TButton",    background=[("active", "#dc2626")])
        s.configure("Secondary.TButton", background=p['border'],  foreground=p['text'])
        s.map("Secondary.TButton", background=[("active", p['card_bg'])])

        s.configure("TCheckbutton", background=p['card_bg'], foreground=p['text'], font=("Segoe UI", 9))
        s.map("TCheckbutton",
              background=[("active", p['card_bg'])],
              foreground=[("active", p['text'])])

        s.configure("TProgressbar", troughcolor=p['bg'], background=p['accent'], borderwidth=0)

        s.configure("Treeview",
                    background=p['card_bg'], fieldbackground=p['card_bg'],
                    foreground=p['text'], rowheight=26, font=("Segoe UI", 9), borderwidth=0)
        s.configure("Treeview.Heading",
                    background=p['bg'], foreground=p['text'],
                    font=("Segoe UI", 10, "bold"), borderwidth=1, relief="flat")
        s.map("Treeview",
              background=[("selected", p['select_bg'])],
              foreground=[("selected", p['select_fg'])])

    def _apply_theme_to_widget_tree(self, widget, p):
        cls = widget.winfo_class()
        if cls == "Frame":
            if widget == self.header_frame:
                widget.configure(bg=p['bg'])
            elif widget == self.toggle_frame:
                widget.configure(bg=p['border'])
            else:
                bg = p['card_bg'] if getattr(widget, "custom_style", "") == "card" else p['bg']
                widget.configure(bg=bg)
        elif cls == "Label":
            sty = getattr(widget, "custom_style", "")
            bg  = p['card_bg'] if sty == "card" else p['bg']
            fg  = p['muted_text'] if sty == "muted" else p['text']
            widget.configure(bg=bg, fg=fg)
        elif cls == "Entry":
            widget.configure(bg=p['bg'], fg=p['text'],
                             insertbackground=p['text'], highlightcolor=p['accent'],
                             relief="solid", bd=1)
        elif cls == "Menu":
            widget.configure(bg=p['card_bg'], fg=p['text'],
                             activebackground=p['accent'], activeforeground=p['text'])
        elif cls == "Text":
            widget.configure(bg=p['bg'], fg=p['text'],
                             insertbackground=p['text'], relief="flat")
        elif cls == "Canvas":
            widget.configure(bg=p['card_bg'], highlightthickness=0)

        for child in widget.winfo_children():
            self._apply_theme_to_widget_tree(child, p)

    # ── Screen navigation ────────────────────────────────────────────────────

    def show_screen(self, screen_name: str):
        screen = self.screens[screen_name]
        screen.tkraise()
        screen.on_show()

    # ── Scan lifecycle ────────────────────────────────────────────────────────

    def start_scan(self, directory, match_name, match_ext, skip_sys,
                   min_size_bytes, exclude_patterns):
        self.scanning = True
        self.selected_files.clear()
        self._scan_start_time = time.monotonic()
        self.event_queue = queue.Queue()   # reset to flush stale events

        self.show_screen("ProgressScreen")
        self._start_elapsed_ticker()

        self.finder = DuplicateFinderEngine(
            target_dir=directory,
            event_queue=self.event_queue,
            match_by_name=match_name,
            match_by_ext=match_ext,
            skip_system_files=skip_sys,
            min_size_bytes=min_size_bytes,
            exclude_patterns=exclude_patterns,
        )
        self.finder.start()
        self.after(50, self.poll_queue)

    def _start_elapsed_ticker(self):
        if self._elapsed_timer_id:
            self.after_cancel(self._elapsed_timer_id)
        self._tick_elapsed()

    def _tick_elapsed(self):
        if not self.scanning:
            return
        elapsed = int(time.monotonic() - self._scan_start_time)
        m, s = divmod(elapsed, 60)
        self.screens["ProgressScreen"].update_elapsed(f"{m:02d}:{s:02d}")
        self._elapsed_timer_id = self.after(1000, self._tick_elapsed)

    def cancel_scan(self):
        if self.finder:
            self.finder.cancel()

    def poll_queue(self):
        if not self.scanning:
            return
        try:
            while True:
                event_type, data = self.event_queue.get_nowait()
                self.handle_event(event_type, data)
                self.event_queue.task_done()
        except queue.Empty:
            pass
        if self.scanning:
            self.after(50, self.poll_queue)

    def handle_event(self, event_type, data):
        ps = self.screens["ProgressScreen"]

        if event_type == 'SCAN_START':
            ps.on_discovery_phase()
        elif event_type == 'SCAN_DIR':
            ps.update_current_dir(data)
        elif event_type == 'SCAN_FILE_COUNT':
            ps.update_file_count(data)
        elif event_type == 'HASH_START':
            ps.on_hashing_phase(data)
        elif event_type == 'HASH_PROGRESS':
            ps.update_hash_progress(data[0], data[1])
        elif event_type == 'COMPARING':
            ps.update_phase("Analyzing matching structures...", 95)
        elif event_type == 'FINISHED':
            self.scanning = False
            self.scan_results = data
            if data:
                self.show_screen("ResultsScreen")
            else:
                # No duplicates — go back to setup with a friendly banner
                scanned = ps.get_scanned_count()
                self.show_screen("SetupScreen")
                self.screens["SetupScreen"].show_empty_state(scanned)
        elif event_type == 'CANCELLED':
            self.scanning = False
            messagebox.showinfo("Scan Cancelled", "The scan was successfully cancelled.")
            self.show_screen("SetupScreen")
        elif event_type == 'ERROR':
            self.scanning = False
            messagebox.showerror("Scan Error", f"An error occurred during scanning:\n{data}")
            self.show_screen("SetupScreen")


# ── SetupScreen ────────────────────────────────────────────────────────────────
class SetupScreen(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.configure(style="TFrame")
        self._empty_banner = None

        title_lbl = tk.Label(self, text="Scan New Directory", font=("Segoe UI", 15, "bold"))
        title_lbl.custom_style = "title"
        title_lbl.pack(anchor="w", pady=(5, 2))

        sub = tk.Label(self, text="Configure matching rules to find redundant files wasting disk space",
                       font=("Segoe UI", 9))
        sub.custom_style = "muted"
        sub.pack(anchor="w", pady=(0, 10))

        # ── Folder selector card ───────────────────────────────────────────────
        path_card = ttk.Frame(self, style="Card.TFrame", padding=12)
        path_card.custom_style = "card"
        path_card.pack(fill="x", pady=5)

        lbl = tk.Label(path_card, text="Select Target Folder", font=("Segoe UI", 10, "bold"))
        lbl.custom_style = "card"
        lbl.pack(anchor="w", pady=(0, 4))

        row = tk.Frame(path_card)
        row.custom_style = "card"
        row.pack(fill="x")

        self.path_var = tk.StringVar()
        self.path_entry = tk.Entry(row, textvariable=self.path_var, font=("Segoe UI", 10))
        self.path_entry.pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 10))

        ttk.Button(row, text="Browse...", command=self.browse_folder,
                   style="Secondary.TButton").pack(side="right")

        # ── Options card ───────────────────────────────────────────────────────
        opt_card = ttk.Frame(self, style="Card.TFrame", padding=12)
        opt_card.custom_style = "card"
        opt_card.pack(fill="x", pady=10)

        lbl2 = tk.Label(opt_card, text="Matching Rules & Filters", font=("Segoe UI", 10, "bold"))
        lbl2.custom_style = "card"
        lbl2.pack(anchor="w", pady=(0, 8))

        # Checkboxes
        checks = tk.Frame(opt_card)
        checks.custom_style = "card"
        checks.pack(fill="x", pady=(0, 8))

        self.match_name_var = tk.BooleanVar(value=False)
        self.match_ext_var  = tk.BooleanVar(value=False)
        self.skip_sys_var   = tk.BooleanVar(value=True)

        ttk.Checkbutton(checks, text="Match File Names (case-insensitive)",
                        variable=self.match_name_var).pack(side="left", padx=(0, 16))
        ttk.Checkbutton(checks, text="Match Extensions",
                        variable=self.match_ext_var).pack(side="left", padx=(0, 16))
        ttk.Checkbutton(checks, text="Ignore Hidden/System Files",
                        variable=self.skip_sys_var).pack(side="left")

        # Min size row
        size_row = tk.Frame(opt_card)
        size_row.custom_style = "card"
        size_row.pack(fill="x", pady=(0, 6))

        sz_lbl = tk.Label(size_row, text="Minimum file size:", font=("Segoe UI", 9))
        sz_lbl.custom_style = "card"
        sz_lbl.pack(side="left")

        self.min_size_var = tk.StringVar(value="0")
        tk.Entry(size_row, textvariable=self.min_size_var,
                 font=("Segoe UI", 9), width=8).pack(side="left", padx=(6, 4), ipady=2)

        self.size_unit_var = tk.StringVar(value="KB")
        ttk.OptionMenu(size_row, self.size_unit_var, "KB", "B", "KB", "MB", "GB").pack(side="left")

        sep = tk.Label(size_row, text="   ", font=("Segoe UI", 9))
        sep.custom_style = "card"
        sep.pack(side="left")

        hint = tk.Label(size_row,
                        text="(0 = scan all files regardless of size)",
                        font=("Segoe UI", 8))
        hint.custom_style = "muted"
        hint.pack(side="left")

        # Exclude folders row
        excl_row = tk.Frame(opt_card)
        excl_row.custom_style = "card"
        excl_row.pack(fill="x", pady=(0, 6))

        excl_lbl = tk.Label(excl_row,
                             text="Exclude folder names (comma-separated, supports * wildcards):",
                             font=("Segoe UI", 9))
        excl_lbl.custom_style = "card"
        excl_lbl.pack(anchor="w", pady=(0, 3))

        self.excl_var = tk.StringVar(value="node_modules, .venv, __pycache__, .git")
        tk.Entry(excl_row, textvariable=self.excl_var, font=("Segoe UI", 9)).pack(fill="x", ipady=2)

        # Info box
        info_row = tk.Frame(opt_card)
        info_row.custom_style = "card"
        info_row.pack(fill="x", pady=(8, 0))

        info_icon = tk.Label(info_row, text="ℹ", font=("Segoe UI", 11), fg=DARK_THEME['accent'])
        info_icon.custom_style = "card"
        info_icon.pack(side="left", anchor="n", padx=(0, 5))

        info_txt = tk.Label(
            info_row,
            text=("By default, duplicates are found strictly by file size + byte-level content hash. "
                  "Optional rules further restrict matches to same name or extension. "
                  "Min size and folder exclusions reduce noise from tiny or generated files."),
            font=("Segoe UI", 9), justify="left", wrap=700)
        info_txt.custom_style = "muted"
        info_txt.pack(side="left", fill="x", expand=True)

        # Scan button
        self.scan_btn = ttk.Button(self, text="Scan Directory 🔍",
                                    command=self.start_scan, style="Primary.TButton")
        self.scan_btn.pack(anchor="e", pady=10)

    # Monkey-patch helper so the Label is created, packed, and custom_style set in one shot
    def _label(self, parent, text, font, style_key="normal", **kw):
        lbl = tk.Label(parent, text=text, font=font, **kw)
        lbl.custom_style = style_key
        return lbl

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.path_var.set(os.path.normpath(folder))

    def _get_min_size_bytes(self) -> int:
        try:
            val = float(self.min_size_var.get())
            multipliers = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3}
            return int(val * multipliers.get(self.size_unit_var.get(), 1024))
        except ValueError:
            return 0

    def _get_exclude_patterns(self) -> list:
        raw = self.excl_var.get().strip()
        if not raw:
            return []
        return [p.strip() for p in raw.split(",") if p.strip()]

    def start_scan(self):
        path = self.path_var.get().strip()
        if not path:
            messagebox.showwarning("Validation Error", "Please select a target folder to scan.")
            return
        if not os.path.exists(path) or not os.path.isdir(path):
            messagebox.showerror("Error", "The specified folder does not exist or is not a directory.")
            return
        self._hide_banner()
        self.controller.start_scan(
            directory=path,
            match_name=self.match_name_var.get(),
            match_ext=self.match_ext_var.get(),
            skip_sys=self.skip_sys_var.get(),
            min_size_bytes=self._get_min_size_bytes(),
            exclude_patterns=self._get_exclude_patterns(),
        )

    def show_empty_state(self, scanned_count: int):
        """Show a friendly 'no duplicates found' banner."""
        self._hide_banner()
        frame = tk.Frame(self, bd=1, relief="solid")
        frame.custom_style = "card"
        frame.pack(fill="x", pady=8)
        self._empty_banner = frame

        icon_lbl = tk.Label(frame, text="✅", font=("Segoe UI", 20), padx=12, pady=8)
        icon_lbl.custom_style = "card"
        icon_lbl.pack(side="left")

        text_frame = tk.Frame(frame)
        text_frame.custom_style = "card"
        text_frame.pack(side="left", fill="x", expand=True, pady=8)

        title = tk.Label(text_frame, text="No duplicate files found",
                         font=("Segoe UI", 11, "bold"))
        title.custom_style = "card"
        title.pack(anchor="w")

        sub = tk.Label(text_frame,
                       text=f"All {scanned_count:,} scanned files are unique. Great — no wasted space!",
                       font=("Segoe UI", 9))
        sub.custom_style = "muted"
        sub.pack(anchor="w")

        # Re-apply theme to the new banner
        self.controller._apply_theme_to_widget_tree(frame, self.controller.palette)

    def _hide_banner(self):
        if self._empty_banner:
            self._empty_banner.destroy()
            self._empty_banner = None

    def on_show(self):
        pass


# ── ProgressScreen ─────────────────────────────────────────────────────────────
class ProgressScreen(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.configure(style="TFrame")
        self._scanned_count = 0
        self.total_to_hash = 0

        self.title_lbl = tk.Label(self, text="Scanning Files...", font=("Segoe UI", 15, "bold"))
        self.title_lbl.custom_style = "title"
        self.title_lbl.pack(anchor="w", pady=(5, 2))

        self.phase_lbl = tk.Label(self, text="Gathering directory hierarchy...", font=("Segoe UI", 9))
        self.phase_lbl.custom_style = "muted"
        self.phase_lbl.pack(anchor="w", pady=(0, 15))

        card = ttk.Frame(self, style="Card.TFrame", padding=15)
        card.custom_style = "card"
        card.pack(fill="both", expand=True, pady=5)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(card, variable=self.progress_var,
                                             maximum=100, mode="indeterminate")
        self.progress_bar.pack(fill="x", pady=10)

        self.percentage_lbl = tk.Label(card, text="Discovering files...", font=("Segoe UI", 11, "bold"))
        self.percentage_lbl.custom_style = "card"
        self.percentage_lbl.pack(anchor="e")

        self.current_action_lbl = tk.Label(card, text="Indexing file structures...",
                                            font=("Segoe UI", 9, "italic"))
        self.current_action_lbl.custom_style = "muted"
        self.current_action_lbl.pack(fill="x", pady=(10, 5))

        stats_row = tk.Frame(card)
        stats_row.custom_style = "card"
        stats_row.pack(fill="x", pady=5)

        self.total_files_lbl = tk.Label(stats_row, text="Files Found: 0", font=("Segoe UI", 10, "bold"))
        self.total_files_lbl.custom_style = "card"
        self.total_files_lbl.pack(side="left")

        self.elapsed_lbl = tk.Label(stats_row, text="Elapsed: 00:00", font=("Segoe UI", 9))
        self.elapsed_lbl.custom_style = "muted"
        self.elapsed_lbl.pack(side="right")

        self.cancel_btn = ttk.Button(self, text="Cancel Scan ⏹",
                                      command=self.controller.cancel_scan, style="Danger.TButton")
        self.cancel_btn.pack(anchor="e", pady=15)

    def on_show(self):
        self.progress_var.set(0)
        self.percentage_lbl.configure(text="Discovering files...")
        self.phase_lbl.configure(text="Initializing engine...")
        self.current_action_lbl.configure(text="")
        self.total_files_lbl.configure(text="Files Found: 0")
        self.elapsed_lbl.configure(text="Elapsed: 00:00")
        self.total_to_hash = 0
        self._scanned_count = 0

    def on_discovery_phase(self):
        """Switch progress bar to indeterminate bounce during file discovery."""
        self.progress_bar.configure(mode="indeterminate")
        self.progress_bar.start(12)
        self.phase_lbl.configure(text="Discovering files recursively...")
        self.percentage_lbl.configure(text="Discovering...")

    def on_hashing_phase(self, total_files: int):
        """Switch progress bar to determinate once hashing starts."""
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
        self.total_to_hash = total_files
        self.update_phase("Computing content hashes...", 0)
        self.total_files_lbl.configure(text=f"Files to Compare: {total_files:,}")

    def get_scanned_count(self) -> int:
        return self._scanned_count

    def update_phase(self, text: str, pct: Optional[float] = None):
        self.phase_lbl.configure(text=text)
        if pct is not None:
            self.progress_var.set(pct)
            self.percentage_lbl.configure(text=f"{int(pct)}%")

    def update_current_dir(self, directory: str):
        display = ("..." + directory[-82:]) if len(directory) > 85 else directory
        self.current_action_lbl.configure(text=f"Searching: {display}")

    def update_file_count(self, count: int):
        self._scanned_count = count
        self.total_files_lbl.configure(text=f"Files Found: {count:,}")

    def update_hash_progress(self, current: int, filepath: str):
        if self.total_to_hash > 0:
            pct = (current / self.total_to_hash) * 100
            self.progress_var.set(pct)
            self.percentage_lbl.configure(text=f"{int(pct)}%")
        display = ("..." + filepath[-82:]) if len(filepath) > 85 else filepath
        self.current_action_lbl.configure(text=f"Hashing [{current}/{self.total_to_hash}]: {display}")

    def update_elapsed(self, time_str: str):
        self.elapsed_lbl.configure(text=f"Elapsed: {time_str}")


# ── ResultsScreen ──────────────────────────────────────────────────────────────
class ResultsScreen(ttk.Frame):
    """
    Treeview values layout for child (file) rows:
      values[0] = formatted_size   → "size"   column (#1)
      values[1] = mtime_str        → "date"   column (#2)
      values[2] = type icon+ext    → "type"   column (#3)
      values[3] = "☐" or "☑"     → "status" column (#4)
      values[4] = full filepath    → hidden, no column
    """
    _FP   = 4   # filepath index
    _CB   = 3   # checkbox index
    _SEL  = "#4"  # Treeview column id for the "Select" column

    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.configure(style="TFrame")

        self._preview_image_ref = None
        self.preview_visible = True
        self._sort_col = "size"
        self._sort_dir = "desc"

        # ── Header bar ─────────────────────────────────────────────────────────
        top_bar = tk.Frame(self)
        top_bar.pack(fill="x", pady=(5, 5))

        title = tk.Label(top_bar, text="Scan Results", font=("Segoe UI", 15, "bold"))
        title.custom_style = "title"
        title.pack(side="left")

        self.preview_toggle_btn = ttk.Button(top_bar, text="Hide Details Panel ◀",
                                              command=self.toggle_preview_pane,
                                              style="Secondary.TButton")
        self.preview_toggle_btn.pack(side="right")

        self.summary_lbl = tk.Label(self, text="Calculating duplicates...", font=("Segoe UI", 9))
        self.summary_lbl.custom_style = "muted"
        self.summary_lbl.pack(anchor="w", pady=(0, 8))

        # ── Body (treeview + preview) ──────────────────────────────────────────
        self.body_container = tk.Frame(self)
        self.body_container.pack(fill="both", expand=True)

        # Left: treeview
        self.left_pane = ttk.Frame(self.body_container, style="Card.TFrame")
        self.left_pane.custom_style = "card"
        self.left_pane.pack(side="left", fill="both", expand=True, padx=(0, 10))

        self.tree = ttk.Treeview(self.left_pane,
                                  columns=("size", "date", "type", "status"),
                                  selectmode="browse")

        self.tree.heading("#0",     text="Path / File",    anchor="w")
        self.tree.heading("size",   text="Size ▼",         anchor="e",
                          command=lambda: self.sort_by("size"))
        self.tree.heading("date",   text="Date Modified",  anchor="w",
                          command=lambda: self.sort_by("date"))
        self.tree.heading("type",   text="Type",           anchor="w")
        self.tree.heading("status", text="Select",         anchor="center")

        self.tree.column("#0",     width=310, anchor="w", minwidth=180)
        self.tree.column("size",   width=80,  anchor="e", minwidth=60)
        self.tree.column("date",   width=128, anchor="w", minwidth=100)
        self.tree.column("type",   width=90,  anchor="w", minwidth=65)
        self.tree.column("status", width=52,  anchor="center", minwidth=44)

        vsb = ttk.Scrollbar(self.left_pane, orient="vertical",   command=self.tree.yview)
        hsb = ttk.Scrollbar(self.left_pane, orient="horizontal",  command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        self.left_pane.grid_rowconfigure(0, weight=1)
        self.left_pane.grid_columnconfigure(0, weight=1)

        self.tree.bind("<Button-1>",        self.on_click_tree)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        self.tree.bind("<Button-3>",        self.show_context_menu)
        self.tree.bind("<space>",           lambda e: self.toggle_selected_row())

        # Context menu
        self.ctx = tk.Menu(self, tearoff=0)
        self.ctx.add_command(label="Open File",             command=self.open_file)
        self.ctx.add_command(label="Open Folder Location",  command=self.open_folder)
        self.ctx.add_separator()
        self.ctx.add_command(label="Toggle Selection",      command=self.toggle_selected_row)
        self.ctx.add_separator()
        self.ctx.add_command(label="Select All in Group",   command=self.select_all_in_group)
        self.ctx.add_command(label="Deselect All in Group", command=self.deselect_all_in_group)

        # Right: preview pane
        self.preview_pane = ttk.Frame(self.body_container, style="Card.TFrame", width=280)
        self.preview_pane.custom_style = "card"
        self.preview_pane.pack(side="right", fill="both", expand=False)
        self.preview_pane.pack_propagate(False)

        self.scroll_preview = ScrollableFrame(self.preview_pane)
        self.scroll_preview.pack(fill="both", expand=True)

        self.inner_preview = self.scroll_preview.scrollable_frame
        self.inner_preview.custom_style = "card"

        self.preview_title = tk.Label(self.inner_preview, text="File Details",
                                       font=("Segoe UI", 11, "bold"))
        self.preview_title.custom_style = "card"
        self.preview_title.pack(anchor="w", pady=(0, 10))

        self.media_frame = tk.Frame(self.inner_preview, bd=1, relief="solid",
                                     bg="#000000", height=160)
        self.media_frame.pack(fill="x", pady=(0, 10))
        self.media_frame.pack_propagate(False)

        self.media_lbl = tk.Label(self.media_frame, text="No Media Preview",
                                   font=("Segoe UI", 9, "italic"), fg="#888888", bg="#000000")
        self.media_lbl.pack(expand=True, fill="both")

        self.snippet_lbl = tk.Label(self.inner_preview, text="Text Snippet:",
                                     font=("Segoe UI", 9, "bold"))
        self.snippet_lbl.custom_style = "card"

        self.snippet_frame = tk.Frame(self.inner_preview, bd=1, relief="solid")
        self.snippet_text = tk.Text(self.snippet_frame, height=7,
                                     font=("Consolas", 8), wrap="char")
        self.snippet_vsb = ttk.Scrollbar(self.snippet_frame, orient="vertical",
                                          command=self.snippet_text.yview)
        self.snippet_text.configure(yscrollcommand=self.snippet_vsb.set)
        self.snippet_text.pack(side="left", fill="both", expand=True)
        self.snippet_vsb.pack(side="right", fill="y")

        self.meta_frame = tk.Frame(self.inner_preview)
        self.meta_frame.custom_style = "card"
        self.meta_frame.pack(fill="both", expand=True, pady=(5, 0))

        self.meta_lbl = tk.Label(self.meta_frame,
                                  text="Select a file to inspect its content.",
                                  font=("Segoe UI", 9, "italic"),
                                  justify="left", anchor="nw", wrap=240)
        self.meta_lbl.custom_style = "card"
        self.meta_lbl.pack(fill="both", expand=True)

        # ── Action bar ──────────────────────────────────────────────────────────
        act = tk.Frame(self)
        act.pack(fill="x", pady=(10, 5))

        qs_lbl = tk.Label(act, text="Quick Select:", font=("Segoe UI", 9, "bold"))
        qs_lbl.custom_style = "muted"
        qs_lbl.pack(side="left", padx=(0, 8))

        for label, cmd in [
            ("Keep Oldest",   lambda: self.select_all_but_one("oldest")),
            ("Keep Newest",   lambda: self.select_all_but_one("newest")),
            ("Keep Largest",  lambda: self.select_all_but_one("largest")),
            ("Keep Smallest", lambda: self.select_all_but_one("smallest")),
            ("Clear Select",  self.deselect_all),
        ]:
            ttk.Button(act, text=label, command=cmd,
                       style="Secondary.TButton").pack(side="left", padx=3)

        ttk.Button(act, text="Export... 📤", command=self.export_results,
                   style="Secondary.TButton").pack(side="right", padx=3)

        # ── Bottom bar ──────────────────────────────────────────────────────────
        bot = tk.Frame(self)
        bot.pack(fill="x", pady=(10, 0))

        ttk.Button(bot, text="⬅ Scan Another Folder",
                   command=self.go_back, style="Secondary.TButton").pack(side="left")

        self.delete_btn = ttk.Button(bot, text="Delete Selected (0 files) 🗑️",
                                      command=self.delete_selected, style="Danger.TButton")
        self.delete_btn.pack(side="right")

    # ── Theme ──────────────────────────────────────────────────────────────────

    def update_theme(self, p):
        self.tree.tag_configure("checked",
                                background=p['checked_bg'],      foreground=p['text'])
        self.tree.tag_configure("unchecked",
                                background=p['card_bg'],          foreground=p['text'])
        self.tree.tag_configure("group_header",
                                background=p['group_header_bg'],  foreground=p['text'],
                                font=("Segoe UI", 9, "bold"))

    # ── Populate results ───────────────────────────────────────────────────────

    def on_show(self):
        self.tree.delete(*self.tree.get_children())
        self.clear_preview()
        self.update_theme(self.controller.palette)

        results = self.controller.scan_results
        if not results:
            self.summary_lbl.configure(text="No duplicate files found.")
            self.update_delete_button_state()
            return

        total_groups = len(results)
        total_dup_files = 0
        total_redundant_size = 0

        for index, group in enumerate(self._sorted_results(results)):
            files = group['files']
            group_size = group['size']

            total_dup_files += len(files) - 1
            total_redundant_size += (len(files) - 1) * group_size

            try:
                base_path = os.path.commonpath(files)
            except Exception:
                base_path = ""

            fmt_size = utils.format_size(group_size)
            if base_path:
                hdr_text = (f"Group #{index+1}  ·  Base: {base_path}"
                            f"  ·  {len(files)} files  ({fmt_size} each)")
            else:
                hdr_text = f"Group #{index+1}  ·  {fmt_size} each  ·  {len(files)} files"

            hdr_id = self.tree.insert("", "end", text=hdr_text,
                                      values=(fmt_size, "", "", ""),
                                      open=True, tags=("group_header",))

            for filepath in files:
                mtime_str = ""
                try:
                    mtime_str = datetime.fromtimestamp(
                        os.path.getmtime(filepath)).strftime("%Y-%m-%d %H:%M")
                except Exception:
                    pass

                display_path = os.path.relpath(filepath, base_path) if base_path else filepath
                type_str = get_file_type_str(filepath)

                # values: [size, date, type, checkbox, filepath(hidden)]
                self.tree.insert(hdr_id, "end",
                                  text=display_path,
                                  values=(fmt_size, mtime_str, type_str, "☐", filepath),
                                  tags=("unchecked",))

        self.summary_lbl.configure(
            text=(f"Found {total_groups:,} duplicate groups  ·  "
                  f"Redundant: {total_dup_files:,} files  ·  "
                  f"{utils.format_size(total_redundant_size)} wasting space")
        )
        self._update_sort_indicators()
        self.update_delete_button_state()

    # ── Sorting ────────────────────────────────────────────────────────────────

    def _sorted_results(self, results):
        reverse = (self._sort_dir == "desc")
        if self._sort_col == "size":
            return sorted(results, key=lambda g: g['size'], reverse=reverse)
        if self._sort_col == "date":
            def _max_mtime(g):
                t = []
                for fp in g['files']:
                    try: t.append(os.path.getmtime(fp))
                    except Exception: t.append(0)
                return max(t) if t else 0
            return sorted(results, key=_max_mtime, reverse=reverse)
        return list(results)

    def sort_by(self, col: str):
        if self._sort_col == col:
            self._sort_dir = "asc" if self._sort_dir == "desc" else "desc"
        else:
            self._sort_col = col
            self._sort_dir = "desc"
        self.on_show()

    def _update_sort_indicators(self):
        for col, base in (("size", "Size"), ("date", "Date Modified")):
            arrow = (" ▼" if self._sort_dir == "desc" else " ▲") if col == self._sort_col else ""
            self.tree.heading(col, text=base + arrow)

    # ── Delete button state ────────────────────────────────────────────────────

    def update_delete_button_state(self):
        n = len(self.controller.selected_files)
        if n > 0:
            self.delete_btn.configure(
                text=f"Send Selected to Recycle Bin ({n} files) 🗑️", state="normal")
        else:
            self.delete_btn.configure(text="Delete Selected (0 files) 🗑️", state="disabled")

    # ── Click / keyboard ───────────────────────────────────────────────────────

    def on_click_tree(self, event):
        item_id = self.tree.identify_row(event.y)
        if not item_id or self.tree.parent(item_id) == "":
            return
        if self.tree.identify_column(event.x) == self._SEL:
            self.toggle_row_selection(item_id)

    def toggle_row_selection(self, item_id: str):
        vals = list(self.tree.item(item_id, "values"))
        if len(vals) <= self._FP:
            return
        filepath = vals[self._FP]
        tags = self.tree.item(item_id, "tags")
        status = tags[0] if tags else "unchecked"

        if status == "unchecked":
            vals[self._CB] = "☑"
            self.tree.item(item_id, values=vals, tags=("checked",))
            self.controller.selected_files.add(filepath)
        else:
            vals[self._CB] = "☐"
            self.tree.item(item_id, values=vals, tags=("unchecked",))
            self.controller.selected_files.discard(filepath)

        self.update_delete_button_state()

    def toggle_selected_row(self):
        for item_id in self.tree.selection():
            if self.tree.parent(item_id) != "":
                self.toggle_row_selection(item_id)

    # ── Context menu actions ───────────────────────────────────────────────────

    def _header_of(self, item_id: str) -> str:
        parent = self.tree.parent(item_id)
        return item_id if parent == "" else parent

    def select_all_in_group(self):
        sel = self.tree.selection()
        if not sel:
            return
        for child_id in self.tree.get_children(self._header_of(sel[0])):
            tags = self.tree.item(child_id, "tags")
            if (tags and tags[0] == "unchecked") or not tags:
                self.toggle_row_selection(child_id)

    def deselect_all_in_group(self):
        sel = self.tree.selection()
        if not sel:
            return
        for child_id in self.tree.get_children(self._header_of(sel[0])):
            tags = self.tree.item(child_id, "tags")
            if tags and tags[0] == "checked":
                self.toggle_row_selection(child_id)

    def show_context_menu(self, event):
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return
        if item_id not in self.tree.selection():
            self.tree.selection_set(item_id)

        is_child = self.tree.parent(item_id) != ""
        state = "normal" if is_child else "disabled"
        for label in ("Open File", "Open Folder Location", "Toggle Selection"):
            self.ctx.entryconfig(label, state=state)
        self.ctx.post(event.x_root, event.y_root)

    def get_selected_file_path(self) -> Optional[str]:
        sel = self.tree.selection()
        if not sel:
            return None
        item_id = sel[0]
        if self.tree.parent(item_id) == "":
            return None
        vals = self.tree.item(item_id, "values")
        return vals[self._FP] if len(vals) > self._FP else None

    def open_file(self):
        path = self.get_selected_file_path()
        if path and os.path.exists(path):
            try:
                os.startfile(path)
            except Exception as e:
                messagebox.showerror("Error", f"Could not open file:\n{e}")

    def open_folder(self):
        path = self.get_selected_file_path()
        if path and os.path.exists(path):
            try:
                subprocess.Popen(f'explorer /select,"{path}"')
            except Exception as e:
                messagebox.showerror("Error", f"Could not open folder:\n{e}")

    def on_tree_select(self, event):
        path = self.get_selected_file_path()
        if not path:
            self.clear_preview()
        else:
            self.update_preview_pane(path)

    # ── Preview pane ───────────────────────────────────────────────────────────

    def toggle_preview_pane(self):
        if self.preview_visible:
            self.preview_pane.pack_forget()
            self.preview_toggle_btn.configure(text="Show Details Panel ▶")
            self.preview_visible = False
        else:
            self.preview_pane.pack(side="right", fill="both", expand=False)
            self.preview_toggle_btn.configure(text="Hide Details Panel ◀")
            self.preview_visible = True

    def clear_preview(self):
        self._preview_image_ref = None
        self.media_lbl.configure(image="", text="No Media Preview")
        self.snippet_lbl.pack_forget()
        self.snippet_frame.pack_forget()
        self.meta_lbl.configure(text="Select a file to inspect its content.",
                                 font=("Segoe UI", 9, "italic"))

    def update_preview_pane(self, filepath: str):
        self.clear_preview()
        if not os.path.exists(filepath):
            self.meta_lbl.configure(text="File does not exist or has been deleted.",
                                     font=("Segoe UI", 9, "italic"))
            return

        filename = os.path.basename(filepath)
        _, ext = os.path.splitext(filename)
        ext = ext.lower()
        icon = FILE_TYPE_ICONS.get(ext, '📦')

        try:
            size_b   = os.path.getsize(filepath)
            size_fmt = utils.format_size(size_b)
            mtime    = os.path.getmtime(filepath)
            mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            self.meta_lbl.configure(text=f"Error reading details:\n{e}")
            return

        self.meta_lbl.configure(
            text=(f"{icon}  {filename}\n\n"
                  f"Size:     {size_fmt}\n"
                  f"Modified: {mtime_str}\n"
                  f"Type:     {ext or 'unknown'}\n\n"
                  f"Full Path:\n{filepath}"),
            font=("Segoe UI", 9))

        IMG_EXTS  = {".png",".jpg",".jpeg",".gif",".bmp",".webp",".tiff",".tif",
                     ".ico",".heic",".psd",".xcf"}
        VID_EXTS  = {".mp4",".mkv",".avi",".mov",".wmv",".flv",".webm",".m4v",
                     ".3gp",".ts",".mts",".vob",".mpg",".mpeg"}
        TEXT_EXTS = {".txt",".py",".log",".json",".ini",".cfg",".xml",".html",".htm",
                     ".css",".md",".csv",".bat",".sh",".yaml",".yml",".toml",
                     ".rs",".go",".c",".cpp",".h",".js",".ts",".jsx",".tsx",".rb",".php"}

        if ext in IMG_EXTS:
            try:
                img = Image.open(filepath)
                img.thumbnail((240, 150))
                photo = ImageTk.PhotoImage(img)
                self.media_lbl.configure(image=photo, text="")
                self._preview_image_ref = photo
            except Exception as e:
                self.media_lbl.configure(text=f"Image preview error:\n{e}")

        elif ext in VID_EXTS:
            if OPENCV_AVAILABLE:
                try:
                    cap = cv2.VideoCapture(filepath)
                    if cap.isOpened():
                        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                        cap.set(cv2.CAP_PROP_POS_FRAMES, min(24, total // 2) if total > 0 else 0)
                        ok, frame = cap.read()
                        cap.release()
                        if ok:
                            img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                            img.thumbnail((240, 150))
                            photo = ImageTk.PhotoImage(img)
                            self.media_lbl.configure(image=photo, text="")
                            self._preview_image_ref = photo
                        else:
                            self.media_lbl.configure(text="🎬 Video\n(could not read frame)")
                    else:
                        self.media_lbl.configure(text="🎬 Video\n(could not open)")
                except Exception as e:
                    self.media_lbl.configure(text=f"🎬 Video\n(error: {e})")
            else:
                self.media_lbl.configure(text="🎬 Video File\n(install opencv-python for preview)")

        elif ext in TEXT_EXTS:
            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    snippet = "".join(f.readline() for _ in range(12))
                self.snippet_text.configure(state="normal")
                self.snippet_text.delete("1.0", tk.END)
                self.snippet_text.insert(tk.END, snippet)
                self.snippet_text.configure(state="disabled")
                self.media_lbl.configure(text="📝 Text Document")
                self.snippet_lbl.pack(after=self.media_frame, anchor="w", pady=(0, 2))
                self.snippet_frame.pack(after=self.snippet_lbl, fill="x", pady=(0, 5))
            except Exception:
                pass
        else:
            self.media_lbl.configure(text=f"{icon}  Binary / Resource File")

        self.controller._apply_theme_to_widget_tree(self.preview_pane, self.controller.palette)

    # ── Quick selects ──────────────────────────────────────────────────────────

    def select_all_but_one(self, keep: str = "oldest"):
        self.controller.selected_files.clear()

        for hdr_id in self.tree.get_children(""):
            children = self.tree.get_children(hdr_id)
            if not children:
                continue

            meta = []
            for child_id in children:
                vals = self.tree.item(child_id, "values")
                if len(vals) > self._FP:
                    fp = vals[self._FP]
                    try:
                        mtime = os.path.getmtime(fp)
                        size  = os.path.getsize(fp)
                    except Exception:
                        mtime, size = 0, 0
                    meta.append((child_id, fp, mtime, size))

            if not meta:
                continue

            if keep == "oldest":
                meta.sort(key=lambda x: x[2])
            elif keep == "newest":
                meta.sort(key=lambda x: x[2], reverse=True)
            elif keep == "largest":
                meta.sort(key=lambda x: x[3], reverse=True)
            elif keep == "smallest":
                meta.sort(key=lambda x: x[3])

            # Keep first item, mark rest for deletion
            keep_id, *del_items = meta

            v = list(self.tree.item(keep_id[0], "values"))
            if len(v) > self._CB:
                v[self._CB] = "☐"
            self.tree.item(keep_id[0], values=v, tags=("unchecked",))

            for item in del_items:
                v = list(self.tree.item(item[0], "values"))
                if len(v) > self._CB:
                    v[self._CB] = "☑"
                self.tree.item(item[0], values=v, tags=("checked",))
                self.controller.selected_files.add(item[1])

        self.update_delete_button_state()

    def deselect_all(self):
        self.controller.selected_files.clear()
        for hdr_id in self.tree.get_children(""):
            for child_id in self.tree.get_children(hdr_id):
                v = list(self.tree.item(child_id, "values"))
                if len(v) > self._CB:
                    v[self._CB] = "☐"
                self.tree.item(child_id, values=v, tags=("unchecked",))
        self.update_delete_button_state()

    # ── Export ─────────────────────────────────────────────────────────────────

    def export_results(self):
        results = self.controller.scan_results
        if not results:
            messagebox.showinfo("Export", "No results to export.")
            return

        path = filedialog.asksaveasfilename(
            title="Export Duplicate Report",
            defaultextension=".csv",
            filetypes=[("CSV file", "*.csv"), ("JSON file", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return

        try:
            if path.lower().endswith(".json"):
                rows = []
                for i, g in enumerate(results, 1):
                    for fp in g['files']:
                        try:
                            mt = datetime.fromtimestamp(os.path.getmtime(fp)).strftime("%Y-%m-%d %H:%M:%S")
                        except Exception:
                            mt = ""
                        rows.append({
                            "group": i,
                            "filepath": fp,
                            "size_bytes": g['size'],
                            "size_readable": utils.format_size(g['size']),
                            "date_modified": mt,
                            "extension": os.path.splitext(fp)[1].lower(),
                            "hash": g['hash'],
                        })
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump(rows, fh, indent=2, ensure_ascii=False)
            else:
                with open(path, "w", newline="", encoding="utf-8") as fh:
                    w = csv.writer(fh)
                    w.writerow(["Group", "File Path", "Size (bytes)", "Size",
                                "Date Modified", "Extension", "Hash"])
                    for i, g in enumerate(results, 1):
                        for fp in g['files']:
                            try:
                                mt = datetime.fromtimestamp(
                                    os.path.getmtime(fp)).strftime("%Y-%m-%d %H:%M:%S")
                            except Exception:
                                mt = ""
                            w.writerow([i, fp, g['size'], utils.format_size(g['size']),
                                        mt, os.path.splitext(fp)[1].lower(), g['hash']])

            messagebox.showinfo("Export Complete",
                                f"Results exported successfully to:\n{path}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Could not export results:\n{e}")

    # ── Delete selected ────────────────────────────────────────────────────────

    def delete_selected(self):
        selected = list(self.controller.selected_files)
        if not selected:
            return
        if not messagebox.askyesno(
                "Confirm Safe Deletion",
                f"Send {len(selected)} selected file(s) to the Recycle Bin?\n\n"
                "They can be restored if needed."):
            return

        if utils.send_to_recycle_bin(selected):
            messagebox.showinfo("Success",
                                f"{len(selected)} file(s) sent to the Recycle Bin.")
            for fp in selected:
                for g in self.controller.scan_results:
                    if fp in g['files']:
                        g['files'].remove(fp)
            self.controller.scan_results = [
                g for g in self.controller.scan_results if len(g['files']) >= 2]
            self.controller.selected_files.clear()
            self.on_show()
        else:
            messagebox.showerror("Deletion Error",
                                 "An error occurred. Please verify permissions.")

    def go_back(self):
        self.controller.show_screen("SetupScreen")
