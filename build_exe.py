import subprocess
import sys

def build():
    print("Building executable...")
    command = [
        sys.executable, "-m", "PyInstaller",
        "--name=OBS_Shot_Extractor",
        "--noconfirm",
        "--windowed", 
        "main.py"
    ]
    subprocess.run(command)
    print("Build complete! Check the 'dist' folder.")

if __name__ == "__main__":
    build()
