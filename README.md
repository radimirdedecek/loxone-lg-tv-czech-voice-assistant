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

### 1. ⚙️ How to Prepare the Remote Server (WS - workstation) 

To prevent your Jabra hardware puck or audio system from dropping connection during idle periods, run these steps directly on the **WS** terminal:

### Disabling Audio and USB Sleep States
1. Open the WirePlumber audio configuration directory:
    ```bash
    mkdir -p ~/.config/wireplumber/wireplumber.conf.d/
    vi ~/.config/wireplumber/wireplumber.conf.d/50-disable-session-suspend.conf
    ```

2. Paste the following configuration to disable auto-suspend for your microphone/audio hardware:
    ```text
    monitor.alsa.rules = [
        {
        matches = [ { node.name = "~alsa_output.*" }, { node.name = "~alsa_input.*" } ]
        actions = { update-props = { session.suspend-timeout-seconds = 0 } }
      }
    ]
    ```

3. Restart the audio services:
    ```bash
    systemctl --user restart wireplumber
    ```

4. To prevent your USB ports from turning off to save power, disable kernel-level USB autosuspend:
    ```bash
    sudo vi /etc/default/grub
    ```
  Add `usbcore.autosuspend=-1` to your `GRUB_CMDLINE_LINUX_DEFAULT` string, save, and update:
    ```bash
    sudo update-grub
    ```  

### 2. 📦 How to Install Necessary Files and SW on WS

Run these steps via your remote connection to set up the clean, isolated Python Virtual Environment:
1. Install the core OpenSSH server and python tools:
    ```bash
    sudo apt update
    sudo apt install openssh-server python3-venv -y
    ```

2. Navigate to your project folder (`~/98_loxone`) and build the environment:
    ```bash
    cd ~/98_loxone
    python3 -m venv .venv
    ```
3. Activate the environment and install your verified, clean dependencies list:
    ```bash
    source .venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    ```

4. Configuration Environment:  
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
    BEEP_START=/usr/share/sounds/sound-icons/percussion-10.wav
    BEEP_END=/usr/share/sounds/sound-icons/cembalo-11.wav
    ```

### 3. 📂 How to Prepare the Folder on local PC for Data Exchange

To edit code from your daily driver PC without bloating your user-home backup streams, use the global Linux `/mnt/` directory combined with `sshfs`:

1. Open a terminal on your PC and configure FUSE to allow cross-boundary mounts:
    ```bash
    sudo chmod 644 /etc/fuse.conf
    sudo vi /etc/fuse.conf
    ```
    Uncomment or add this line at the bottom: `user_allow_other`

2. Create the target mirror directory and assign explicit user ownership:
    ```bash
    sudo mkdir -p /mnt/shared_ws
    sudo chown -R dr:dr /mnt/shared_ws
    ```

3. Securely mount the folder over the network (No `sudo` required!):
    ```bash
    sshfs dr@192.168.88.202:/home/dr/98_loxone /mnt/shared_ws
    ```
    Now you can open `/mnt/shared_ws` in VS Code on your PC to manage all files live on the server.

### 4. 🚀 How to Login from PC to WS and Run the App

Whenever you want to run the assistant framework manually or look at standard logging cycles:

1. Open your terminal on your PC and SSH directly into the processing hardware pool of WS:
    ```bash
    ssh dr@192.168.88.202
    ```
2. Jump into the project scope, activate the native compiler context, and trigger execution:
    ```bash
    cd ~/98_loxone
    source .venv/bin/activate
    python3 app.py
    ```

### 5. 🛑 Disconnecting the File Bridge
When you are done developing and want to sever the directory mount point cleanly from your local file system, run this on your PC:  

```bash
fusermount -u /mnt/shared_ws
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
