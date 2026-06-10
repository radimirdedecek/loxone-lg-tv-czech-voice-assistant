import subprocess
import os
from pathlib import Path
from dotenv import load_dotenv


def speak(audio_file_name):
    BASE_DIR = Path(__file__).resolve().parent
    if not audio_file_name.endswith(".mp3"):
        audio_file_name += ".mp3"
    audio_file = BASE_DIR / "messages" / audio_file_name
    subprocess.Popen(["pw-play", audio_file])


required_vars = ["TV_IP", "TV_MAC", "LOX_IP", "LOX_USER", "LOX_PASS"]


def initialize_var():
    print("Initializing env variables...")
    if not os.path.exists(".env"):
        print(f"❌ ERROR: .env file not found.")
        return False
    load_dotenv()
    for var_name in required_vars:
        if os.getenv(var_name) is None:
            print(f"❌ CRITICAL ERROR: .env file is missing variable '{var_name}'!")
            print("App execution stopped to prevent crashes.")
            return False
    # print("✅ All environment variables loaded successfully.")
    return True


def get_config():
    return {key: os.getenv(key) for key in required_vars}


if __name__ == "__main__":
    cfg = get_config()
    print(type(cfg))
    print(cfg["TV_MAC"])
    print(cfg["LOX_USER"])
