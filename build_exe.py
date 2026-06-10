import os
import sys
import subprocess

def install_dependencies():
    print("==========================================================")
    print("Checking and installing dependencies from requirements.txt")
    print("==========================================================")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)
        print("Dependencies installed successfully.\n")
    except Exception as e:
        print(f"Warning: Could not automatically install dependencies: {e}")
        print("Please run manually: pip install -r requirements.txt\n")

def run_build():
    print("==========================================================")
    print("Building standalone DuplicateRemover.exe using PyInstaller")
    print("==========================================================")
    
    # PyInstaller arguments:
    # --onefile: Packages the app as a single standalone executable
    # --noconsole: Hides the terminal window on launch (GUI mode only)
    # --name: Names the output executable file
    # --clean: Cleans PyInstaller cache before building
    cmd = [
        "pyinstaller",
        "--onefile",
        "--noconsole",
        "--name=DuplicateRemover",
        "--clean",
        "main.py"
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print("\n==========================================================")
        print("BUILD COMPLETED SUCCESSFULY!")
        print(f"Your standalone executable is in: {os.path.abspath('dist/DuplicateRemover.exe')}")
        print("==========================================================")
    except FileNotFoundError:
        print("\nError: 'pyinstaller' command not found in your PATH.")
        print("Attempting to run pyinstaller via python module interface...")
        try:
            mod_cmd = [sys.executable, "-m", "PyInstaller", "--onefile", "--noconsole", "--name=DuplicateRemover", "--clean", "main.py"]
            subprocess.run(mod_cmd, check=True)
            print("\n==========================================================")
            print("BUILD COMPLETED SUCCESSFULY!")
            print(f"Your standalone executable is in: {os.path.abspath('dist/DuplicateRemover.exe')}")
            print("==========================================================")
        except Exception as ex:
            print(f"\nBuild failed: {ex}")
            print("Please ensure pyinstaller is installed by running: pip install pyinstaller")
    except subprocess.CalledProcessError as e:
        print(f"\nBuild failed during PyInstaller compilation: {e}")
    except Exception as e:
        print(f"\nAn unexpected error occurred during build: {e}")

if __name__ == "__main__":
    # Ensure working directory is the script folder
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    install_dependencies()
    run_build()
