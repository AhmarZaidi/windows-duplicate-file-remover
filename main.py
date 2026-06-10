import sys
from gui import MainWindow

def main():
    # Set Windows Process DPI Awareness so that the GUI fonts and widgets
    # render with sharp, native resolution instead of being blurry.
    try:
        import ctypes
        # DPI awareness level 1: System DPI aware
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        # Fallback if DPI awareness setting is not supported by the OS version
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

    app = MainWindow()
    app.mainloop()

if __name__ == "__main__":
    main()
