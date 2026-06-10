# Windows Duplicate File Remover

A modern, fast, and accurate Windows desktop utility to scan a directory recursively, identify duplicate files of all types, preview matched contents, and safely delete files via Windows Recycle Bin integration. 

Built using Python's standard libraries, styled to match Windows 11 Fluent design principles, and enhanced with image and video frame previews.

---

## Key Features

1. **Multi-Pass Comparison Engine**:
   - Compares files based on **size**, **partial hash** (first 8KB), and **full content hash** (MD5) to instantly identify matching byte structures.
   - Skips unique files early in the pipeline to avoid redundant I/O, ensuring lightning-fast scans even across tens of thousands of files.
2. **Windows 11 Fluent UI Design**:
   - Modern dark/light/system theme support with a horizontal segmented 3-state toggle button.
   - Dynamically drawn canvas-based rounded buttons that change states on hover and click.
   - Windows 11 styled list view with real checkboxes and soft row-highlight states (`#e0f2fe` for light mode, `#2a3a4e` for dark mode).
   - Visually distinguished group dividers for clear separator rows, fully keyboard navigable.
3. **Advanced Collapsable Preview Pane**:
   - **Images**: Renders scaled thumbnails of all formats (PNG, JPG, BMP, WEBP, GIF, etc.) using Pillow.
   - **Videos**: Automatically extracts frame previews (at roughly the 1-second mark) for video formats (MP4, MKV, AVI, MOV, etc.) using OpenCV.
   - **Text Files**: Displays a scrollable read-only preview of the first 12 lines of text.
   - **Scrollable Details**: The entire right pane is scrollable, preventing element clipping on small displays.
4. **Path Differentiation**:
   - Calculates the longest common path base for each duplicate group.
   - Displays the common path in the group header, and shows only the relative differences in the child items, reducing visual clutter.
5. **Safe Native Deletions**:
   - Integrates with the Windows shell API via `ctypes` (`shell32.dll`) to send deleted files directly to the native Windows Recycle Bin, allowing files to be recovered if deleted by mistake.

---

## Project Structure

```
windows_duplicate_remover/
├── duplicate_remover/
│   ├── __init__.py
│   ├── duplicate_finder.py  # Optimized hashing engine (background thread)
│   ├── gui.py               # Tkinter GUI (custom widgets, theme toggles, preview)
│   └── utils.py             # Recycle Bin ctypes integration, size formatters
├── main.py                  # DPI-aware entry point
├── tests.py                 # Core unit tests (runs matching accuracy tests)
├── requirements.txt         # Package dependencies (Pillow, OpenCV, PyInstaller)
├── build_exe.py             # Packaging automation script
└── README.md                # Documentation (this file)
```

---

## Prerequisites

Ensure you have Python 3.8 or higher installed on your Windows machine.

---

## Installation & Running

1. Open your terminal in the project directory.
2. Install the required external libraries:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application:
   ```bash
   python main.py
   ```

---

## Building a Standalone Executable (`.exe`)

You can compile the application into a single, console-less, portable executable file using PyInstaller.

1. Run the build automation script:
   ```bash
   python build_exe.py
   ```
2. Once the script finishes compiling, your portable executable will be located in:
   `dist/DuplicateRemover.exe`
3. You can copy `DuplicateRemover.exe` to any folder or system, and run it independently without needing Python or external libraries installed!

---

## Running Unit Tests

To run the automated test suite verifying duplicate logic and file metric conditions:
```bash
python tests.py
```
