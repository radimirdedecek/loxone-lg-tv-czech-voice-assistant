import subprocess
import os
import time
from pathlib import Path
from dotenv import load_dotenv
from gtts import gTTS

required_vars = ["TV_IP", "TV_MAC", "LOX_IP", "LOX_USER", "LOX_PASS", "BEEP_START", "BEEP_END"]


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


def play(txt):
    audio_file = "output.mp3"
    language = "cs"
    tts = gTTS(text=txt, lang=language)
    tts.save(str(audio_file))
    subprocess.Popen(["pw-play", audio_file])


def speak_and_wait(audio_file_name, wait):
    """Plays an audio file and pauses execution until the file finishes completely."""
    BASE_DIR = Path(__file__).resolve().parent
    if not audio_file_name.endswith(".mp3"):
        audio_file_name += ".mp3"
    audio_file = BASE_DIR / "messages" / audio_file_name
    if wait:
        subprocess.run(["pw-play", str(audio_file)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.Popen(["pw-play", audio_file])


def beep_start():
    cfg = get_config()
    subprocess.Popen(["pw-play", "-p", cfg["BEEP_START"]])


def beep_end():
    cfg = get_config()
    subprocess.Popen(["pw-play", "-p", cfg["BEEP_END"]])


def tea_timer(min, txt):
    print(f"⏱️ Tea timer started in background for {min} minutes...")
    time.sleep(min * 60)
    print("🔔 Tea timer finished!")
    play(f"{min} {txt} uběhlo, čaj je hotový.")  # Highly recommend creating a caj_hotov.mp3 file!


if __name__ == "__main__":
    initialize_var()
    # cfg = get_config()
    # print(type(cfg))
    # print(cfg["TV_MAC"])
    # print(cfg["LOX_USER"])
    # tea_timer(1)
    # beep_start()
    beep_end()
    x = 3
    print(f"{x:3}%")
