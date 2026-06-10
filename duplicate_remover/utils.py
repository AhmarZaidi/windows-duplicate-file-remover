import os
import sys
import ctypes
from ctypes import windll, Structure, c_wchar_p, c_uint, c_int, byref

# Define the Windows Shell API SHFILEOPSTRUCTW structure for sending files to the Recycle Bin.
class SHFILEOPSTRUCTW(Structure):
    _fields_ = [
        ("hwnd", ctypes.c_void_p),
        ("wFunc", c_uint),
        ("pFrom", c_wchar_p),
        ("pTo", c_wchar_p),
        ("fFlags", c_uint),
        ("fAnyOperationsAborted", c_int),
        ("hNameMappings", ctypes.c_void_p),
        ("lpszProgressTitle", c_wchar_p),
    ]

# SHFileOperation constants
FO_DELETE = 3
FOF_ALLOWUNDO = 0x0040
FOF_NOCONFIRMATION = 0x0010  # Don't prompt the user
FOF_NOERRORUI = 0x0400       # Don't show error dialogs
FOF_SILENT = 0x0004          # Don't show progress dialog

def send_to_recycle_bin(paths) -> bool:
    """
    Sends one or more files/folders to the Windows Recycle Bin.
    Accepts a single path string or a list of path strings.
    Returns True if successful, False otherwise.
    """
    if isinstance(paths, str):
        paths = [paths]
    
    if not paths:
        return True

    if sys.platform != 'win32':
        return False

    try:
        abs_paths = [os.path.abspath(p).replace('/', '\\') for p in paths]
        p_from = "\0".join(abs_paths) + "\0\0"
        
        fileop = SHFILEOPSTRUCTW()
        fileop.hwnd = None
        fileop.wFunc = FO_DELETE
        fileop.pFrom = p_from
        fileop.pTo = None
        fileop.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_NOERRORUI | FOF_SILENT
        fileop.fAnyOperationsAborted = 0
        fileop.hNameMappings = None
        fileop.lpszProgressTitle = None

        result = windll.shell32.SHFileOperationW(byref(fileop))
        return result == 0
    except Exception:
        return False

def format_size(size_in_bytes: int) -> str:
    """
    Formats bytes into human-readable strings (e.g. 1.25 MB).
    """
    if size_in_bytes < 0:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_in_bytes < 1024.0:
            if unit == 'B':
                return f"{size_in_bytes} B"
            return f"{size_in_bytes:.2f} {unit}"
        size_in_bytes /= 1024.0
    return f"{size_in_bytes:.2f} PB"

def get_windows_system_theme() -> str:
    """Queries the Windows registry to check if Dark Mode is active."""
    if sys.platform != 'win32':
        return "dark"
    try:
        import winreg
        registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
        key = winreg.OpenKey(registry, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return "light" if value == 1 else "dark"
    except Exception:
        return "dark"  # Default fallback
