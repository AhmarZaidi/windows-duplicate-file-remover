import os
import queue
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
from datetime import datetime
import winreg

from PIL import Image, ImageTk, ImageDraw

try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False

import duplicate_remover.utils as utils
from duplicate_remover.duplicate_finder import DuplicateFinderEngine

# Color Palettes
DARK_THEME = {
    'bg': '#1e1e1e',
    'card_bg': '#2d2d2d',
    'text': '#ffffff',
    'muted_text': '#aaaaaa',
    'border': '#3f3f3f',
    'accent': '#0078d4',          # Windows 11 Blue
    'accent_hover': '#106ebe',
    'success': '#107c41',         # Success Green
    'danger': '#a80000',          # Danger Red
    'select_bg': '#0078d4',
    'select_fg': '#ffffff',
    'checked_bg': '#2a3a4e',       # Dark blue-gray checked row highlight
    'group_header_bg': '#252525', # Dark group divider background
}

LIGHT_THEME = {
    'bg': '#f3f3f3',
    'card_bg': '#ffffff',
    'text': '#000000',
    'muted_text': '#666666',
    'border': '#d2d2d2',
    'accent': '#0078d4',
    'accent_hover': '#106ebe',
    'success': '#107c41',
    'danger': '#a80000',
    'select_bg': '#0078d4',
    'select_fg': '#ffffff',
    'checked_bg': '#e0f2fe',       # Soft light blue checked row highlight
    'group_header_bg': '#e5e5e5', # Light group divider background
}

class ScrollableFrame(ttk.Frame):
    """
    A generic scrollable container using Canvas. Perfect for details panes that can overflow.
    """
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        
        self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas)
        
        # Configure scrollregion dynamically on size configuration
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )
        
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        # Auto-adjust frame width to fill canvas
        self.canvas.bind('<Configure>', self._on_canvas_configure)
        
        # Bind mousewheel scroll
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        bbox = self.canvas.bbox("all")
        canvas_height = self.canvas.winfo_height()
        if bbox and bbox[3] - bbox[1] > canvas_height:
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

# --- MAIN APP VIEW ---

class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Duplicate File Remover")
        self.geometry("1000x700")
        self.configure(bg=DARK_THEME['bg'])
        self.minsize(950, 650)
        
        self.eval('tk::PlaceWindow . center')
        
        # Core State
        self.event_queue = queue.Queue()
        self.finder = None
        self.scanning = False
        self.scan_results = []
        self.selected_files = set()
        self.current_theme = "system"
        self.palette = DARK_THEME
        
        # Checkbox assets (drawn programmatically)
        self.unchecked_img = None
        self.checked_img = None
        self._generate_checkbox_images()
        
        # Persistent header & controls
        self._create_header_bar()
        
        # Switching Screens container
        self.container = tk.Frame(self, bg=DARK_THEME['bg'])
        self.container.pack(fill="both", expand=True, padx=20, pady=(5, 20))
        
        self.screens = {}
        for F in (SetupScreen, ProgressScreen, ResultsScreen):
            screen_name = F.__name__
            screen = F(parent=self.container, controller=self)
            self.screens[screen_name] = screen
            screen.grid(row=0, column=0, sticky="nsew")
            
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)
        
        self.apply_theme("system")
        self.show_screen("SetupScreen")

    def _generate_checkbox_images(self):
        """Generates checkbox image assets at runtime using PIL."""
        img_un = Image.new("RGBA", (14, 14), (255, 255, 255, 0))
        draw_un = ImageDraw.Draw(img_un)
        draw_un.rounded_rectangle([0, 0, 13, 13], radius=2, outline=(140, 140, 140), width=1, fill=(255, 255, 255, 0))
        self.unchecked_img = ImageTk.PhotoImage(img_un)
        
        img_ch = Image.new("RGBA", (14, 14), (255, 255, 255, 0))
        draw_ch = ImageDraw.Draw(img_ch)
        draw_ch.rounded_rectangle([0, 0, 13, 13], radius=2, outline=(0, 120, 212), width=1, fill=(0, 120, 212))
        draw_ch.line([(3, 6), (6, 9), (10, 3)], fill=(255, 255, 255), width=2)
        self.checked_img = ImageTk.PhotoImage(img_ch)

    def _create_header_bar(self):
        """Creates persistent title and theme toggle buttons."""
        self.header_frame = tk.Frame(self, bg=DARK_THEME['bg'], height=45)
        self.header_frame.pack(fill="x", padx=20, pady=(15, 5))
        
        title_lbl = tk.Label(self.header_frame, text="📁 Windows Duplicate Remover", 
                             font=("Segoe UI", 12, "bold"), fg=DARK_THEME['text'], bg=DARK_THEME['bg'])
        title_lbl.pack(side="left")
        
        toggle_wrapper = tk.Frame(self.header_frame, bg=DARK_THEME['bg'])
        toggle_wrapper.pack(side="right")
        
        theme_lbl = tk.Label(toggle_wrapper, text="Theme:", font=("Segoe UI", 9), 
                             fg=DARK_THEME['muted_text'], bg=DARK_THEME['bg'])
        theme_lbl.pack(side="left", padx=(0, 8))
        
        # Horizontal Segmented Toggle Frame
        self.toggle_frame = tk.Frame(toggle_wrapper, bd=1, relief="solid")
        self.toggle_frame.pack(side="left")
        
        self.toggle_btns = {}
        for theme_opt in ["Light", "Dark", "System"]:
            btn = tk.Button(self.toggle_frame, text=theme_opt, font=("Segoe UI", 8, "bold"),
                            relief="flat", bd=0, padx=8, pady=3, cursor="hand2",
                            command=lambda t=theme_opt: self.select_toggle_theme(t))
            btn.pack(side="left")
            self.toggle_btns[theme_opt.lower()] = btn

    def select_toggle_theme(self, theme_opt):
        self.apply_theme(theme_opt.lower())

    def apply_theme(self, theme_name):
        self.current_theme = theme_name
        
        if theme_name == "system":
            sys_theme = utils.get_windows_system_theme()
            self.palette = DARK_THEME if sys_theme == "dark" else LIGHT_THEME
        else:
            self.palette = DARK_THEME if theme_name == "dark" else LIGHT_THEME
            
        self._update_ttk_styles(self.palette)
        self.configure(bg=self.palette['bg'])
        
        # Update Segmented toggle buttons highlight states
        self.toggle_frame.configure(bg=self.palette['border'], highlightbackground=self.palette['border'])
        for key, btn in self.toggle_btns.items():
            if key == theme_name:
                btn.configure(bg=self.palette['accent'], fg=self.palette['select_fg'], 
                              activebackground=self.palette['accent_hover'], activeforeground=self.palette['select_fg'])
            else:
                btn.configure(bg=self.palette['card_bg'], fg=self.palette['muted_text'],
                              activebackground=self.palette['card_bg'], activeforeground=self.palette['text'])
        
        # Apply palette recursively to standard widgets
        self._apply_theme_to_widget_tree(self, self.palette)
        
        # Explicitly update ResultsScreen tree tags if it exists
        if "ResultsScreen" in self.screens:
            self.screens["ResultsScreen"].update_theme(self.palette)

    def _update_ttk_styles(self, palette):
        style = ttk.Style()
        style.theme_use("clam")
        
        style.configure("TFrame", background=palette['bg'])
        style.configure("Card.TFrame", background=palette['card_bg'], borderwidth=1, relief="solid", bordercolor=palette['border'])
        style.configure("TLabel", background=palette['bg'], foreground=palette['text'])
        
        # Custom button styles
        style.configure("TButton", font=("Segoe UI", 10, "bold"), background=palette['accent'], foreground=palette['select_fg'], borderwidth=0, padding=8)
        style.map("TButton", 
                  background=[("active", palette['accent_hover']), ("disabled", palette['border'])],
                  foreground=[("disabled", palette['muted_text'])])
        
        style.configure("Primary.TButton", background=palette['success'], foreground=palette['select_fg'])
        style.map("Primary.TButton", background=[("active", "#059669")])
        
        style.configure("Danger.TButton", background=palette['danger'], foreground=palette['select_fg'])
        style.map("Danger.TButton", background=[("active", "#dc2626")])
        
        style.configure("Secondary.TButton", background=palette['border'], foreground=palette['text'])
        style.map("Secondary.TButton", background=[("active", palette['card_bg'])])

        # Checkbutton
        style.configure("TCheckbutton", background=palette['card_bg'], foreground=palette['text'], font=("Segoe UI", 9))
        style.map("TCheckbutton", 
                  background=[("active", palette['card_bg'])],
                  foreground=[("active", palette['text'])])

        # Progressbar
        style.configure("TProgressbar", troughcolor=palette['bg'], background=palette['accent'], borderwidth=0)
        
        # Treeview
        style.configure("Treeview", 
                        background=palette['card_bg'], 
                        fieldbackground=palette['card_bg'], 
                        foreground=palette['text'],
                        rowheight=26,
                        font=("Segoe UI", 9),
                        borderwidth=0)
        style.configure("Treeview.Heading", 
                        background=palette['bg'], 
                        foreground=palette['text'], 
                        font=("Segoe UI", 10, "bold"),
                        borderwidth=1,
                        relief="flat")
        style.map("Treeview", 
                  background=[("selected", palette['select_bg'])],
                  foreground=[("selected", palette['select_fg'])])

    def _apply_theme_to_widget_tree(self, widget, palette):
        w_class = widget.winfo_class()
        
        if w_class == "Frame":
            if widget == self.header_frame:
                widget.configure(bg=palette['bg'])
            elif widget == self.toggle_frame:
                widget.configure(bg=palette['border'])
            else:
                style_type = getattr(widget, "custom_style", "normal")
                bg = palette['card_bg'] if style_type == "card" else palette['bg']
                widget.configure(bg=bg)
                
        elif w_class == "Label":
            style_type = getattr(widget, "custom_style", "normal")
            bg = palette['card_bg'] if style_type == "card" else palette['bg']
            
            if style_type == "muted":
                fg = palette['muted_text']
            elif style_type == "title":
                fg = palette['text']
            else:
                fg = palette['text']
            widget.configure(bg=bg, fg=fg)
            
        elif w_class == "Entry":
            widget.configure(bg=palette['bg'], fg=palette['text'], 
                             insertbackground=palette['text'], highlightcolor=palette['accent'],
                             relief="solid", bd=1)
                             
        elif w_class == "Menu":
            widget.configure(bg=palette['card_bg'], fg=palette['text'], 
                             activebackground=palette['accent'], activeforeground=palette['text'])
                             
        elif w_class == "Text":
            widget.configure(bg=palette['bg'], fg=palette['text'], 
                             insertbackground=palette['text'], relief="flat")
        
        elif w_class == "Canvas":
            widget.configure(bg=palette['card_bg'], highlightthickness=0)

        # Recurse children
        for child in widget.winfo_children():
            self._apply_theme_to_widget_tree(child, palette)

    def show_screen(self, screen_name):
        screen = self.screens[screen_name]
        screen.tkraise()
        screen.on_show()

    def start_scan(self, directory, match_name, match_ext, skip_sys):
        self.scanning = True
        self.selected_files.clear()
        
        # Re-initialize the event queue to clear any stale events from a previous scan
        self.event_queue = queue.Queue()
        
        self.show_screen("ProgressScreen")
        
        self.finder = DuplicateFinderEngine(
            target_dir=directory,
            event_queue=self.event_queue,
            match_by_name=match_name,
            match_by_ext=match_ext,
            skip_system_files=skip_sys
        )
        self.finder.start()
        self.after(50, self.poll_queue)

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
        progress_screen = self.screens["ProgressScreen"]
        
        if event_type == 'SCAN_START':
            progress_screen.update_phase("Gathering files recursively...", 0)
        elif event_type == 'SCAN_DIR':
            progress_screen.update_current_dir(data)
        elif event_type == 'SCAN_FILE_COUNT':
            progress_screen.update_file_count(data)
        elif event_type == 'HASH_START':
            progress_screen.setup_hashing(data)
        elif event_type == 'HASH_PROGRESS':
            progress_screen.update_hash_progress(data[0], data[1])
        elif event_type == 'COMPARING':
            progress_screen.update_phase("Analyzing matching structures...", 95)
        elif event_type == 'FINISHED':
            self.scanning = False
            self.scan_results = data
            self.show_screen("ResultsScreen")
        elif event_type == 'CANCELLED':
            self.scanning = False
            messagebox.showinfo("Scan Cancelled", "The scan was successfully cancelled.")
            self.show_screen("SetupScreen")
        elif event_type == 'ERROR':
            self.scanning = False
            messagebox.showerror("Scan Error", f"An error occurred during scanning:\n{data}")
            self.show_screen("SetupScreen")

# --- SCREENS ---

class SetupScreen(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.configure(style="TFrame")
        
        title_lbl = tk.Label(self, text="Scan New Directory", font=("Segoe UI", 15, "bold"))
        title_lbl.custom_style = "title"
        title_lbl.pack(anchor="w", pady=(5, 2))
        
        subtitle_lbl = tk.Label(self, text="Configure matching rules to find redundant files wasting disk space", font=("Segoe UI", 9))
        subtitle_lbl.custom_style = "muted"
        subtitle_lbl.pack(anchor="w", pady=(0, 10))
        
        # Folder Selector Card
        path_frame = ttk.Frame(self, style="Card.TFrame", padding=12)
        path_frame.custom_style = "card"
        path_frame.pack(fill="x", pady=5)
        
        lbl = tk.Label(path_frame, text="Select Target Folder", font=("Segoe UI", 10, "bold"))
        lbl.custom_style = "card"
        lbl.pack(anchor="w", pady=(0, 4))
        
        selector_inner = tk.Frame(path_frame)
        selector_inner.custom_style = "card"
        selector_inner.pack(fill="x")
        
        self.path_var = tk.StringVar()
        self.path_entry = tk.Entry(selector_inner, textvariable=self.path_var, font=("Segoe UI", 10))
        self.path_entry.pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 10))
        
        self.browse_btn = ttk.Button(selector_inner, text="Browse...", command=self.browse_folder, style="Secondary.TButton")
        self.browse_btn.pack(side="right")
        
        # Options Card
        options_frame = ttk.Frame(self, style="Card.TFrame", padding=12)
        options_frame.custom_style = "card"
        options_frame.pack(fill="x", pady=10)
        
        options_lbl = tk.Label(options_frame, text="Matching Rules & Filters", font=("Segoe UI", 10, "bold"))
        options_lbl.custom_style = "card"
        options_lbl.pack(anchor="w", pady=(0, 8))
        
        self.match_name_var = tk.BooleanVar(value=False)
        self.match_ext_var = tk.BooleanVar(value=False)
        self.skip_sys_var = tk.BooleanVar(value=True)
        
        cb_name = ttk.Checkbutton(options_frame, text="Match File Names (Case-insensitive)", variable=self.match_name_var)
        cb_name.pack(anchor="w", pady=3)
        
        cb_ext = ttk.Checkbutton(options_frame, text="Match File Extensions", variable=self.match_ext_var)
        cb_ext.pack(anchor="w", pady=3)
        
        cb_sys = ttk.Checkbutton(options_frame, text="Ignore Hidden and System Files", variable=self.skip_sys_var)
        cb_sys.pack(anchor="w", pady=3)
        
        # Info Box inside Card
        desc_frame = tk.Frame(options_frame)
        desc_frame.custom_style = "card"
        desc_frame.pack(fill="x", pady=(8, 0))
        
        info_icon = tk.Label(desc_frame, text="ℹ", font=("Segoe UI", 11), fg=DARK_THEME['accent'])
        info_icon.custom_style = "card"
        info_icon.pack(side="left", anchor="n", padx=(0, 5))
        
        info_lbl = tk.Label(desc_frame, text="By default, duplicate status is determined strictly by file size and byte-level content hash. Ticking the rules above requires matched duplicates to also share the exact name or extension.",
                             font=("Segoe UI", 9), justify="left", wrap=600)
        info_lbl.custom_style = "muted"
        info_lbl.pack(side="left", fill="x", expand=True)

        # Action Buttons
        self.scan_btn = ttk.Button(self, text="Scan Directory 🔍", command=self.start_scan, style="Primary.TButton")
        self.scan_btn.pack(anchor="e", pady=10)

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.path_var.set(os.path.normpath(folder))

    def start_scan(self):
        path = self.path_var.get().strip()
        if not path:
            messagebox.showwarning("Validation Error", "Please select a target folder to scan.")
            return
        if not os.path.exists(path) or not os.path.isdir(path):
            messagebox.showerror("Error", "The specified folder does not exist or is not a directory.")
            return
        self.controller.start_scan(
            directory=path,
            match_name=self.match_name_var.get(),
            match_ext=self.match_ext_var.get(),
            skip_sys=self.skip_sys_var.get()
        )

    def on_show(self):
        pass

class ProgressScreen(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.configure(style="TFrame")
        
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
        self.progress_bar = ttk.Progressbar(card, variable=self.progress_var, maximum=100, mode="determinate")
        self.progress_bar.pack(fill="x", pady=10)
        
        self.percentage_lbl = tk.Label(card, text="0%", font=("Segoe UI", 12, "bold"))
        self.percentage_lbl.custom_style = "card"
        self.percentage_lbl.pack(anchor="e")
        
        self.current_action_lbl = tk.Label(card, text="Indexing file structures...", font=("Segoe UI", 9, "italic"))
        self.current_action_lbl.custom_style = "muted"
        self.current_action_lbl.pack(fill="x", pady=(10, 5))
        
        stats_frame = tk.Frame(card)
        stats_frame.custom_style = "card"
        stats_frame.pack(fill="x", pady=5)
        
        self.total_files_lbl = tk.Label(stats_frame, text="Files Found: 0", font=("Segoe UI", 10, "bold"))
        self.total_files_lbl.custom_style = "card"
        self.total_files_lbl.pack(anchor="w", pady=2)
        
        self.cancel_btn = ttk.Button(self, text="Cancel Scan ⏹", command=self.controller.cancel_scan, style="Danger.TButton")
        self.cancel_btn.pack(anchor="e", pady=15)
        self.total_to_hash = 0

    def on_show(self):
        self.progress_var.set(0)
        self.percentage_lbl.configure(text="0%")
        self.phase_lbl.configure(text="Initializing engine...")
        self.current_action_lbl.configure(text="")
        self.total_files_lbl.configure(text="Files Scanned: 0")
        self.total_to_hash = 0

    def update_phase(self, phase_text, percentage=None):
        self.phase_lbl.configure(text=phase_text)
        if percentage is not None:
            self.progress_var.set(percentage)
            self.percentage_lbl.configure(text=f"{int(percentage)}%")

    def update_current_dir(self, directory):
        if len(directory) > 85:
            display_dir = "..." + directory[-82:]
        else:
            display_dir = directory
        self.current_action_lbl.configure(text=f"Searching: {display_dir}")

    def update_file_count(self, count):
        self.total_files_lbl.configure(text=f"Files Found: {count:,}")

    def setup_hashing(self, total_files):
        self.total_to_hash = total_files
        self.update_phase("Computing content hashes...", 0)
        self.total_files_lbl.configure(text=f"Files to Compare: {total_files:,}")

    def update_hash_progress(self, current, filepath):
        if self.total_to_hash > 0:
            percentage = (current / self.total_to_hash) * 100
            self.progress_var.set(percentage)
            self.percentage_lbl.configure(text=f"{int(percentage)}%")
            
        if len(filepath) > 85:
            display_path = "..." + filepath[-82:]
        else:
            display_path = filepath
        self.current_action_lbl.configure(text=f"Hashing [{current}/{self.total_to_hash}]: {display_path}")

class ResultsScreen(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.configure(style="TFrame")
        
        self._preview_image_ref = None
        self.preview_visible = True
        
        # Header layout
        top_bar = tk.Frame(self)
        top_bar.pack(fill="x", pady=(5, 5))
        
        title_lbl = tk.Label(top_bar, text="Scan Results", font=("Segoe UI", 15, "bold"))
        title_lbl.custom_style = "title"
        title_lbl.pack(side="left")
        
        self.preview_toggle_btn = ttk.Button(top_bar, text="Hide Details Panel ◀", command=self.toggle_preview_pane, style="Secondary.TButton")
        self.preview_toggle_btn.pack(side="right")
        
        self.summary_lbl = tk.Label(self, text="Calculating duplicates...", font=("Segoe UI", 9))
        self.summary_lbl.custom_style = "muted"
        self.summary_lbl.pack(anchor="w", pady=(0, 8))
        
        # Main body container
        self.body_container = tk.Frame(self)
        self.body_container.pack(fill="both", expand=True)
        
        # 1. Left Panel: Treeview Table
        self.left_pane = ttk.Frame(self.body_container, style="Card.TFrame")
        self.left_pane.custom_style = "card"
        self.left_pane.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        self.tree = ttk.Treeview(self.left_pane, columns=("size", "date", "status"), selectmode="browse")
        self.tree.heading("#0", text="Path Difference / Base Directory", anchor="w")
        self.tree.heading("size", text="Size", anchor="e")
        self.tree.heading("date", text="Date Modified", anchor="w")
        self.tree.heading("status", text="Select", anchor="center")
        
        self.tree.column("#0", width=350, anchor="w")
        self.tree.column("size", width=80, anchor="e")
        self.tree.column("date", width=130, anchor="w")
        self.tree.column("status", width=60, anchor="center")
        
        vsb = ttk.Scrollbar(self.left_pane, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(self.left_pane, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        
        self.left_pane.grid_rowconfigure(0, weight=1)
        self.left_pane.grid_columnconfigure(0, weight=1)
        
        self.tree.bind("<Button-1>", self.on_click_tree)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        self.tree.bind("<Button-3>", self.show_context_menu)
        self.tree.bind("<space>", lambda e: self.toggle_selected_row())
        
        # Context Menu
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="Open File", command=self.open_file)
        self.context_menu.add_command(label="Open Folder Location", command=self.open_folder)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Toggle Selection", command=self.toggle_selected_row)
        
        # 2. Right Panel: Collapsable Preview Pane
        self.preview_pane = ttk.Frame(self.body_container, style="Card.TFrame", width=280)
        self.preview_pane.custom_style = "card"
        self.preview_pane.pack(side="right", fill="both", expand=False)
        self.preview_pane.pack_propagate(False)
        
        self.scroll_preview = ScrollableFrame(self.preview_pane)
        self.scroll_preview.pack(fill="both", expand=True)
        
        self.inner_preview = self.scroll_preview.scrollable_frame
        self.inner_preview.custom_style = "card"
        
        self.preview_title = tk.Label(self.inner_preview, text="File Details", font=("Segoe UI", 11, "bold"))
        self.preview_title.custom_style = "card"
        self.preview_title.pack(anchor="w", pady=(0, 10))
        
        self.media_frame = tk.Frame(self.inner_preview, bd=1, relief="solid", bg="#000000", height=160)
        self.media_frame.pack(fill="x", pady=(0, 10))
        self.media_frame.pack_propagate(False)
        
        self.media_lbl = tk.Label(self.media_frame, text="No Media Preview", font=("Segoe UI", 9, "italic"), fg="#888888", bg="#000000")
        self.media_lbl.pack(expand=True, fill="both")
        
        self.snippet_lbl = tk.Label(self.inner_preview, text="Text Snippet:", font=("Segoe UI", 9, "bold"))
        self.snippet_lbl.custom_style = "card"
        
        self.snippet_frame = tk.Frame(self.inner_preview, bd=1, relief="solid")
        self.snippet_text = tk.Text(self.snippet_frame, height=7, font=("Consolas", 8), wrap="char")
        self.snippet_vsb = ttk.Scrollbar(self.snippet_frame, orient="vertical", command=self.snippet_text.yview)
        self.snippet_text.configure(yscrollcommand=self.snippet_vsb.set)
        self.snippet_text.pack(side="left", fill="both", expand=True)
        self.snippet_vsb.pack(side="right", fill="y")
        
        self.meta_frame = tk.Frame(self.inner_preview)
        self.meta_frame.custom_style = "card"
        self.meta_frame.pack(fill="both", expand=True, pady=(5, 0))
        
        self.meta_lbl = tk.Label(self.meta_frame, text="Select a file to inspect its content.", font=("Segoe UI", 9, "italic"), justify="left", anchor="nw", wrap=240)
        self.meta_lbl.custom_style = "card"
        self.meta_lbl.pack(fill="both", expand=True)
        
        # Selection / Action Panel
        actions_bar = tk.Frame(self)
        actions_bar.pack(fill="x", pady=(10, 5))
        
        select_lbl = tk.Label(actions_bar, text="Quick Select:", font=("Segoe UI", 9, "bold"))
        select_lbl.custom_style = "muted"
        select_lbl.pack(side="left", padx=(0, 8))
        
        self.all_but_one_btn = ttk.Button(actions_bar, text="Keep Oldest", command=lambda: self.select_all_but_one(keep="oldest"), style="Secondary.TButton")
        self.all_but_one_btn.pack(side="left", padx=3)

        self.all_but_one_newest_btn = ttk.Button(actions_bar, text="Keep Newest", command=lambda: self.select_all_but_one(keep="newest"), style="Secondary.TButton")
        self.all_but_one_newest_btn.pack(side="left", padx=3)
        
        self.deselect_all_btn = ttk.Button(actions_bar, text="Clear Select", command=self.deselect_all, style="Secondary.TButton")
        self.deselect_all_btn.pack(side="left", padx=3)

        # Bottom Frame
        bottom_frame = tk.Frame(self)
        bottom_frame.pack(fill="x", pady=(10, 0))
        
        self.back_btn = ttk.Button(bottom_frame, text="⬅ Scan Another Folder", command=self.go_back, style="Secondary.TButton")
        self.back_btn.pack(side="left")
        
        self.delete_btn = ttk.Button(bottom_frame, text="Delete Selected (0 files) 🗑️", command=self.delete_selected, style="Danger.TButton")
        self.delete_btn.pack(side="right")

    def toggle_preview_pane(self):
        if self.preview_visible:
            self.preview_pane.pack_forget()
            self.preview_toggle_btn.configure(text="Show Details Panel ▶")
            self.preview_visible = False
        else:
            self.preview_pane.pack(side="right", fill="both", expand=False)
            self.preview_toggle_btn.configure(text="Hide Details Panel ◀")
            self.preview_visible = True

    def update_theme(self, palette):
        self.tree.tag_configure("checked", background=palette['checked_bg'], foreground=palette['text'])
        self.tree.tag_configure("unchecked", background=palette['card_bg'], foreground=palette['text'])
        self.tree.tag_configure("group_header", background=palette['group_header_bg'], foreground=palette['text'], font=("Segoe UI", 9, "bold"))

    def on_show(self):
        self.tree.delete(*self.tree.get_children())
        self.clear_preview()
        
        self.update_theme(self.controller.palette)
        
        results = self.controller.scan_results
        total_groups = len(results)
        total_dup_files = 0
        total_redundant_size = 0
        
        for index, group in enumerate(results):
            group_size = group['size']
            files = group['files']
            
            dups_in_group = len(files) - 1
            total_dup_files += dups_in_group
            total_redundant_size += dups_in_group * group_size
            
            try:
                base_path = os.path.commonpath(files)
            except Exception:
                base_path = ""
            
            formatted_size = utils.format_size(group_size)
            
            if base_path:
                header_name = f"Group #{index + 1} | Base: {base_path} | {len(files)} files ({formatted_size} each)"
            else:
                header_name = f"Group #{index + 1} | Size: {formatted_size} | {len(files)} files"
                
            header_id = self.tree.insert("", "end", text=header_name, values=(formatted_size, "", ""), 
                                         open=True, tags=("group_header",))
            
            for filepath in files:
                mtime_str = ""
                try:
                    mtime = os.path.getmtime(filepath)
                    mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    pass
                
                if base_path:
                    display_path = os.path.relpath(filepath, base_path)
                else:
                    display_path = filepath
                    
                # Insert row initialized as unchecked and save path as 4th element in values (Select status is Unicode '☐')
                self.tree.insert(header_id, "end", text=display_path, values=(formatted_size, mtime_str, "☐", filepath), 
                                  tags=("unchecked",))
                
        formatted_redundant_size = utils.format_size(total_redundant_size)
        self.summary_lbl.configure(
            text=f"Found {total_groups:,} duplicate groups. Redundant files: {total_dup_files:,} ({formatted_redundant_size} wasting space)"
        )
        self.update_delete_button_state()

    def update_delete_button_state(self):
        count = len(self.controller.selected_files)
        if count > 0:
            self.delete_btn.configure(text=f"Send Selected to Recycle Bin ({count} files) 🗑️", state="normal")
        else:
            self.delete_btn.configure(text="Delete Selected (0 files) 🗑️", state="disabled")

    def on_click_tree(self, event):
        item_id = self.tree.identify_row(event.y)
        if not item_id or self.tree.parent(item_id) == "":
            return
            
        # Only toggle checked state if the user clicks in the "Select" column (column "#3")
        column = self.tree.identify_column(event.x)
        if column == "#3":
            self.toggle_row_selection(item_id)

    def toggle_row_selection(self, item_id):
        # Retrieve path from values
        vals = list(self.tree.item(item_id, "values"))
        if len(vals) <= 3:
            return
        filepath = vals[3]
        
        tags = self.tree.item(item_id, "tags")
        status = tags[0] if tags else "unchecked"
        
        if status == "unchecked":
            vals[2] = "☑"
            self.tree.item(item_id, values=vals, tags=("checked",))
            self.controller.selected_files.add(filepath)
        else:
            vals[2] = "☐"
            self.tree.item(item_id, values=vals, tags=("unchecked",))
            self.controller.selected_files.discard(filepath)
            
        self.update_delete_button_state()

    def toggle_selected_row(self):
        selected_items = self.tree.selection()
        for item_id in selected_items:
            if self.tree.parent(item_id) != "":
                self.toggle_row_selection(item_id)

    def show_context_menu(self, event):
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return
            
        if item_id not in self.tree.selection():
            self.tree.selection_set(item_id)
            
        is_child = self.tree.parent(item_id) != ""
        state = "normal" if is_child else "disabled"
        
        self.context_menu.entryconfig("Open File", state=state)
        self.context_menu.entryconfig("Open Folder Location", state=state)
        self.context_menu.entryconfig("Toggle Selection", state=state)
        self.context_menu.post(event.x_root, event.y_root)

    def get_selected_file_path(self) -> Optional[str]:
        selected = self.tree.selection()
        if not selected:
            return None
        item_id = selected[0]
        if self.tree.parent(item_id) == "":
            return None
        vals = self.tree.item(item_id, "values")
        return vals[3] if len(vals) > 3 else None

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
            return
        self.update_preview_pane(path)

    def clear_preview(self):
        self._preview_image_ref = None
        self.media_lbl.configure(image="", text="No Media Preview")
        self.snippet_lbl.pack_forget()
        self.snippet_frame.pack_forget()
        self.meta_lbl.configure(text="Select a file to inspect its content.", font=("Segoe UI", 9, "italic"))

    def update_preview_pane(self, filepath):
        self.clear_preview()
        if not os.path.exists(filepath):
            self.meta_lbl.configure(text="File does not exist or has been deleted.", font=("Segoe UI", 9, "italic"))
            return
            
        filename = os.path.basename(filepath)
        _, ext = os.path.splitext(filename)
        ext = ext.lower()
        
        try:
            size_b = os.path.getsize(filepath)
            size_fmt = utils.format_size(size_b)
            mtime = os.path.getmtime(filepath)
            mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            self.meta_lbl.configure(text=f"Error reading details:\n{e}")
            return
            
        metadata_text = f"Name: {filename}\nSize: {size_fmt}\nModified: {mtime_str}\n\nFull Path:\n{filepath}"
        self.meta_lbl.configure(text=metadata_text, font=("Segoe UI", 9))
        
        image_exts = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff"}
        video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm"}
        text_exts = {".txt", ".py", ".log", ".json", ".ini", ".cfg", ".xml", ".html", ".css", ".md", ".csv", ".bat", ".sh"}
        
        if ext in image_exts:
            try:
                img = Image.open(filepath)
                img.thumbnail((240, 150))
                photo = ImageTk.PhotoImage(img)
                self.media_lbl.configure(image=photo, text="")
                self._preview_image_ref = photo
            except Exception as e:
                self.media_lbl.configure(text=f"Image preview error:\n{e}")
                
        elif ext in video_exts:
            if OPENCV_AVAILABLE:
                try:
                    cap = cv2.VideoCapture(filepath)
                    if cap.isOpened():
                        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                        frame_idx = min(24, total // 2) if total > 0 else 0
                        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                        success, frame = cap.read()
                        cap.release()
                        
                        if success:
                            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            img = Image.fromarray(frame_rgb)
                            img.thumbnail((240, 150))
                            photo = ImageTk.PhotoImage(img)
                            self.media_lbl.configure(image=photo, text="")
                            self._preview_image_ref = photo
                        else:
                            self.media_lbl.configure(text="🎬 Video File\n(Could not read frame)")
                    else:
                        self.media_lbl.configure(text="🎬 Video File\n(Could not open video file)")
                except Exception as e:
                    self.media_lbl.configure(text=f"🎬 Video File\n(Frame extract error:\n{e})")
            else:
                self.media_lbl.configure(text="🎬 Video File\n(Install opencv-python for frame preview)")
                
        elif ext in text_exts:
            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    snippet = "".join([f.readline() for _ in range(12)])
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
            self.media_lbl.configure(text="📄 Binary / Resource File")

        self.controller._apply_theme_to_widget_tree(self.preview_pane, self.controller.palette)

    def select_all_but_one(self, keep="oldest"):
        self.controller.selected_files.clear()
        
        root_items = self.tree.get_children("")
        for header_id in root_items:
            children = self.tree.get_children(header_id)
            if not children:
                continue
                
            file_meta = []
            for child_id in children:
                vals = self.tree.item(child_id, "values")
                if len(vals) > 3:
                    filepath = vals[3]
                    try:
                        mtime = os.path.getmtime(filepath)
                    except Exception:
                        mtime = 0
                    file_meta.append((child_id, filepath, mtime))
                
            file_meta.sort(key=lambda x: x[2])
            
            if keep == "oldest":
                keep_item = file_meta[0]
                delete_items = file_meta[1:]
            else:
                keep_item = file_meta[-1]
                delete_items = file_meta[:-1]
                
            vals_keep = list(self.tree.item(keep_item[0], "values"))
            if len(vals_keep) > 2:
                vals_keep[2] = "☐"
            self.tree.item(keep_item[0], values=vals_keep, tags=("unchecked",))
            
            for item in delete_items:
                vals_del = list(self.tree.item(item[0], "values"))
                if len(vals_del) > 2:
                    vals_del[2] = "☑"
                self.tree.item(item[0], values=vals_del, tags=("checked",))
                self.controller.selected_files.add(item[1])
                
        self.update_delete_button_state()

    def deselect_all(self):
        self.controller.selected_files.clear()
        root_items = self.tree.get_children("")
        for header_id in root_items:
            children = self.tree.get_children(header_id)
            for child_id in children:
                vals = list(self.tree.item(child_id, "values"))
                if len(vals) > 2:
                    vals[2] = "☐"
                self.tree.item(child_id, values=vals, tags=("unchecked",))
        self.update_delete_button_state()

    def delete_selected(self):
        selected = list(self.controller.selected_files)
        count = len(selected)
        if count == 0:
            return
            
        confirm = messagebox.askyesno(
            "Confirm Safe Deletion",
            f"Are you sure you want to send {count} selected files to the Recycle Bin?\n\nThey can be restored from the Recycle Bin if needed."
        )
        if not confirm:
            return
            
        success = utils.send_to_recycle_bin(selected)
        
        if success:
            messagebox.showinfo("Success", f"{count} files were successfully sent to the Recycle Bin.")
            
            for filepath in selected:
                for group in self.controller.scan_results:
                    if filepath in group['files']:
                        group['files'].remove(filepath)
                        
            self.controller.scan_results = [g for g in self.controller.scan_results if len(g['files']) >= 2]
            self.controller.selected_files.clear()
            self.on_show()
        else:
            messagebox.showerror(
                "Deletion Error",
                "An error occurred while sending files to the Recycle Bin. Please verify permissions."
            )

    def go_back(self):
        self.controller.show_screen("SetupScreen")
