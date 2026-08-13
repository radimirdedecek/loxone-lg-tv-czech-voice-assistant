import subprocess
import os
import io
import time
import socket
from pathlib import Path
from dotenv import load_dotenv
from gtts import gTTS
from pvrecorder import PvRecorder

required_vars = ["WIIM_IP", "TV_IP", "TV_MAC", "LOX_IP", "LOX_UDP_PORT", "LOX_USER", "LOX_PASS", "IP_BINDING", "SERVER_UDP_PORT", "BEEP_START", "BEEP_END"]
ALEXA_MUTED = False

# Checks if Jabra is explicitly requested via environment variable.
def is_jabra_requested() -> bool:
    return os.getenv("ALEXA_USE_JABRA", "0").lower() in ("1", "true", "yes")

import subprocess
import os

# Dynamically finds the PulseAudio/PipeWire sink name for the Jabra speaker.
def get_jabra_sink_name(sink_name) -> str | None:
    try:
        result = subprocess.run(
            ["pactl", "list", "short", "sinks"],
            capture_output=True,
            text=True,
            check=True
        )
        for line in result.stdout.splitlines():
            if "jabra" in line.lower():
                # pactl output format: ID <sink_name> driver sample_spec state
                parts = line.split()
                if len(parts) >= 2:
                    return parts[1]
    except Exception as e:
        print(f"⚠️ Error finding Jabra sink via pactl: {e}")
    return sink_name

# Configures audio output sink for TTS / audio clips.
def setup_audio_output(JABRA_SINK_NAME):
    if is_jabra_requested():
        print("🔊 Output Mode: Dedicated Jabra Speaker")
        os.environ["PIPEWIRE_NODE"] = JABRA_SINK_NAME
        os.environ["PULSE_SINK"] = JABRA_SINK_NAME
    else:
        print("🔊 Output Mode: System Default Speaker")
        # Clear environment overrides so audio plays via default system device
        os.environ.pop("PIPEWIRE_NODE", None)
        os.environ.pop("PULSE_SINK", None)
        
# Creates PvRecorder instance automatically choosing between Jabra and Default mic.
def create_pvrecorder(frame_length=512): # frame_length=1280 samples = 80ms chunks
    mic_index = -1
    if is_jabra_requested():
        jabra_idx = mic_index
        devices = PvRecorder.get_available_devices()
        for index, device_name in enumerate(devices):
            name_lower = device_name.lower()
            if "jabra" in name_lower and "monitor" not in name_lower:
                jabra_idx = index
        if jabra_idx != mic_index:
            print(f"🎙️ Input Mode: Jabra physical mic (Index [{jabra_idx}])")
            mic_index = jabra_idx
        else:
            print("⚠️ Jabra requested but not found! Falling back to Default Mic.")
    else:
        print("🎙️ Input Mode: System Default Microphone")
    return PvRecorder(device_index=mic_index, frame_length=frame_length)

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
    cfg = get_config()
    lox_ip = cfg.get("LOX_IP")
    lox_port = int(cfg.get("LOX_UDP_PORT", 5005))

    # Since ALEXA_MUTED initializes as False, immediately let Loxone know the mic is live
    send_udp_payload("mic_enabled", lox_ip, lox_port)
    print("📢 Boot Sync: Sent initial microphone status ('mic_enabled') to Loxone.")
    return True


def get_config():
    return {key: os.getenv(key) for key in required_vars}


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
                ["espeak-ng", "-v", "cs+f4", "--stdout", txt],
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
    error_file = BASE_DIR / "messages" / "error.mp3"
    if not audio_file.exists():
        print(f"⚠️ Audio file missing: '{audio_file}'. Playing 'error.mp3' fallback...")
        subprocess.Popen(["pw-play", error_file])
        return
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
    speak_and_wait("caj_je_hotovy", True)


def send_udp_payload(payload_string, ip, port):
    # Sends a raw UDP string message
    try:
        # Create a standard Internet UDP socket
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            # Encode the text string to raw bytes and fire it over the network
            sock.sendto(payload_string.encode('utf-8'), (ip, int(port)))
            print(f"📡 UDP Sent to ({ip}:{port}) -> '{payload_string}'")
    except Exception as e:
        print(f"❌ Failed to send UDP packet: {e}")


def listen_for_loxone_udp():
    cfg = get_config()
    ip_binding = cfg.get("IP_BINDING", "0.0.0.0")        # "0.0.0.0" Listen on all local interfaces
    server_port = int(cfg.get("SERVER_UDP_PORT"))  # Choose any free custom port
    loxone_port = int(cfg.get("LOX_UDP_PORT"))
    loxone_ip = cfg.get("LOX_IP")
    global ALEXA_MUTED
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((ip_binding, server_port))

    print(f"Loxone Listener active on server port {server_port}...")
    while True:
        data, addr = sock.recvfrom(1024)
        command = data.decode('utf-8').strip()
        if command == "sleep_ws":
            print("Received sleep command from Loxone! Triggering suspend...")
            speak_and_wait("vypinam_system", True)
            os.system("echo mem | sudo tee /sys/power/state")
        elif command == "disable_mic":
            ALEXA_MUTED = True
            send_udp_payload("mic_disabled", loxone_ip, loxone_port)
            print("🛑 Alexa Voice Engine MUTED")
            speak_and_wait("mikrofon_vypnut", True)
        elif command == "enable_mic":
            ALEXA_MUTED = False
            print("🟢 Alexa Voice Engine ACTIVE")
            speak_and_wait("mikrofon_zapnut", True)
        elif command == "mic_status":
            # Check the real variable state in memory
            if ALEXA_MUTED:
                # If muted, tell Loxone to reset (turn off) the mic status
                send_udp_payload("mic_disabled", loxone_ip, loxone_port)
            else:
                # If unmuted, tell Loxone to set (turn on) the mic status
                send_udp_payload("mic_enabled", loxone_ip, loxone_port)

_ORIG_CONNECT = socket.socket.connect
def set_offline_mode(enabled=True):
    """
    Toggles simulated offline mode for the current Python process.
    - enabled=True : Blocks WAN calls (gTTS, etc.) while leaving LAN (192.168.x.x / 127.0.0.1) open.
    - enabled=False: Restores full internet access.
    """
    if not enabled:
        socket.socket.connect = _ORIG_CONNECT
        # print("🌐 Offline simulator: OFF (Normal internet access restored)")
        return
    def guarded_connect(self, address):
        host = address[0]
        # Allow local connections (LAN and Localhost)
        if host.startswith("192.168.") or host.startswith("127.") or host == "localhost":
            return _ORIG_CONNECT(self, address)
        # Block any external IP/domain (simulates no internet for gTTS/cloud APIs)
        raise socket.error("[Simulated WAN Block] Network interface offline")
    socket.socket.connect = guarded_connect
    print("\n")
    print(67 * "#")
    print("###  🌐 Offline simulator: ON (External WAN calls are blocked)  ###")
    print(67 * "#","\n")

if __name__ == "__main__":
    initialize_var()
    cfg = get_config()
    
    # print(type(cfg))
    # print(cfg["TV_MAC"])
    # print(cfg["LOX_USER"])
    # tea_timer(1)
    # beep_start()
    # beep_end()
    # send_udp_payload("mic_disabled")
    # send_udp_payload("mic_enabled")
    # import util
    # util.set_offline_mode(True)
    # send_udp_payload("mic_enabled", cfg["LOX_IP"], int(cfg.get("LOX_UDP_PORT", 5005)))
    # tea_timer(3, "minuty")
    # print(get_jabra_device_index())
    # recorder = create_pvrecorder(frame_length=1280) # openWakeWord uses 1280 (80ms)
