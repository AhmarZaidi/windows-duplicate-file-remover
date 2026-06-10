import os
import queue
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
from datetime import datetime

import utils
from duplicate_finder import DuplicateFinderEngine

# Color Palette (Dark Theme / Glassmorphism inspired)
BG_COLOR = "#181824"          # Deep dark background
CARD_BG = "#222232"          # Dark blue-gray card background
ACCENT_COLOR = "#3b82f6"     # Vibrant Blue
ACCENT_HOVER = "#2563eb"     # Darker Blue
TEXT_COLOR = "#f3f4f6"       # Light gray text
MUTED_TEXT = "#9ca3af"       # Muted gray text
DANGER_COLOR = "#ef4444"     # Soft Red
SUCCESS_COLOR = "#10b981"    # Soft Green
BORDER_COLOR = "#374151"     # Dark outline

class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Duplicate File Remover")
        self.geometry("850x650")
        self.configure(bg=BG_COLOR)
        self.minsize(700, 500)
        
        # Center the window on screen
        self.eval('tk::PlaceWindow . center')
        
        # Application state
        self.event_queue = queue.Queue()
        self.finder = None
        self.scanning = False
        self.scan_results = []
        self.selected_files = set()  # set of paths selected for deletion
        
        # Configure styles
        self._setup_styles()
        
        # Container frame for switching screens
        self.container = tk.Frame(self, bg=BG_COLOR)
        self.container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Initialize screens
        self.screens = {}
        for F in (SetupScreen, ProgressScreen, ResultsScreen):
            screen_name = F.__name__
            screen = F(parent=self.container, controller=self)
            self.screens[screen_name] = screen
            screen.grid(row=0, column=0, sticky="nsew")
            
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)
        
        self.show_screen("SetupScreen")

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        
        # Base frame & labels
        style.configure("TFrame", background=BG_COLOR)
        style.configure("TLabel", background=BG_COLOR, foreground=TEXT_COLOR, font=("Segoe UI", 10))
        
        # Card style
        style.configure("Card.TFrame", background=CARD_BG, borderwidth=1, relief="solid", bordercolor=BORDER_COLOR)
        style.configure("Card.TLabel", background=CARD_BG, foreground=TEXT_COLOR)
        
        # Buttons
        style.configure("TButton", font=("Segoe UI", 10, "bold"), background=ACCENT_COLOR, foreground=TEXT_COLOR, borderwidth=0, padding=10)
        style.map("TButton", 
                  background=[("active", ACCENT_HOVER), ("disabled", BORDER_COLOR)],
                  foreground=[("disabled", MUTED_TEXT)])
        
        # Primary Action Button (Teal/Green)
        style.configure("Primary.TButton", background=SUCCESS_COLOR, foreground=TEXT_COLOR)
        style.map("Primary.TButton", background=[("active", "#059669")])
        
        # Danger Button (Red)
        style.configure("Danger.TButton", background=DANGER_COLOR, foreground=TEXT_COLOR)
        style.map("Danger.TButton", background=[("active", "#dc2626")])
        
        # Secondary Button (Slate Gray)
        style.configure("Secondary.TButton", background="#4b5563", foreground=TEXT_COLOR)
        style.map("Secondary.TButton", background=[("active", "#374151")])

        # Checkbutton
        style.configure("TCheckbutton", background=CARD_BG, foreground=TEXT_COLOR, font=("Segoe UI", 10))
        style.map("TCheckbutton", 
                  background=[("active", CARD_BG)],
                  foreground=[("active", TEXT_COLOR)])

        # Progressbar
        style.configure("TProgressbar", thickness=15, troughcolor=BG_COLOR, background=ACCENT_COLOR, borderwidth=0)
        
        # Treeview styling
        style.configure("Treeview", 
                        background=CARD_BG, 
                        fieldbackground=CARD_BG, 
                        foreground=TEXT_COLOR,
                        rowheight=26,
                        font=("Segoe UI", 9),
                        borderwidth=0)
        style.configure("Treeview.Heading", 
                        background=BG_COLOR, 
                        foreground=TEXT_COLOR, 
                        font=("Segoe UI", 10, "bold"),
                        borderwidth=1,
                        relief="flat")
        style.map("Treeview", 
                  background=[("selected", "#3b82f6")],
                  foreground=[("selected", "#ffffff")])

    def show_screen(self, screen_name):
        screen = self.screens[screen_name]
        screen.tkraise()
        screen.on_show()

    def start_scan(self, directory, match_name, match_ext, skip_sys):
        self.scanning = True
        self.selected_files.clear()
        
        # Switch to progress screen
        self.show_screen("ProgressScreen")
        
        # Initialize and start engine
        self.finder = DuplicateFinderEngine(
            target_dir=directory,
            event_queue=self.event_queue,
            match_by_name=match_name,
            match_by_ext=match_ext,
            skip_system_files=skip_sys
        )
        self.finder.start()
        
        # Start checking the queue
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
            progress_screen.update_phase("Analyzing matching file structures...", 95)
            
        elif event_type == 'FINISHED':
            self.scanning = False
            self.scan_results = data
            self.show_screen("ResultsScreen")
            
        elif event_type == 'CANCELLED':
            self.scanning = False
            messagebox.showinfo("Scan Cancelled", "The scan operation was successfully cancelled.")
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
        
        # Layout weights
        self.columnconfigure(0, weight=1)
        
        # Title Banner
        title_lbl = tk.Label(self, text="Duplicate File Finder", font=("Segoe UI", 20, "bold"), fg=TEXT_COLOR, bg=BG_COLOR)
        title_lbl.pack(anchor="w", pady=(10, 5))
        
        subtitle_lbl = tk.Label(self, text="Scan your folders and identify duplicate content using customizable rules", 
                                font=("Segoe UI", 10), fg=MUTED_TEXT, bg=BG_COLOR)
        subtitle_lbl.pack(anchor="w", pady=(0, 20))
        
        # Folder Selector Card
        path_frame = ttk.Frame(self, style="Card.TFrame", padding=15)
        path_frame.pack(fill="x", pady=10)
        
        lbl = tk.Label(path_frame, text="Select Target Folder", font=("Segoe UI", 11, "bold"), fg=TEXT_COLOR, bg=CARD_BG)
        lbl.pack(anchor="w", pady=(0, 5))
        
        selector_inner = tk.Frame(path_frame, bg=CARD_BG)
        selector_inner.pack(fill="x")
        
        self.path_var = tk.StringVar()
        self.path_entry = tk.Entry(selector_inner, textvariable=self.path_var, font=("Segoe UI", 10), 
                                   bg=BG_COLOR, fg=TEXT_COLOR, insertbackground=TEXT_COLOR, bd=1, relief="solid")
        self.path_entry.pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 10))
        
        browse_btn = ttk.Button(selector_inner, text="Browse...", command=self.browse_folder, style="TButton")
        browse_btn.pack(side="right")
        
        # Options Card
        options_frame = ttk.Frame(self, style="Card.TFrame", padding=15)
        options_frame.pack(fill="x", pady=15)
        
        options_lbl = tk.Label(options_frame, text="Matching Rules & Filters", font=("Segoe UI", 11, "bold"), fg=TEXT_COLOR, bg=CARD_BG)
        options_lbl.pack(anchor="w", pady=(0, 10))
        
        # Variables for settings
        self.match_name_var = tk.BooleanVar(value=False)
        self.match_ext_var = tk.BooleanVar(value=False)
        self.skip_sys_var = tk.BooleanVar(value=True)
        
        # Layout rules checkboxes
        cb_name = ttk.Checkbutton(options_frame, text="Match File Names (Case-insensitive)", variable=self.match_name_var)
        cb_name.pack(anchor="w", pady=4)
        
        cb_ext = ttk.Checkbutton(options_frame, text="Match File Extensions", variable=self.match_ext_var)
        cb_ext.pack(anchor="w", pady=4)
        
        cb_sys = ttk.Checkbutton(options_frame, text="Ignore Hidden and System Files", variable=self.skip_sys_var)
        cb_sys.pack(anchor="w", pady=4)
        
        # Match description info label
        desc_frame = tk.Frame(options_frame, bg=CARD_BG)
        desc_frame.pack(fill="x", pady=(10, 0))
        info_icon = tk.Label(desc_frame, text="ℹ", font=("Segoe UI", 12), fg=ACCENT_COLOR, bg=CARD_BG)
        info_icon.pack(side="left", anchor="n", padx=(0, 5))
        info_lbl = tk.Label(desc_frame, text="By default, files are matched strictly by content size and hash, regardless of name. Tick checkboxes to restrict duplicate matches to those that also share the same name or extension.",
                             font=("Segoe UI", 9), fg=MUTED_TEXT, bg=CARD_BG, justify="left", wrap=600)
        info_lbl.pack(side="left", fill="x", expand=True)

        # Action Buttons
        self.scan_btn = ttk.Button(self, text="Scan Now 🔍", command=self.start_scan, style="Primary.TButton")
        self.scan_btn.pack(anchor="e", pady=20)

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.path_var.set(os.path.normpath(folder))

    def start_scan(self):
        path = self.path_var.get().strip()
        if not path:
            messagebox.showwarning("Validation Error", "Please select or type a target folder to scan.")
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
        
        # Title
        self.title_lbl = tk.Label(self, text="Scanning Files...", font=("Segoe UI", 20, "bold"), fg=TEXT_COLOR, bg=BG_COLOR)
        self.title_lbl.pack(anchor="w", pady=(10, 5))
        
        self.phase_lbl = tk.Label(self, text="Gathering directory hierarchy...", font=("Segoe UI", 10), fg=MUTED_TEXT, bg=BG_COLOR)
        self.phase_lbl.pack(anchor="w", pady=(0, 20))
        
        # Progress Card
        card = ttk.Frame(self, style="Card.TFrame", padding=20)
        card.pack(fill="both", expand=True, pady=10)
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(card, variable=self.progress_var, maximum=100, mode="determinate")
        self.progress_bar.pack(fill="x", pady=10)
        
        self.percentage_lbl = tk.Label(card, text="0%", font=("Segoe UI", 14, "bold"), fg=TEXT_COLOR, bg=CARD_BG)
        self.percentage_lbl.pack(anchor="e")
        
        # Current file display
        self.current_action_lbl = tk.Label(card, text="Indexing file structures...", font=("Segoe UI", 10, "italic"), 
                                           fg=MUTED_TEXT, bg=CARD_BG, anchor="w", justify="left")
        self.current_action_lbl.pack(fill="x", pady=(15, 5))
        
        # Stats Counter Card
        stats_frame = tk.Frame(card, bg=CARD_BG)
        stats_frame.pack(fill="x", pady=10)
        
        self.total_files_lbl = tk.Label(stats_frame, text="Files Found: 0", font=("Segoe UI", 11, "bold"), fg=TEXT_COLOR, bg=CARD_BG)
        self.total_files_lbl.pack(anchor="w", pady=4)
        
        # Cancel Button
        cancel_btn = ttk.Button(self, text="Cancel Scan ⏹", command=self.controller.cancel_scan, style="Danger.TButton")
        cancel_btn.pack(anchor="e", pady=20)

        # Hashing specific stats
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
        # Truncate long paths
        if len(directory) > 75:
            display_dir = "..." + directory[-72:]
        else:
            display_dir = directory
        self.current_action_lbl.configure(text=f"Searching: {display_dir}")

    def update_file_count(self, count):
        self.total_files_lbl.configure(text=f"Files Found: {count:,}")

    def setup_hashing(self, total_files):
        self.total_to_hash = total_files
        self.update_phase("Computing content hashes (comparing content)...", 0)
        self.total_files_lbl.configure(text=f"Files to Compare: {total_files:,}")

    def update_hash_progress(self, current, filepath):
        if self.total_to_hash > 0:
            percentage = (current / self.total_to_hash) * 100
            self.progress_var.set(percentage)
            self.percentage_lbl.configure(text=f"{int(percentage)}%")
            
        # Truncate long path
        if len(filepath) > 75:
            display_path = "..." + filepath[-72:]
        else:
            display_path = filepath
        self.current_action_lbl.configure(text=f"Hashing [{current}/{self.total_to_hash}]: {display_path}")

class ResultsScreen(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.configure(style="TFrame")
        
        # Title and summary
        title_lbl = tk.Label(self, text="Scan Results", font=("Segoe UI", 20, "bold"), fg=TEXT_COLOR, bg=BG_COLOR)
        title_lbl.pack(anchor="w", pady=(10, 5))
        
        self.summary_lbl = tk.Label(self, text="Calculating duplicates...", font=("Segoe UI", 10), fg=MUTED_TEXT, bg=BG_COLOR)
        self.summary_lbl.pack(anchor="w", pady=(0, 15))
        
        # Results Table Panel
        table_frame = ttk.Frame(self, style="Card.TFrame")
        table_frame.pack(fill="both", expand=True, pady=5)
        
        # Set up Treeview with checkboxes column
        self.tree = ttk.Treeview(table_frame, columns=("size", "date", "status"), selectmode="extended")
        self.tree.heading("#0", text="File Path / Group Details", anchor="w")
        self.tree.heading("size", text="Size", anchor="e")
        self.tree.heading("date", text="Date Modified", anchor="w")
        self.tree.heading("status", text="Select", anchor="center")
        
        self.tree.column("#0", width=400, anchor="w")
        self.tree.column("size", width=100, anchor="e")
        self.tree.column("date", width=150, anchor="w")
        self.tree.column("status", width=70, anchor="center")
        
        # Scrollbars
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        # Grid layout for table + scrollbars
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
        
        # Tree Bindings
        self.tree.bind("<Double-1>", self.on_double_click)
        self.tree.bind("<Button-3>", self.show_context_menu)  # Right-click context menu
        
        # Context Menu Setup
        self.context_menu = tk.Menu(self, tearoff=0, bg=CARD_BG, fg=TEXT_COLOR, activebackground=ACCENT_COLOR)
        self.context_menu.add_command(label="Open File", command=self.open_file)
        self.context_menu.add_command(label="Open Folder Location", command=self.open_folder)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Toggle Selection", command=self.toggle_selected_row)
        
        # Selection / Action Panel
        actions_bar = tk.Frame(self, bg=BG_COLOR)
        actions_bar.pack(fill="x", pady=(15, 5))
        
        # Select options
        select_lbl = tk.Label(actions_bar, text="Quick Select:", font=("Segoe UI", 9, "bold"), fg=MUTED_TEXT, bg=BG_COLOR)
        select_lbl.pack(side="left", padx=(0, 10))
        
        all_but_one_btn = ttk.Button(actions_bar, text="Select All but One (Keep Oldest)", 
                                     command=lambda: self.select_all_but_one(keep="oldest"), style="Secondary.TButton")
        all_but_one_btn.pack(side="left", padx=5)

        all_but_one_newest_btn = ttk.Button(actions_bar, text="Select All but One (Keep Newest)", 
                                             command=lambda: self.select_all_but_one(keep="newest"), style="Secondary.TButton")
        all_but_one_newest_btn.pack(side="left", padx=5)
        
        deselect_all_btn = ttk.Button(actions_bar, text="Clear Selections", 
                                       command=self.deselect_all, style="Secondary.TButton")
        deselect_all_btn.pack(side="left", padx=5)

        # Bottom Frame for global buttons
        bottom_frame = tk.Frame(self, bg=BG_COLOR)
        bottom_frame.pack(fill="x", pady=(15, 0))
        
        back_btn = ttk.Button(bottom_frame, text="⬅ Scan Another Folder", command=self.go_back, style="Secondary.TButton")
        back_btn.pack(side="left")
        
        self.delete_btn = ttk.Button(bottom_frame, text="Delete Selected (0 files) 🗑️", command=self.delete_selected, style="Danger.TButton")
        self.delete_btn.pack(side="right")

    def on_show(self):
        # Refresh tree items
        self.tree.delete(*self.tree.get_children())
        
        results = self.controller.scan_results
        
        total_groups = len(results)
        total_dup_files = 0
        total_redundant_size = 0
        
        for index, group in enumerate(results):
            group_size = group['size']
            files = group['files']
            
            # Count duplicates: total files minus one (which is the main original)
            dups_in_group = len(files) - 1
            total_dup_files += dups_in_group
            total_redundant_size += dups_in_group * group_size
            
            # Add Group Header Row
            group_name = f"Group #{index + 1} | Content Hash: {group['hash'][:8]}... | {len(files)} files"
            formatted_size = utils.format_size(group_size)
            header_id = self.tree.insert("", "end", text=group_name, values=(formatted_size, "", ""), open=True)
            
            # Add Child File Rows
            for filepath in files:
                mtime_str = ""
                try:
                    mtime = os.path.getmtime(filepath)
                    mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    pass
                
                # Insert file item
                child_id = self.tree.insert(header_id, "end", text=filepath, values=(formatted_size, mtime_str, "[ ]"))
                # Store absolute file path in treeview item values to retrieve easily
                self.tree.set(child_id, "status", "[ ]")
                
        # Update summary text
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

    def on_double_click(self, event):
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return
            
        # Double click on parent group header does nothing (or normal collapse)
        if self.tree.parent(item_id) == "":
            return
            
        self.toggle_row_selection(item_id)

    def toggle_row_selection(self, item_id):
        filepath = self.tree.item(item_id, "text")
        current_status = self.tree.set(item_id, "status")
        
        if current_status == "[ ]":
            self.tree.set(item_id, "status", "[x]")
            self.controller.selected_files.add(filepath)
        else:
            self.tree.set(item_id, "status", "[ ]")
            self.controller.selected_files.discard(filepath)
            
        self.update_delete_button_state()

    def toggle_selected_row(self):
        selected_items = self.tree.selection()
        for item_id in selected_items:
            # Skip parent headers
            if self.tree.parent(item_id) != "":
                self.toggle_row_selection(item_id)

    def show_context_menu(self, event):
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return
            
        # Select the item that was right-clicked if not already selected
        if item_id not in self.tree.selection():
            self.tree.selection_set(item_id)
            
        # Disable options if right click is on group header
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
            return None  # Parent group header
        return self.tree.item(item_id, "text")

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
                folder = os.path.dirname(path)
                # Select the file in explorer
                subprocess.Popen(f'explorer /select,"{path}"')
            except Exception as e:
                messagebox.showerror("Error", f"Could not open folder:\n{e}")

    def select_all_but_one(self, keep="oldest"):
        """
        Walks all groups in results and selects all but one file in each group for deletion.
        - "oldest": Keeps the file with the oldest modification time (original).
        - "newest": Keeps the file with the newest modification time.
        """
        self.controller.selected_files.clear()
        
        # Iterate over root items (the group headers)
        root_items = self.tree.get_children("")
        for header_id in root_items:
            children = self.tree.get_children(header_id)
            if not children:
                continue
                
            # Gather files with their modification dates
            file_meta = []
            for child_id in children:
                filepath = self.tree.item(child_id, "text")
                try:
                    mtime = os.path.getmtime(filepath)
                except Exception:
                    mtime = 0
                file_meta.append((child_id, filepath, mtime))
                
            # Sort files by date
            # oldest first (smallest timestamp)
            file_meta.sort(key=lambda x: x[2])
            
            # Determine which item to keep
            if keep == "oldest":
                keep_item = file_meta[0]
                delete_items = file_meta[1:]
            else:  # newest
                keep_item = file_meta[-1]
                delete_items = file_meta[:-1]
                
            # Update GUI checkboxes and selection set
            self.tree.set(keep_item[0], "status", "[ ]")
            for item in delete_items:
                self.tree.set(item[0], "status", "[x]")
                self.controller.selected_files.add(item[1])
                
        self.update_delete_button_state()

    def deselect_all(self):
        self.controller.selected_files.clear()
        root_items = self.tree.get_children("")
        for header_id in root_items:
            children = self.tree.get_children(header_id)
            for child_id in children:
                self.tree.set(child_id, "status", "[ ]")
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
            
        # Perform Recycle Bin operation
        success = utils.send_to_recycle_bin(selected)
        
        if success:
            messagebox.showinfo("Success", f"{count} files were successfully sent to the Recycle Bin.")
            
            # Remove deleted files from our model results
            for filepath in selected:
                # Remove from results
                for group in self.controller.scan_results:
                    if filepath in group['files']:
                        group['files'].remove(filepath)
                        
            # Remove groups with less than 2 files remaining (since they are no longer duplicates)
            self.controller.scan_results = [g for g in self.controller.scan_results if len(g['files']) >= 2]
            
            # Clear selection and redraw screen
            self.controller.selected_files.clear()
            self.on_show()
        else:
            # Fallback error
            messagebox.showerror(
                "Deletion Error",
                "An error occurred while attempting to send the files to the Recycle Bin.\n"
                "Please verify file permissions or check if some files are currently locked by other applications."
            )

    def go_back(self):
        self.controller.show_screen("SetupScreen")
