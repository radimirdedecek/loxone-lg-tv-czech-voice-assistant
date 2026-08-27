import subprocess
import os
import io
import time
import socket
from pathlib import Path
from dotenv import load_dotenv
from gtts import gTTS
from pvrecorder import PvRecorder

required_vars = ["WIIM_IP", "TV_IP", "TV_MAC", "LOX_IP", "LOX_UDP_PORT", "LOX_USER", "LOX_PASS", "IP_BINDING",
                 "SERVER_UDP_PORT", "BEEP_DETECTED", "BEEP_START", "BEEP_END", "SINK_VOL", "MIC_VOL",
                 "THRESHOLD_LOW", "THRESHOLD_HIGH"]
ALEXA_MUTED = False

def check_udp_port_available() -> bool:
    """Verifies that the server UDP port is free before starting another instance."""
    cfg = get_config()
    ip_binding = cfg.get("IP_BINDING", "0.0.0.0")
    server_port = int(cfg.get("SERVER_UDP_PORT", 5005))
    
    test_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        test_sock.bind((ip_binding, server_port))
        test_sock.close()
        return True
    except OSError as e:
        test_sock.close()
        if e.errno == 98:  # Address already in use
            print("\n" + "=" * 65)
            print("❌ CANNOT START APP: ANOTHER INSTANCE IS ALREADY RUNNING!")
            print(f"👉 Port {server_port} is bound by 'alexa.service' or another process.")
            print("👉 Stop the background systemd service first before testing in VSCode:")
            print("   sudo systemctl stop alexa.service")
            print("=" * 65 + "\n")
            return False
        raise e

# Fast, non-blocking check to verify WAN connectivity.
def is_online(host="8.8.8.8", port=53, timeout=0.4) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False
    
# Parses /proc/asound/cards to find the dynamic integer card index for Jabra.
def get_jabra_alsa_card() -> str:
    try:
        with open("/proc/asound/cards", "r") as f:
            for line in f:
                if "jabra" in line.lower():
                    parts = line.strip().split()
                    if parts and parts[0].isdigit():
                        return parts[0]  # Returns integer card string, e.g. "1"
    except Exception as e:
        print(f"⚠️ Error reading /proc/asound/cards: {e}")
    return "1"  # Default fallback index

# Dynamically finds the PulseAudio/PipeWire input source for Jabra mic.
def get_jabra_source_name() -> str | None:
    try:
        result = subprocess.run(["pactl", "list", "short", "sources"],
                                 capture_output=True,text=True,check=True)
        for line in result.stdout.splitlines():
            line_lower = line.lower()
            if "alsa_input" in line_lower and "jabra" in line_lower and "monitor" not in line_lower:
                parts = line.split()
                if len(parts) >= 2:
                    return parts[1]  # Returns e.g. alsa_input.usb-0b0e_...mono-fallback
    except Exception as e:
        print(f"⚠️ Error finding Jabra source via pactl: {e}")
    return None

# Dynamically locks Jabra speaker/mic volumes using a volume pulse to override physical HW button offsets.
def enforce_jabra_volumes(sink_name: str | None = None,sink_volume: float | None = None,mic_volume: float | None = None):
    sink_volume = sink_volume if sink_volume is not None else float(os.getenv("SINK_VOL", "0.9"))
    mic_volume = mic_volume if mic_volume is not None else float(os.getenv("MIC_VOL", "1.0"))
    try:
        time.sleep(2)  # Brief pause for USB re-enumeration
        if sink_name and "jabra" in sink_name.lower():
            # 1. Derive base card name
            card_name = sink_name.replace("alsa_output.", "alsa_card.")
            if "." in card_name: card_name = card_name.rsplit(".", 1)[0]
            # 2. Enforce Duplex Profile (Speaker + Mic active)
            subprocess.run(["pactl", "set-card-profile", card_name, "output:analog-stereo+input:mono-fallback"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            # 3. Always un-mute and max out ALSA Hardware Capture (Headset) on Jabra card
            alsa_card_num = get_jabra_alsa_card()
            subprocess.run(["amixer", "-c", alsa_card_num, "sset", "Headset", "100%", "unmute"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            # 4. SPEAKER VOLUME KICK & LOCK
            subprocess.run(["pactl", "set-sink-volume", sink_name, "10%"], check=False)
            time.sleep(0.1)
            subprocess.run(["pactl", "set-sink-volume", sink_name, f"{int(sink_volume * 100)}%"], check=False)
            # 5. MICROPHONE VOLUME KICK & LOCK
            jabra_source = get_jabra_source_name()
            if jabra_source:
                subprocess.run(["pactl", "set-source-volume", jabra_source, "10%"], check=False)
                time.sleep(0.1)
                subprocess.run(["pactl", "set-source-volume", jabra_source, f"{int(mic_volume * 100)}%"], check=False)
                print(f"🔊 Jabra hardware sync complete: Sink {to_cubic_pct(sink_volume)}, Mic {to_cubic_pct(mic_volume)}")
            else:
                print(f"🔊 Jabra hardware sync complete: Sink {to_cubic_pct(sink_volume)} | ⚠️ Mic source not found")
        else:
            # Fallback for default workstation sound card when Jabra mode is disabled
            subprocess.run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", str(sink_volume)], check=False)
            subprocess.run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SOURCE@", str(mic_volume)], check=False)
            print(f"🔊 Default audio volumes set: Sink {to_cubic_pct(sink_volume)}, Mic {to_cubic_pct(mic_volume)}")
    except Exception as e:
        print(f"⚠️ Could not enforce audio volumes: {e}")
                               
# Checks if Jabra is explicitly requested via environment variable.
def is_jabra_requested() -> bool:
    return os.getenv("ALEXA_USE_JABRA", "0").lower() in ("1", "true", "yes")

# Dynamically finds the PulseAudio/PipeWire sink name for the Jabra speaker.
def get_jabra_sink_name() -> str | None:
    try:
        result = subprocess.run(["pactl", "list", "short", "sinks"],capture_output=True,text=True,check=True)
        for line in result.stdout.splitlines():
            line_lower = line.lower()
            if "jabra" in line_lower and "monitor" not in line_lower:
                parts = line.split() # pactl output format: ID <sink_name> driver sample_spec state
                if len(parts) >= 2:
                    return parts[1]  # Returns active sink name dynamically
    except Exception as e:
        print(f"⚠️ Error scanning sound sinks via pactl: {e}")
    return None

# Configures audio output sink for TTS / audio clips.
def setup_audio_output():
    if is_jabra_requested():
        jabra_sink = get_jabra_sink_name()
        if jabra_sink:
            print(f"🔊 Output Mode: Dedicated Jabra Speaker ({jabra_sink})")
            os.environ["PIPEWIRE_NODE"] = jabra_sink
            os.environ["PULSE_SINK"] = jabra_sink
            enforce_jabra_volumes(jabra_sink)
        else:
            # Fallback if ALEXA_USE_JABRA=1 but device is unplugged / missing
            print("⚠️ Jabra requested (ALEXA_USE_JABRA=1), but device not found! Falling back to System Default.")
            os.environ.pop("PIPEWIRE_NODE", None)
            os.environ.pop("PULSE_SINK", None)
            enforce_jabra_volumes(None)
    else:
        print("🔊 Output Mode: System Default Speaker")
        os.environ.pop("PIPEWIRE_NODE", None)
        os.environ.pop("PULSE_SINK", None)
        enforce_jabra_volumes(None)
        
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
    # Single-instance check: Exit early if background service is active
    if not check_udp_port_available():
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

def beep_detected():  
    cfg = get_config()
    subprocess.Popen(["pw-play", "-p", cfg["BEEP_DETECTED"]])
    
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
            ALEXA_MUTED = True
            send_udp_payload("mic_disabled", loxone_ip, loxone_port)
            print("Received sleep command from Loxone! Triggering suspend...")
            speak_and_wait("vypinam_system", True)
            time.sleep(2)
            subprocess.run(["systemctl", "suspend"])
            time.sleep(5)
            print("🌅 System woke up from sleep (WoL / Manual)! Re-activating Alexa...")
            setup_audio_output() # <---------------- established volume after System woke up from sleep
            speak_and_wait("system_je_zapnuty", True)
            ALEXA_MUTED = False
            send_udp_payload("mic_enabled", loxone_ip, loxone_port)
            time.sleep(0.5)
            send_udp_payload("system_on", loxone_ip, loxone_port)
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

# Calculates PipeWire perceived cubic loudness percentage (v^3 * 100)
def to_cubic_pct(v: float) -> str:
    return f"@ {(v ** 3) * 100:.0f}%"

if __name__ == "__main__":
    initialize_var()
    cfg = get_config()
    # os.environ["ALEXA_USE_JABRA"] = "0" 
    # setup_audio_output()
    # exit()
    JABRA_SINK_NAME=get_jabra_sink_name()
    enforce_jabra_volumes(JABRA_SINK_NAME,sink_volume=.63,mic_volume=1.0)


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

# List of PLAYBACK Hardware Devices 
# aplay -l
#
# get JABRA card num
# N=`aplay -l|grep -i jabra| cut -d':' -f 1|cut -d' ' -f 2`
#
# get JABRA mic & sink names
# amixer -c $N scontrols
# 
# get JABRA PCM volume
# amixer -c $N sget PCM
#
# change JABRA PCM volume to 50%
# amixer -c $N sset PCM 50%
#
# wpctl status
# wpctl set-volume 53 0.9

# PipeWire SINK volume to PCT signal power = 100*volume**3
# volume = 0.63   >  25% signal power
# volume = 0.794  >  50% signal power
# volume = 0.909  >  75% signal power
# volume = 1.0     > 100% signal power
