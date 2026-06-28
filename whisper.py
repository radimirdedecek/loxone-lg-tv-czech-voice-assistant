import numpy as np
import time
import asyncio
import threading
import re
import socket
from pvrecorder import PvRecorder
from faster_whisper import WhisperModel
from unidecode import unidecode
from thefuzz import fuzz
from util import speak_and_wait, play, tea_timer, beep_start, beep_end
from lg_tv import send_lg_cmd
from loxone import async_send_lox_cmd, is_voice_control_allowed, get_temperature

# --- CONFIG ---
WHISPER_MODEL_SIZE = "small"  # Options: 'tiny', 'base', 'small' , "medium" (small is great for Czech)
commands = {
    # LOXONE shading
    "zavři žaluzie v kuchyni": ("lox", ("z.kuchyn", "down")),
    "zavři žaluzie v obýváku": ("lox", ("z.obyvak", "down")),
    "zavři žaluzie na terasu": ("lox", ("z.terasa", "down")),
    "dej žaluzie v kuchyni dolů": ("lox", ("z.kuchyn", "down")),
    "dej žaluzie v obýváku dolů": ("lox", ("z.obyvak", "down")),
    "dej žaluzie na terasu dolů": ("lox", ("z.terasa", "down")),
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
    # LOXONE temperature
    "jak je venku": ("lox", ("venku.u.studny.teplota", "temperature")),
    "jak je na půdě": ("lox", ("puda.rozvadec.teplota", "temperature")),
    "jak je v ložnici": ("lox", ("loznice.tepl.", "temperature")),
    # LG TV Commands
    "zapni televizi": ("lg", "on"),
    "vypni televizi": ("lg", "off"),
    "zapni zvuk": ("lg", "mute off"),
    "vypni zvuk": ("lg", "mute on"),
    "hlasitěji": ("lg", "+"),
    "potišeji": ("lg", "-"),
    "přepni na jedničku": ("lg", "1"),
    "přepni na trojku": ("lg", "3"),
    "přepni nahoru": ("lg", "up"),
    "přepni dolů": ("lg", "down"),
    # OTHER Commands
    "prečti příkazy": ("cmd", "prikazy"),
    "prečti seznam": ("cmd", "prikazy"),
    "nastav pět minut": ("cmd", "5minut"),
    "nastav tři minuty": ("cmd", "3minuty"),
    "ale nic": ("cmd", "test"),
    "vypni mikrofon": ("cmd", "mikrofon"),
    "kdo je tady nejkrásnější": ("cmd", "beautiful"),
}

print("Loading Whisper Czech Brain... (Please wait, downloading if first time)")
whisper_model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8", cpu_threads=8)


def generate_initial_prompt(commands_dict):
    """Automatically extracts all unique words from the commands dictionary keys

    to create a biased context prompt for Faster-Whisper.
    """
    unique_words = set()

    # Loop through every voice command phrase (the keys of your dictionary)
    for phrase in commands_dict.keys():
        # Remove anything that isn't a letter or a space, and turn to lowercase
        cleaned_phrase = re.sub(r"[^\w\s]", "", phrase.lower())
        # Split the phrase into individual words
        words = cleaned_phrase.split()
        # Add them to our unique word set
        unique_words.update(words)

    # Join the words with commas into a single string for Whisper
    return ", ".join(sorted(list(unique_words)))


AUTOMATED_PROMPT = generate_initial_prompt(commands)


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
        if actions == "temperature":
            get_temperature(targets)
        else:
            threading.Thread(target=lambda: asyncio.run(async_send_lox_cmd(targets, actions)), daemon=True).start()
        return "OK"
    elif system_type == "cmd":
        print(f"CALLING OTHER Commands: {cmd_data}")
        if cmd_data == "prikazy":
            for txt in commands:
                play(txt)
                time.sleep(3)
        elif cmd_data[1:6] == "minut":
            min = int(cmd_data[0])
            if min > 0:
                threading.Thread(target=lambda: tea_timer(min, cmd_data[1:]), daemon=True).start()
            else:
                speak_and_wait("error", True)
        elif cmd_data == "mikrofon":
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.sendto("stop_alexa".encode('utf-8'), ("192.168.88.202", 5005))
            sock.close()
        elif cmd_data == "beautiful":
            play("nejkrásnější široko daleko je sluníčko")
        elif cmd_data == "test":
            time.sleep(1)
            pass
        else:
            speak_and_wait("error", True)
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
        print(f"MATCH FOUND ({highest_score:3}%): {phrase} -> {command_tuple}")
        return [f"🚀 ACTION: {phrase}", command_tuple]
    return ["❌ Command not Recognised", None]


def record_command(recorder, duration=3):
    """Records audio for a fixed duration after the wake word"""
    print(f"Listening to command for {duration}s...")
    frames = []
    for _ in range(0, int(16000 / 1280 * duration)):
        frames.extend(recorder.read())
    # temp_file = "command.wav"                               write to temp_file replaced
    # with wave.open(temp_file, "wb") as wf:
    #     wf.setnchannels(1)
    #     wf.setsampwidth(2)  # 16-bit
    #     wf.setframerate(16000)
    #     # wf.writeframes(np.array(frames, dtype=np.int16).tobytes())
    #     wf.writeframes(struct.pack("<" + str(len(frames)) + "h", *frames))
    # return temp_file
    audio_array = np.array(frames, dtype=np.int16)
    return audio_array


def whisper():
    if not is_voice_control_allowed():
        # Actively ignore the wake word and loop back to listening
        return
    speak_and_wait("co_chces", True)
    recorder = PvRecorder(frame_length=1280, device_index=-1)
    try:
        beep_start()
        print("Whisper Ready! Now recording...")
        recorder.start()

        # audio_file = record_command(recorder, duration=3)
        audio_data_int16 = record_command(recorder, duration=3)               # new ✅ Passed directly as a RAM object
        recorder.stop()  # Stop recording so CPU can focus on transcribing
        beep_end()
        print("Transcribing...")
        audio_data_float32 = audio_data_int16.astype(np.float32) / 32768.0
        # Transcribe using the global instance
        segments, info = whisper_model.transcribe(
            # audio_file,
            audio_data_float32,   # new ✅ Passed directly as a RAM object!
            language="cs",
            beam_size=1,  # 1 - fast, 5 - Better accuracy for "Zavři"
            best_of=1,  # NEW PARAM: Don't waste CPU evaluating multiple variations
            temperature=0,  # NEW PARAM: Force direct deterministic text generation
            # vad_parameters=dict(min_silence_duration_ms=300),  # NEW PARAM: Cut trailing silence fast
            vad_filter=True,  # Removes silence before processing
            word_timestamps=True,  # Faster if you don't need timing
            initial_prompt=AUTOMATED_PROMPT
            # initial_prompt="zavři, otevři, žaluzie, dolů, nahoru, rozsviť, zhasni, světlo, ztlum, zapni, vypni, naplno, maximum, střední, noční, obýváku, kuchyni, terasu, nad, stolem, lampičku, televizi, zvuk, bránu, hlasitěji, potišeji, prečti, seznam, nastav, tři, pět, minut, ale, nic",
        )
        # beep_end()
        # segments, _ = whisper.transcribe(audio_file, language="cs")
        full_text = "".join([s.text for s in segments])

        # 3. Process
        # print("Processing...")
        msg_text, cmd_tuple = process_smart_home_intent(full_text)
        # beep_end()
        if cmd_tuple is None:
            print("❌ Nerozumím")
            speak_and_wait("nerozumim", False)
        else:
            # print(f"🟢 Matched: {cmd_tuple} -> {cmd_tuple}")
            speak_and_wait("jasne", False)
            status = run_command(cmd_tuple)
            # time.sleep(2) xxx
            if status is None:
                speak_and_wait("error", True)
            else:
                speak_and_wait("hotovo", True)
    except Exception as e:
        print(f"❌ Critical failure during command processing: {e}")
        speak_and_wait("error", True)
    finally:
        # This code ALWAYS runs, even if the transcription crashes completely!
        recorder.delete()


if __name__ == "__main__":
    # --- TEST ---
    # [target_phrase, cmd] = process_smart_home_intent("avri branu")
    # [target_phrase, cmd] = process_smart_home_intent("Zauři šeluzie")
    # run_command(("cmd", "5minut"))

    # for txt in commands:
    #     play(txt)
    #     time.sleep(3)

    cmd_data = "3minuty"
    print(cmd_data[1:6])
    print("\u2714")
    print(3 + int(cmd_data[0]))
