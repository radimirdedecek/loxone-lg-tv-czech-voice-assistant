import os
import urllib.request
import numpy as np
import time
import warnings
import threading
from openwakeword.model import Model
from pathlib import Path
from whisper import whisper, speak_and_wait, verify_alexa_local
from collections import deque
import util

# Testing simulated offline mode. Blocks WAN calls (gTTS, etc.) while leaving LAN (192.168.x.x / 127.0.0.1) open.
# util.set_offline_mode(True)
util.set_offline_mode(False)

# Testing simulated start alexa.service mode = 1, manual start = 0
# os.environ["ALEXA_USE_JABRA"] = "1" 

# Tell ONNX to stop looking for CUDA
os.environ["ORT_LOGGING_LEVEL"] = "3"
# Silence Python warnings in the console
warnings.filterwarnings("ignore", category=UserWarning, module="onnxruntime")

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "oww_models"
MODEL_DIR.mkdir(exist_ok=True)
MODEL_PATH = str(MODEL_DIR / "alexa.onnx")
MAX_CONSECUTIVE_ERRORS = 5
THRESHOLD_LOW = float(os.getenv("THRESHOLD_LOW", "0.62")) 
THRESHOLD_HIGH = float(os.getenv("THRESHOLD_HIGH", "0.95"))
NET_CHECK_INTERVAL = 45  # Re-check internet every 45 seconds
util.setup_audio_output()

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

    recorder = util.create_pvrecorder(frame_length=1280) # 1280 samples = 80ms chunks
    recorder.start()

    # Start the Loxone UDP sleep listener in a separate thread
    udp_thread = threading.Thread(target=util.listen_for_loxone_udp, daemon=True)
    udp_thread.start()
    time.sleep(0.5)
    print(".\n\033[1;37m" + "=" * 57)
    print(f">>> SYSTEM ACTIVE: \033[1;33m{get_time()} \033[1;37mALEXA is Ready <<<")
    print("=" * 57 + "\033[0m")
    speak_and_wait("posloucham", True)  
    USE_CLOUD_VERIFY = util.is_online()  # dynamically checked via internet ping
    last_net_check = 0
    consecutive_errors = 0
    consecutive_matches = 0 
    audio_ring_buffer = deque(maxlen=24) # Rolling ring buffer to hold the last ~1.9s of audio (24 x 80ms chunks)
    try:
        while True:
            now = time.time()
            if now - last_net_check > NET_CHECK_INTERVAL:
                was_online = USE_CLOUD_VERIFY
                USE_CLOUD_VERIFY = util.is_online()
                last_net_check = now
                # Log status shifts
                if was_online != USE_CLOUD_VERIFY:
                    status_str = "🌐 ONLINE (Google Cloud STT/TTS Active)" if USE_CLOUD_VERIFY else "🔌 OFFLINE (Strict Local Mode Active)"
                    print(f"📡 Network status changed: {status_str}")
            # Dynamic sensitivity based on internet availability
            # Must match 'alexa' across ~240ms of contiguous audio
            # 1 Frame (>= 1): Too sensitive. A quick burst of TV noise or a cough might produce a single random spike to 0.87 for 80 ms, triggering a false wake-up.
            # 2 Frames(>= 2): Ideal. Verifies that the activation peak is real and sustained across adjacent audio chunks while you finish saying the word.
            # 5 Frames(>= 5): Too strict. Real speech peaks fade too fast to sustain 5 consecutive
            REQUIRED_CONSECUTIVE_FRAMES = 2 
            try:
                pcm = recorder.read()
                if pcm:
                    consecutive_errors = 0
                    chunk_np = np.array(pcm, dtype=np.int16)
                    audio_ring_buffer.append(chunk_np)
                    if util.ALEXA_MUTED:
                        time.sleep(0.5)
                        continue  # Skip processing entirely if Loxone turned us off!
                    prediction = model.predict(chunk_np)  # Predict directly on the freshly read chunk
                    prob = prediction["alexa"]
                else:
                    continue
                if prob >= THRESHOLD_LOW:               # changed from 0.85 -> 0.82
                    consecutive_matches += 1        # new adjusting sensitivity
                else:                               # Instead of consecutive_matches = 0, decay slowly!                           
                    consecutive_matches = max(0, consecutive_matches - 1)     # new decay
                if consecutive_matches >= REQUIRED_CONSECUTIVE_FRAMES:        # new adjusting sensitivity
                    util.beep_detected()  # xxx FOR: wake word sensitivity testing xxx
                    consecutive_matches = 0
                    should_trigger = False
                    if prob >= THRESHOLD_HIGH:
                        print(f"DETECTED: ALEXA - High confidence, Bypassing Local Verification ({prob:.2f} >= {THRESHOLD_HIGH}) ...")
                        should_trigger = True
                    else:
                        if len(audio_ring_buffer) > 0:
                            print(f"DETECTED: ALEXA - Running Local Verification ({prob:.2f}) ...")
                            recent_audio = np.concatenate(list(audio_ring_buffer))
                            should_trigger = verify_alexa_local(recent_audio)
                            if should_trigger: print(f"DETECTED: ALEXA - ✅ Verified! Launching Whisper...")
                        else:
                            should_trigger = False
                        
                    if should_trigger:
                        audio_ring_buffer.clear()
                        whisper(USE_CLOUD_VERIFY)
                        # Reset openWakeWord model state
                        model = Model(wakeword_model_paths=[MODEL_PATH])
                        print(".\n\033[1;37m" + "=" * 65)
                        print(f">>> System Re-initialized: \033[1;33m{get_time()} \033[1;37mALEXA is Ready <<<")
                        print("=" * 65 + "\033[0m")
                    else:
                        print("DETECTED: ALEXA - ❌ ALEXA Rejected by Local Verification! Resuming listener...")
                        audio_ring_buffer.clear()
                    
                    # OLD:
                    # print(f"DETECTED: ALEXA ({prob:.2f})")
                    # consecutive_matches = 0         # new Reset counter and trigger cloud/local transcription
                    # whisper()
                    # # NUCLEAR RESET: Re-create the model object to wipe everything
                    # model = Model(wakeword_model_paths=[MODEL_PATH])
                    # # time.sleep(1.0)
                    # print(".\n\033[1;37m" + "=" * 65)
                    # print(f">>> System Re-initialized: \033[1;33m{get_time()} \033[1;37mALEXA is Ready <<<")
                    # print("=" * 65 + "\033[0m")
            # except Exception as loop_error:
            #     print(f"⚠️ Internal engine hiccup: {loop_error}. Auto-recovering stack...")
            #     time.sleep(2)
            #     continue  # Keeps the loop alive no matter what
            except Exception as e:
                consecutive_errors += 1
                print(f"⚠️ Internal engine hiccup: Failed to read from device. ({consecutive_errors}/{MAX_CONSECUTIVE_ERRORS})")
                
                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    print("🔄 USB/PipeWire stream disconnected. Auto-recovering PvRecorder stack...")
                    
                    # 1. Safely tear down stale C object
                    try:
                        recorder.stop()
                        recorder.delete()
                    except Exception:
                        pass

                    # 2. Pause to allow USB bus & PipeWire to finish re-enumeration
                    time.sleep(2)

                    # 3. Re-create a fresh recorder instance
                    try:
                        recorder = util.create_pvrecorder(frame_length=1280)
                        recorder.start()
                        consecutive_errors = 0
                        print("✅ PvRecorder stack successfully recovered!")
                    except Exception as rec_err:
                        print(f"❌ Re-initialization failed: {rec_err}. Retrying in 3s...")
                        time.sleep(3)

            time.sleep(0.01)
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        recorder.stop()
        recorder.delete()


if __name__ == "__main__":
    main()
