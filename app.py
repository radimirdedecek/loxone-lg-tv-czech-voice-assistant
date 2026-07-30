import os
import urllib.request
import numpy as np
import time
import warnings
import threading
from openwakeword.model import Model
from pvrecorder import PvRecorder
from pathlib import Path
from whisper import whisper, speak_and_wait
import util

# Testing simulated offline mode. Blocks WAN calls (gTTS, etc.) while leaving LAN (192.168.x.x / 127.0.0.1) open.
util.set_offline_mode(False)

# Tell ONNX to stop looking for CUDA
os.environ["ORT_LOGGING_LEVEL"] = "3"
# Silence Python warnings in the console
warnings.filterwarnings("ignore", category=UserWarning, module="onnxruntime")

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "oww_models"
MODEL_DIR.mkdir(exist_ok=True)
MODEL_PATH = str(MODEL_DIR / "alexa.onnx")


def download_alexa_model():
    url = "https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/alexa_v0.1.onnx"
    if not os.path.exists(MODEL_PATH):
        print("Downloading production Alexa model...")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"})
            with urllib.request.urlopen(req) as response, open(MODEL_PATH, "wb") as out_file:
                out_file.write(response.read())
            print("Download successful!")
        except Exception as e:
            print(f"Download failed: {e}")


def get_time():
    return f"{time.strftime('%d.%m.%Y %H:%M:%S')}"


def main():
    if not util.initialize_var():
        return

    download_alexa_model()
    if not os.path.exists(MODEL_PATH):
        print(f"❌ ERROR: model_path {MODEL_PATH} not found.")
        return

    print("Initializing openWakeWord...")
    model = Model(wakeword_model_paths=[MODEL_PATH])

    # pvrecorder: 1280 samples = 80ms chunks
    recorder = PvRecorder(frame_length=1280, device_index=-1)
    recorder.start()

    # Start the Loxone UDP sleep listener in a separate thread
    udp_thread = threading.Thread(target=util.listen_for_loxone_udp, daemon=True)
    udp_thread.start()
    time.sleep(0.5)
    print(".\n\033[1;37m" + "=" * 57)
    print(f">>> SYSTEM ACTIVE: \033[1;33m{get_time()} \033[1;37mALEXA is Ready <<<")
    print("=" * 57 + "\033[0m")
    speak_and_wait("posloucham", True)
    # Tune these two variables in your main loop
    THRESHOLD = 0.82                                # changed from 0.85 -> 0.82
    REQUIRED_CONSECUTIVE_FRAMES = 3                 # Must match 'alexa' across ~240ms of contiguous audio
                                                    # changed from 2 -> 3
    # 1 Frame (>= 1): Too sensitive. A quick burst of TV noise or a cough might produce a single random spike to 0.87 for 80 ms, triggering a false wake-up.
    # 2 Frames(>= 2): Ideal. Verifies that the activation peak is real and sustained across adjacent audio chunks while you finish saying the word.
    # 5 Frames(>= 5): Too strict. Real speech peaks fade too fast to sustain 5 consecutive
    consecutive_matches = 0 
    try:
        while True:
            try:
                pcm = recorder.read()
                if util.ALEXA_MUTED:
                    time.sleep(0.5)
                    continue  # Skip processing entirely if Loxone turned us off!
                input_data = np.array(pcm, dtype=np.int16)
                prediction = model.predict(input_data)
                prob = prediction["alexa"]
                if prob >= THRESHOLD:               # changed from 0.85 -> 0.82
                    consecutive_matches += 1        # new adjusting sensitivity
                else:                               # Instead of consecutive_matches = 0, decay slowly!                           
                    consecutive_matches = max(0, consecutive_matches - 1)     # new decay
                if consecutive_matches >= REQUIRED_CONSECUTIVE_FRAMES:        # new adjusting sensitivity
                    print(f"DETECTED: ALEXA ({prob:.2f})")
                    consecutive_matches = 0         # new Reset counter and trigger cloud/local transcription
                    whisper()
                    # NUCLEAR RESET: Re-create the model object to wipe everything
                    model = Model(wakeword_model_paths=[MODEL_PATH])
                    # time.sleep(1.0)
                    print(".\n\033[1;37m" + "=" * 65)
                    print(f">>> System Re-initialized: \033[1;33m{get_time()} \033[1;37mALEXA is Ready <<<")
                    print("=" * 65 + "\033[0m")
            except Exception as loop_error:
                print(f"⚠️ Internal engine hiccup: {loop_error}. Auto-recovering stack...")
                time.sleep(2)
                continue  # Keeps the loop alive no matter what
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        recorder.stop()
        recorder.delete()


if __name__ == "__main__":
    main()
