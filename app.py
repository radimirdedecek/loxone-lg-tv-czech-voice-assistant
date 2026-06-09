import os
from dotenv import load_dotenv
import urllib.request
import numpy as np
from openwakeword.model import Model
from pvrecorder import PvRecorder
from pathlib import Path
import time
from wisper import wisper, speak
import warnings

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


def load_config(var_name):
    var = os.getenv(var_name)
    if var is None:
        print(f"❌ ERROR: .env file, variable '{var_name}' not defined.")
    return var


def main():
    download_alexa_model()
    if not os.path.exists(MODEL_PATH):
        print(f"❌ ERROR: model_path {MODEL_PATH} not found.")
        return

    print("Initializing env variables...")
    if not os.path.exists(".env"):
        print(f"❌ ERROR: .env file not found.")
        return
    load_dotenv()
    TV_IP = load_config("TV_IP")
    TV_MAC = load_config("TV_MAC")
    LOX_IP = load_config("LOX_IP")
    LOX_USER = load_config("LOX_USER")
    LOX_PASS = load_config("LOX_PASS")
    if None in [TV_IP, TV_MAC, LOX_IP, LOX_USER, LOX_PASS]:
        return

    print("Initializing openWakeWord...")
    model = Model(wakeword_model_paths=[MODEL_PATH])

    # pvrecorder: 1280 samples = 80ms chunks
    recorder = PvRecorder(frame_length=1280, device_index=-1)
    recorder.start()

    print("\n" + "=" * 45)
    print(" >>> SYSTEM ACTIVE: ALEXA is Ready <<<")
    print("=" * 45 + "\n")
    speak("posloucham")
    try:
        while True:
            pcm = recorder.read()
            input_data = np.array(pcm, dtype=np.int16)

            # 1. Get prediction
            prediction = model.predict(input_data)
            prob = prediction["alexa"]

            # if prob > 0.15:
            #     print(f"Match Confidence: {prob:.4f}", end="\r")

            # 2. Trigger point
            if prob >= 0.80:
                print(f"\nDETECTED: ALEXA ({prob:.2f})")
                wisper()
                # NUCLEAR RESET: Re-create the model object to wipe everything
                model = Model(wakeword_model_paths=[MODEL_PATH])
                time.sleep(1.0)
                print("\n\n\n\n\n" + "=" * 45)
                print(">>> System Re-initialized.")
                print(">>> ALEXA is Ready for next command.")
                print("=" * 45)

    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        recorder.stop()
        recorder.delete()


if __name__ == "__main__":
    main()
