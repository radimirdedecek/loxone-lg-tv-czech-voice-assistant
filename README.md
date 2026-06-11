# Český hlasový asistent pro Loxone Miniserver & LG TV
Autonomní hlasový asistent navržený pro nepřetržitý provoz (24/7) v češtině, který umožňuje plné ovládání Loxone Miniserveru a LG Smart TV bez závislosti na internetovém připojení a bez nutnosti integrace do robustních platforem jako je Home Assistant. Systém poskytuje absolutní svobodu v ovládání libovolných vstupů/výstupů funkčních bloků v Loxone. Uživatel si může pro každou akci definovat libovolné klíčové fráze v přirozené češtině, včetně podpory více různých výrazů pro stejný povel.

# Czech Voice Assistant for Loxone Miniserver & LG TV
A fully offline, privacy-first Python voice assistant engineered for 24/7 local smart home deployment. This system enables direct control over Loxone Miniserver states and LG webOS Smart TVs without cloud dependencies or complex middle-layer integrations like Home Assistant. It provides granular execution mapping across any operational Loxone functional block input/output. Users can provision highly custom voice trigger phrases using natural Czech syntax, supporting multiple lexical variations mapped directly to the same hardware command array.

---

## 🛠️ System Architecture

The assistant leverages a pipeline that maximizes local hardware configurations while preventing execution lockups across real-time device operations:

* **Wake Word Detection (`openWakeWord`):** Monitors audio streams with low CPU consumption using a specialized ONNX runtime engine.
* **Edge Transcription Core (`faster-whisper`):** A pre-warmed Czech language model configured in INT8 execution mode directly inside workstation RAM for instantaneous voice-to-text inference.
* **Asynchronous Command Handlers:** Background threads isolate long-running asynchronous routines (like blind travel checking and network timeouts) from the core listening thread.

---

## 📁 Repository Structure

```text
.
├── app.py               # Application entryway & primary 24/7 wake word tracking loop
├── wisper.py            # Whisper model lifecycle, intent-matching & string-distance logic
├── loxone.py            # Miniserver HTTP/XML communication layer & blind tracking loops
├── lg_tv.py             # LG webOS TV API control interface with Wake-on-LAN recovery
├── util.py              # System audio playback wrapper (`pw-play`) & environment config guards
├── .env.example         # Template configuration containing credential mapping tokens
├── oww_models/          # Cached ONNX runtime localized wake word target binaries
└── messages/            # System response feedback confirmation audio files

```

## 🚀 Installation & Prerequisites
### Hardware Requirements

  - Linux Environment (Tested on Ubuntu/X11 profiles)

  -  Recommended Microphones: Intelligent USB Far-field Microphone Arrays (e.g., Jabra Speak 410/510 series) equipped with hardware Acoustic Echo Cancellation (AEC) and Automatic Gain Control (AGC) to ensure clear pickup while TVs or music play nearby.

### Core Dependencies

Ensure your development environment contains `PipeWire` audio utilities (`pw-play`). Initialize your isolated virtual environment and pull down the engine requirements:

```bash

pip install numpy pvrecorder faster-whisper openwakeword pywebostv wakeonlan requests python-dotenv thefuzz unidecode

```
### Configuration Environment (`.env`)

Generate your `.env` file from the repository tracking template:
```bash

cp .env.example .env

```
Configure your local network topology keys appropriately:
```bash

TV_IP=your_TV_IP_address
TV_MAC=your_TV_MAC_address
LOX_IP=your_miniserver_IP_address
LOX_USER=your_miniserver_username
LOX_PASS=your_miniserver_password

```
## 🤖 Intent Architecture & Commands

The processing pipeline strips accent marks, enforces string-collapsing protocols via unidecode, and calculates token differences using fuzzy character ratio logic to protect accuracy against transcription variations (e.g., matching **"zeluz je"** securely to **"žaluzie"**).

Supported configurations out-of-the-box include (which can be changed/added as desired):
| Intent Category   | Voice Target Sequence (Czech)	| System Hand-off Verb |
| ----------------  | ----------------------------	| -------------------- |
| Loxone Shading    | “zavři žaluzie v kuchyni”     | `/dev/sps/io/z.kuchyn/down` | 
| Loxone Shading    | “otevři žaluzie v obýváku”    | Automated full drop loop followed by `/shade` slat tilts| 
| Loxone Lighting   | “rozsviť noční světlo”        | `/dev/sps/io/sv.obyvak/changeTo/3` | 
| Loxone Lighting   | “rozsviť nad stolem”          | Sub-control addressing via `/AI2/on` channels| 
| Loxone Perimeter  | “otevři bránu”                | Virtual button state triggering via `/pulse` paths| 
| LG Smart TV       | “zapni / vypni televizi”      | Magic Packet broadcast or webOS system controls| 
| LG Smart TV       | “hlasiteji / potišeji         | Dynamic incremental volume stepping frames| 
more actions, see code...

## 📦 Defensive Execution & Error Recovery

This assistant is engineered to withstand real-time infrastructure challenges without dropping out or crashing:

  -  ***Microphone Integrity Guard:*** Core streaming scopes wrap within execution safety barriers. If network pipelines break, audio frame reading variables drop securely via finally routines to ensure inputs do not become unresponsive or deadlocked.

  -  ***Automatic Network Recovery:*** Unhandled standard exceptions during routine light commands or peripheral drops log notifications to the standard shell console but allow the global voice tracking layer to continue scanning for inputs.

  -  ***Audio Echo Padding:*** Implements intentional wait frames (time.sleep) during verbal feedback confirmation playback blocks to prevent the microphone from processing the computer's own voice response as an accidental voice command string.

## 🏃 Execution

Start the daemon securely to keep the listener active:
```bash

python app.py

```