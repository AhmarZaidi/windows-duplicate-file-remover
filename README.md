# Windows Duplicate File Remover

<!-- [![Windows Duplicate File Remover Screenshot](screenshot.png)](#) -->
*A modern, fast, and accurate Windows desktop utility to scan, find, preview, and safely delete duplicate files.*

---

## 🚀 Key Features

* **Multi-Pass Scan Engine**: Fast comparison using file size $\rightarrow$ partial hash (8 KB) $\rightarrow$ full MD5 hash.
* **Scan Customization**: Filter by minimum file size (Bytes/KB/MB/GB) and exclude folders (e.g. `node_modules`, `.git`).
* **Windows 11 UI Style**: 3-state Theme Toggle (Light/Dark/System), custom checkboxes, row highlighting, and group headers.
* **Smart Quick Select**: One-click selection options (Keep Oldest, Keep Newest, Keep Largest, Keep Smallest, Clear Selection).
* **Collapsible Preview Pane**: View image thumbnails, video keyframes (via OpenCV), and text file snippets.
* **Compact Path Display**: Shows the common directory base in the group header, displaying only the relative diff path per file.
* **Safe Deletion**: Deletes files using the native Windows shell API, sending them directly to the **Recycle Bin**.
* **Data Export**: Export scanning results to CSV or JSON.

---

## 📥 Usage

### Option 1: Standalone Portable Executable (Recommended)
1. Go to [Releases](https://github.com/AhmarZaidi/windows-duplicate-file-remover/releases/latest).
2. Download the latest `DuplicateRemover.exe`.
3. Double-click to run! (No Python or installation required).

### Option 2: Run from Source
1. Clone this repository and open the project directory.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application:
   ```bash
   python main.py
   ```

---

## 🛠️ Build and Development

### Compile to EXE
To build the standalone portable executable yourself:
```bash
python build_exe.py
```
The compiled artifact will be located at `dist/DuplicateRemover.exe`.

### Run Unit Tests
To run the scanning engine test suite:
```bash
python -m unittest tests.py
```

---

## 📂 Project Layout

* `duplicate_remover/`
  * `duplicate_finder.py`: Hashing and matching engine (runs in a background thread).
  * `gui.py`: Tkinter-based Windows 11 style UI, preview generation, and widget trees.
  * `utils.py`: Recycle Bin integration (`ctypes`) and file formatters.
* `main.py`: DPI-aware application entry point.
* `build_exe.py`: Spec compilation and PyInstaller build automate.
* `tests.py`: Unit tests for matching accuracy.
