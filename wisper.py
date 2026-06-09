import numpy as np
from pvrecorder import PvRecorder
from faster_whisper import WhisperModel
import wave
from unidecode import unidecode
from thefuzz import fuzz
import time
import asyncio
import threading
from lg_tv import send_lg_cmd
from loxone import async_send_lox_cmd
import subprocess
from pathlib import Path

# --- CONFIG ---
WHISPER_MODEL_SIZE = "small"  # Options: 'tiny', 'base', 'small' , "medium" (small is great for Czech)
commands = {
    # LOXONE shading
    "zavri zaluzie v kuchyni": ("lox", ("z.kuchyn", "down")),
    "zavri zaluzie v obyvaku": ("lox", ("z.obyvak", "down")),
    "zavri zaluzie na terasu": ("lox", ("z.terasa", "down")),
    "dej zaluzie v kuchyni dolu": ("lox", ("z.kuchyn", "down")),
    "dej zaluzie v obyvaku dolu": ("lox", ("z.obyvak", "down")),
    "dej zaluzie na terasu dolu": ("lox", ("z.terasa", "down")),
    "dej zaluzie v kuchyni nahoru": ("lox", ("z.kuchyn", "up")),
    "dej zaluzie v obyvaku nahoru": ("lox", ("z.obyvak", "up")),
    "dej zaluzie na terasu nahoru": ("lox", ("z.terasa", "up")),
    "zavri zaluzie": ("lox", ("z.kuchyn z.obyvak z.terasa", "down")),
    "otevri zaluzie v kuchyni": ("lox", ("z.kuchyn", "down shade")),
    "otevri zaluzie v obyvaku": ("lox", ("z.obyvak", "down shade")),
    "otevri zaluzie na terasu": ("lox", ("z.terasa", "down shade")),
    "otevri zaluzie": ("lox", ("z.kuchyn z.obyvak z.terasa", "down shade")),
    # LOXONE lights
    "rozsvit svetlo": ("lox", ("sv.obyvak", "2")),
    "rozsvit stredni svetlo": ("lox", ("sv.obyvak", "2")),
    "rozsvit svetlo naplno": ("lox", ("sv.obyvak", "on")),
    "rozsvit svetlo na maximum": ("lox", ("sv.obyvak", "on")),
    "zhasni svetlo": ("lox", ("sv.obyvak", "off")),
    "rozsvit nocni svetlo": ("lox", ("sv.obyvak", "3")),
    "ztlum svetlo": ("lox", ("sv.obyvak", "3")),
    "rozsvit nad stolem": ("lox", ("sv.obyvak", "V2/on")),
    "zhasni nad stolem": ("lox", ("sv.obyvak", "V2/off")),
    "rozsvit v kuchyni": ("lox", ("sv.obyvak", "AI5/on")),
    "zhasni v kuchyni": ("lox", ("sv.obyvak", "AI1/off AI5/off AI7/off AI8/off")),
    "rozsvit v obyvaku": ("lox", ("sv.obyvak", "AI3/on")),
    "zhasni v obyvaku": ("lox", ("sv.obyvak", "AI3/off")),
    "zhasni lampicku": ("lox", ("zasuvka.obyvak", "off on")),
    # LOXONE gate
    "zavri branu": ("lox", ("brana", "pulse")),
    "otevri branu": ("lox", ("brana", "pulse")),
    # LG TV Commands
    "zapni televizi": ("lg", "on"),
    "vypni televizi": ("lg", "off"),
    "zapni zvuk": ("lg", "mute off"),
    "vypni zvuk": ("lg", "mute on"),
    "hlasitejc": ("lg", "+"),
    "potisejc": ("lg", "-"),
}


def speak(audio_file_name):
    BASE_DIR = Path(__file__).resolve().parent
    if not audio_file_name.endswith(".mp3"):
        audio_file_name += ".mp3"
    audio_file = BASE_DIR / "messages" / audio_file_name
    subprocess.Popen(["pw-play", audio_file])


def run_command(command_tuple):
    if not command_tuple or not isinstance(command_tuple, tuple):
        print(f"❌ ERROR: command is not a valid tuple")
        return None
    system_type, cmd_data = command_tuple
    if system_type == "lg":
        print(f"CALLING LG TV API: {cmd_data}")
        return send_lg_cmd(cmd_data)
    elif system_type == "lox":
        if not cmd_data or not isinstance(cmd_data, tuple):
            print(f"❌ ERROR: loxone cmd_data is not a valid tuple")
            return None
        targets, actions = cmd_data
        print(f"CALLING LOXONE API: {targets}/{actions}")
        threading.Thread(target=lambda: asyncio.run(async_send_lox_cmd(targets, actions)), daemon=True).start()
        return "OK"
    print(f"❌ ERROR: command system '{system_type}' not recognized")
    return None


def process_smart_home_intent(raw_text):
    text = unidecode(raw_text.lower())
    collapsed_spoken = text.replace(" ", "")
    print(f"Processing Raw Text ...")
    print(f"          raw_text: {raw_text}")
    print(f"collapsed raw_text: {collapsed_spoken}")
    best_match = None
    highest_score = 0
    for target_phrase, command_tuple in commands.items():
        # Collapse the target phrase too
        clean_target = unidecode(target_phrase.lower())
        collapsed_target = clean_target.replace(" ", "")

        # 1. Flexible Length Guard (Character count instead of word count)
        # Allow +/- 20% difference in total character length
        len_diff = abs(len(collapsed_spoken) - len(collapsed_target))
        if len_diff > 5:  # If the character count is way off, skip
            continue

        # 2. Compare the collapsed strings
        # This solves the "zeluz je" vs "zaluzie" problem
        score = fuzz.ratio(collapsed_spoken, collapsed_target)

        if score > highest_score:
            highest_score = score
            best_match = (target_phrase, command_tuple, collapsed_target)

    if highest_score > 70:
        phrase, command_tuple, collapsed_target = best_match
        print(f"  collapsed target: {collapsed_target}")
        print(f" MATCH FOUND ({highest_score}%): {phrase} -> {command_tuple}")
        return [f"🚀 ACTION: {phrase}", command_tuple]
    return ["❌ Command not Recognised", None]


# --- TEST ---
# [target_phrase, cmd] = process_smart_home_intent("avri branu")
# [target_phrase, cmd] = process_smart_home_intent("Zauři šeluzie")
# exit()


def record_command(recorder, duration=3):
    """Records audio for a fixed duration after the wake word"""
    print(f"Listening to command for {duration}s...")
    frames = []
    for _ in range(0, int(16000 / 1280 * duration)):
        frames.extend(recorder.read())

    # # This stretches the volume to the maximum clear level
    # audio_data = np.array(frames, dtype=np.int16)
    # audio_data = audio_data.astype(np.float32)
    # max_val = np.max(np.abs(audio_data))
    # if max_val > 0:
    #     audio_data = audio_data / max_val
    # audio_data = (audio_data * 32767).astype(np.int16)
    # # ---------------------------------

    # Save to temporary file for Whisper
    temp_file = "command.wav"
    with wave.open(temp_file, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(16000)
        wf.writeframes(np.array(frames, dtype=np.int16).tobytes())
        # wf.writeframes(audio_data.tobytes())
    return temp_file


def wisper():
    print("Loading Whisper Czech Brain... (Please wait, downloading if first time)")
    # Initialize Whisper first, You can use 8 or 12 threads on a Xeon!
    speak("co_chces")
    whisper = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8", cpu_threads=8)

    # NOW initialize and start the recorder
    recorder = PvRecorder(frame_length=1280, device_index=-1)

    print("Whisper Ready! Now recording...")

    recorder.start()

    # 1. Record
    audio_file = record_command(recorder, duration=4)
    recorder.stop()  # Stop recording so CPU can focus on transcribing

    print("Transcribing...")
    # 2. Transcribe
    # Use these settings for the best Czech speed/accuracy balance
    segments, info = whisper.transcribe(
        audio_file,
        language="cs",
        beam_size=5,  # Better accuracy for "Zavři"
        vad_filter=True,  # Removes silence before processing
        # word_timestamps=True,  # Faster if you don't need timing
        initial_prompt="zavři, otevři, žaluzie, rozsviť, zhasni, světlo, ztlum, zapni, vypni, obýváku, kuchyni, terasu, bránu, hlasitěji, potišeji",
    )

    # segments, _ = whisper.transcribe(audio_file, language="cs")
    full_text = "".join([s.text for s in segments])

    # 3. Process
    msg_text, cmd_tuple = process_smart_home_intent(full_text)
    if cmd_tuple is None:
        print("❌ Nerozumím")
        speak("nerozumim")
    else:
        print(f"Matched: {cmd_tuple} -> {cmd_tuple}")
        speak("provedu")
        status = run_command(cmd_tuple)
        time.sleep(2)
        if status is None:
            speak("error")
        else:
            speak("hotovo")

    recorder.delete()
