import subprocess
import os
import io
import time
import socket
from pathlib import Path
from dotenv import load_dotenv
from gtts import gTTS

required_vars = ["TV_IP", "TV_MAC", "LOX_IP", "LOX_UDP_PORT", "LOX_USER", "LOX_PASS", "IP_BINDING", "SERVER_UDP_PORT", "BEEP_START", "BEEP_END"]
ALEXA_MUTED = False


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
            play("vypínám systém")
            os.system("echo mem | sudo tee /sys/power/state")
        elif command == "disable_mic":
            ALEXA_MUTED = True
            send_udp_payload("mic_disabled", loxone_ip, loxone_port)
            print("🛑 Alexa Voice Engine MUTED")
            play("vypínám mikrofon, alexa neposlouchá příkazy")
        elif command == "enable_mic":
            ALEXA_MUTED = False
            print("🟢 Alexa Voice Engine ACTIVE")
            play("mikrofon zapnut, alexa poslouchá")
        elif command == "mic_status":
            # Check the real variable state in memory
            if ALEXA_MUTED:
                # If muted, tell Loxone to reset (turn off) the mic status
                send_udp_payload("mic_disabled", loxone_ip, loxone_port)
            else:
                # If unmuted, tell Loxone to set (turn on) the mic status
                send_udp_payload("mic_enabled", loxone_ip, loxone_port)


if __name__ == "__main__":
    initialize_var()
    cfg = get_config()
    # print(type(cfg))
    # print(cfg["TV_MAC"])
    # print(cfg["LOX_USER"])
    # tea_timer(1)
    # beep_start()
    # beep_end()
    # play("nejkrásnější široko daleko je sluníčko")
    # send_udp_payload("mic_disabled")
    # send_udp_payload("mic_enabled")
    send_udp_payload("mic_enabled", cfg["LOX_IP"], int(cfg.get("LOX_UDP_PORT", 5005)))
