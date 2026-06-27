import subprocess
import os
import io
import time
import socket
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


def play1(txt):
    language = "cs"
    try:
        fp = io.BytesIO()
        tts = gTTS(text=txt, lang=language)
        tts.write_to_fp(fp)
        fp.seek(0)
        process = subprocess.Popen(
            ["pw-play", "-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        process.communicate(input=fp.read())
    except Exception as e:
        print(f"❌ RAM Audio Playback engine failed: {e}")


def play(txt):
    language = "cs"
    # 🌐 STRATEGY 1: Try High-Quality Online gTTS via RAM
    try:
        fp = io.BytesIO()
        tts = gTTS(text=txt, lang=language)
        tts.write_to_fp(fp)
        fp.seek(0)
        process = subprocess.Popen(["pw-play", "-"], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        process.communicate(input=fp.read())
        return  # Success! Exit the function.
    except Exception as network_error:
        print(f"⚠️ Internet down or gTTS failed. Switching to local offline TTS... ({network_error})")
        # 🔌 STRATEGY 2: Local Offline Fallback using espeak mapped directly to PipeWire
        try:
            # espeak parameters:
            # -v cs (Czech voice)
            # -v cs+f3 (Optional: switch to a smoother female variant if preferred)
            # --stdout (Streams raw audio straight out of the process)
            espeak_process = subprocess.Popen(
                ["espeak", "-v", "cs+f4", language, "--stdout", txt],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )
            # Pipe espeak's raw audio bytes directly into your active PipeWire audio speaker pool
            pw_process = subprocess.Popen(["pw-play", "-"], stdin=espeak_process.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            # Wait for playback to finish cleanly
            pw_process.communicate()
        except Exception as offline_error:
            print(f"❌ Both online and offline voice engines failed: {offline_error}")


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


def listen_for_loxone_sleep():
    UDP_IP = "0.0.0.0"       # Listen on all local interfaces
    UDP_PORT = 5005          # Choose any free custom port

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))

    print(f"Loxone Sleep Listener active on port {UDP_PORT}...")
    while True:
        data, addr = sock.recvfrom(1024)
        if data.decode('utf-8').strip() == "sleep_ws":
            print("Received sleep command from Loxone! Triggering suspend...")
            os.system("echo mem | sudo tee /sys/power/state")


if __name__ == "__main__":
    initialize_var()
    # cfg = get_config()
    # print(type(cfg))
    # print(cfg["TV_MAC"])
    # print(cfg["LOX_USER"])
    # tea_timer(1)
    # beep_start()
    beep_end()
    play("nejkrásnější široko daleko je sluníčko")
