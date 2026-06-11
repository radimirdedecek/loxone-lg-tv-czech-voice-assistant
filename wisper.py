import numpy as np
from pvrecorder import PvRecorder
from faster_whisper import WhisperModel
import wave
from unidecode import unidecode
from thefuzz import fuzz
import time
import asyncio
import threading
from util import speak, play
from lg_tv import send_lg_cmd
from loxone import async_send_lox_cmd

# --- CONFIG ---
WHISPER_MODEL_SIZE = "small"  # Options: 'tiny', 'base', 'small' , "medium" (small is great for Czech)
commands = {
    # LOXONE shading
    "zavři žaluzie v kuchyni": ("lox", ("z.kuchyn", "down")),
    "zavři žaluzie v obýváku": ("lox", ("z.obyvak", "down")),
    "zavři žaluzie na terasu": ("lox", ("z.terasa", "down")),
    "dej žaluzie v kuchyni dolu": ("lox", ("z.kuchyn", "down")),
    "dej žaluzie v obýváku dolu": ("lox", ("z.obyvak", "down")),
    "dej žaluzie na terasu dolu": ("lox", ("z.terasa", "down")),
    "dej žaluzie v kuchyni nahoru": ("lox", ("z.kuchyn", "up")),
    "dej žaluzie v obýváku nahoru": ("lox", ("z.obyvak", "up")),
    "dej žaluzie na terasu nahoru": ("lox", ("z.terasa", "up")),
    "zavři žaluzie": ("lox", ("z.kuchyn z.obyvak z.terasa", "down")),
    "otevři žaluzie v kuchyni": ("lox", ("z.kuchyn", "down shade")),
    "otevři žaluzie v obýváku": ("lox", ("z.obyvak", "down shade")),
    "otevři žaluzie na terasu": ("lox", ("z.terasa", "down shade")),
    "otevři žaluzie": ("lox", ("z.kuchyn z.obyvak z.terasa", "down shade")),
    # LOXONE lights
    "rozsviť světlo": ("lox", ("sv.obyvak", "2")),
    "rozsviť střední světlo": ("lox", ("sv.obyvak", "2")),
    "rozsviť světlo naplno": ("lox", ("sv.obyvak", "on")),
    "rozsviť světlo na maximum": ("lox", ("sv.obyvak", "on")),
    "zhasni světlo": ("lox", ("sv.obyvak", "off")),
    "rozsviť noční světlo": ("lox", ("sv.obyvak", "3")),
    "ztlum světlo": ("lox", ("sv.obyvak", "3")),
    "rozsviť nad stolem": ("lox", ("sv.obyvak", "AI2/on")),
    "zhasni nad stolem": ("lox", ("sv.obyvak", "AI2/off")),
    "rozsviť v kuchyni": ("lox", ("sv.obyvak", "AI5/on")),
    "zhasni v kuchyni": ("lox", ("sv.obyvak", "AI1/off AI5/off AI7/off AI8/off")),
    "rozsviť v obýváku": ("lox", ("sv.obyvak", "AI3/on")),
    "zhasni v obýváku": ("lox", ("sv.obyvak", "AI3/off")),
    "zhasni lampičku": ("lox", ("zasuvka.obyvak", "off on")),
    # LOXONE gate
    "zavři bránu": ("lox", ("brana", "pulse")),
    "otevři bránu": ("lox", ("brana", "pulse")),
    # LG TV Commands
    "zapni televizi": ("lg", "on"),
    "vypni televizi": ("lg", "off"),
    "zapni zvuk": ("lg", "mute off"),
    "vypni zvuk": ("lg", "mute on"),
    "hlasitěji": ("lg", "+"),
    "potišeji": ("lg", "-"),
    # OTHER Commands
    "prečti příkazy": ("cmd", "prikazy"),
    "prečti seznam": ("cmd", "prikazy"),
}

print("Loading Whisper Czech Brain... (Please wait, downloading if first time)")
whisper = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8", cpu_threads=8)


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
    elif system_type == "cmd":
        print(f"CALLING OTHER Commands: {cmd_data}")
        for txt in commands:
            play(txt)
            time.sleep(3)
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
        # This solves the "zeluz je" vs "žaluzie" problem
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


def record_command(recorder, duration=3):
    """Records audio for a fixed duration after the wake word"""
    print(f"Listening to command for {duration}s...")
    frames = []
    for _ in range(0, int(16000 / 1280 * duration)):
        frames.extend(recorder.read())
    temp_file = "command.wav"
    with wave.open(temp_file, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(16000)
        wf.writeframes(np.array(frames, dtype=np.int16).tobytes())
        # wf.writeframes(audio_data.tobytes())
    return temp_file


def wisper():
    speak("co_chces")
    time.sleep(1.2)
    recorder = PvRecorder(frame_length=1280, device_index=-1)
    try:
        print("Whisper Ready! Now recording...")
        recorder.start()

        # 1. Record
        audio_file = record_command(recorder, duration=3)
        recorder.stop()  # Stop recording so CPU can focus on transcribing

        print("Transcribing...")
        # 2. Transcribe using the global instance
        segments, info = whisper.transcribe(
            audio_file,
            language="cs",
            beam_size=4,  # 1 - fast, 5 - Better accuracy for "Zavři"
            # best_of=1,  # NEW PARAM: Don't waste CPU evaluating multiple variations
            # temperature=0,  # NEW PARAM: Force direct deterministic text generation
            # vad_parameters=dict(min_silence_duration_ms=300),  # NEW PARAM: Cut trailing silence fast
            vad_filter=True,  # Removes silence before processing
            # word_timestamps=True,  # Faster if you don't need timing
            initial_prompt="zavři, otevři, žaluzie, rozsviť, zhasni, světlo, ztlum, zapni, vypni, obýváku, kuchyni, terasu, bránu, hlasitěji, potišeji",
        )

        # segments, _ = whisper.transcribe(audio_file, language="cs")
        full_text = "".join([s.text for s in segments])

        # 3. Process
        print("Processing...")
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
    except Exception as e:
        print(f"❌ Critical failure during command processing: {e}")
        speak("error")
    finally:
        # This code ALWAYS runs, even if the transcription crashes completely!
        recorder.delete()


if __name__ == "__main__":
    # --- TEST ---
    # [target_phrase, cmd] = process_smart_home_intent("avri branu")
    # [target_phrase, cmd] = process_smart_home_intent("Zauři šeluzie")

    for txt in commands:
        play(txt)
        time.sleep(3)
