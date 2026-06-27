# Český hlasový asistent pro Loxone Miniserver & LG TV
Autonomní hlasový asistent navržený pro nepřetržitý provoz (24/7) v češtině, který umožňuje plné ovládání Loxone Miniserveru a LG Smart TV bez závislosti na internetovém připojení a bez nutnosti integrace do robustních platforem jako je Home Assistant. Systém poskytuje absolutní svobodu v ovládání libovolných vstupů/výstupů funkčních bloků v Loxone. Uživatel si může pro každou akci definovat libovolné klíčové fráze v přirozené češtině, včetně podpory více různých výrazů pro stejný povel.

# Czech Voice Assistant for Loxone Miniserver & LG TV
A fully offline, privacy-first Python voice assistant engineered for 24/7 local smart home deployment. This system enables direct control over Loxone Miniserver states and LG webOS Smart TVs without cloud dependencies or complex middle-layer integrations like Home Assistant. It provides granular execution mapping across any operational Loxone functional block input/output. Users can provision highly custom voice trigger phrases using natural Czech syntax, supporting multiple lexical variations mapped directly to the same hardware command array.

## 🚀 Key Features:
* **Any Loxone Function:** Universal Loxone Mapping across any functional block input/output.
* **Any Voice Command for Function:** Map customized natural language voice commands to any hardware target.
* **More Voice Commands for same Function:** Bind multiple voice phrases to trigger the exact same action.
* **Fully Offline:** Operates completely local and offline for core command handling.
* **Remote Start/Sleep from Loxone Mniserver:** Wake the workstation up (Wake-on-LAN) or trigger a system sleep to conserve energy when the house is armed or empty.
* **Remote Microphone Enable/Disable from Loxone APP:** Toggle microphone recording states (Mute/Unmute) on the fly directly inside the Loxone App.
* **Diskless Audio Engine:** Audio responses are processed directly within RAM buffers, eliminating local storage write.
* **Smart Hybrid TTS Backend:** Uses high-quality Google TTS by default. If the home internet connection drops, the engine automatically falls back to a 100% local, offline Czech voice.
---

## 🛠️ System Architecture

The assistant leverages a pipeline that maximizes local hardware configurations while preventing execution lockups across real-time device operations:

* **Wake Word Detection (`openWakeWord`):** Monitors audio streams with low CPU consumption using a specialized ONNX runtime engine.
* **Edge Transcription Core (`faster-whisper`):** A pre-warmed Czech language model configured in INT8 execution mode directly inside workstation RAM for instantaneous voice-to-text inference.
* **Asynchronous Command Handlers:** Background threads isolate long-running asynchronous routines (like blind travel checking and network timeouts) from the core listening thread.
* **Loxone Block Names:** must be a single continuous string—using dots (.), underscores (_), or camelCase `!!!`

---

## 📁 Repository Structure

  ```text
  .
  ├── .env.example          # Template configuration containing credential mapping tokens
  ├── app.py                # Application entryway & primary 24/7 wake word tracking loop
  ├── lg_tv.py              # LG webOS TV API control interface with Wake-on-LAN recovery
  ├── LICENSE               # Github license
  ├── loxone.py             # Miniserver HTTP/XML communication layer & blind tracking loops
  ├── messages/             # System response feedback confirmation audio files
  ├── oww_models/           # Cached ONNX runtime localized wake word target binaries
  ├── README.md             # Github readme
  ├── requirements.txt      # Python requirements
  ├── tv_token.json_example # Template configuration containing credential mapping tokens
  ├── util.py               # System audio playback wrapper (`pw-play`) & environment config guards
  └── whisper.py            # Whisper model lifecycle, intent-matching & string-distance logic
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
5. To prevent default Ubuntu Server power-saving:
    ```bash
    # Unmask System Sleep States:
    sudo systemctl unmask sleep.target suspend.target hybrid-sleep.target
    sudo vi /etc/systemd/logind.conf
    # uncomment this lines:
    IdleAction=ignore
    HandleLidSwitch=ignore
    HandleLidSwitchExternalPower=ignore
    # Save and exit
    # Apply the changes instantly:
    sudo systemctl restart systemd-logind
    ``` 
### Create the Automation Service on WS
1. Create a custom systemd configuration:
    ```bash
    mkdir -p ~/.config/systemd/user/
    vi ~/.config/systemd/user/alexa.service
    # add this content:
    [Unit]
    Description=Loxone Voice Assistant Background Service
    After=pipewire.service wireplumber.service
    [Service]
    Type=simple
    WorkingDirectory=/home/<username>/98_loxone
    # This executes python natively straight from your virtual environment!
    ExecStart=/home/<username>/98_loxone/.venv/bin/python3 app.py
    Restart=always
    RestartSec=5
    # Ensures prints show up in logs immediately instead of waiting in buffers
    Environment=PYTHONUNBUFFERED=1
    [Install]
    WantedBy=default.target
    # Save and exit
    ``` 
2. Enable Autostart on Boot:
    ```bash
    # Reload the systemd daemon to see your new service
    systemctl --user daemon-reload

    # Enable it so it boots automatically every time the WS turns on
    systemctl --user enable alexa.service

    # Start the service right now in the background!
    systemctl --user start alexa.service 
    ``` 

3. How to Manage the App Natively:
    ```bash
    # Check if it is currently running:
    systemctl --user status alexa.service

    # Stop the auto-run to do manual testing/debugging:
    systemctl --user stop alexa.service

    # Start it back up when you are done testing:
    systemctl --user start alexa.service

    # Restart the code after you make an edit in VS Code:
    systemctl --user restart alexa.service

    # Tracking the Logs Natively:
    journalctl --user -u alexa.service -f -o cat

    # usefull aliases:
    alias alexalog="journalctl --user -u alexa.service -f -o cat"
    alias alexastart="systemctl --user start alexa.service"
    alias alexastop="systemctl --user stop alexa.service"
    alias alexarestart="systemctl --user restart alexa.service"
    alias serverstart='wakeonlan 98:90:96:a1:9e:6b'
    alias serverstop='ssh <ws_username>@<ws_ip_address> "echo mem | sudo tee /sys/power/state"'
    alias alexash='ssh <ws_username>@<ws_ip_address>'
    alias mount98loxone='sshfs -o reconnect,ServerAliveInterval=15 <ws_username>@<ws_ip_address>:/home/<username>/98_loxone /mnt/shared_ws'
    alias umount98loxone='fusermount -u /mnt/shared_ws'

    # flash changes:
    source ~/.bashrc
    ``` 
4. Switch WS to Server Mode (Headless / No Desktop)
    ```bash
    # To completely disable the desktop interface (Saves massive RAM & CPU):
    sudo systemctl set-default multi-user.target

    # How to turn the desktop back ON (If you ever need it in the future):
    sudo systemctl set-default graphical.target

    # Grant Your User Group Access to Audio Hardware. Since there is no desktop session managing permissions anymore,
    # your user account (<username>) needs direct, explicit access to the system sound boards.
    sudo usermod -aG audio,video <username>

    # Enable "User Lingering" (The Headless Server Fix):
    sudo loginctl enable-linger <username>

    # Now, restart the workstation
    sudo reboot
    ``` 
5. Automate Remote Hibernation and WOL
    ```bash
    # Configure Passwordless Suspend on WS
    sudo visudo
    # Scroll all the way to the very bottom of the file and add this exact line:
    <ws_username> ALL=(ALL) NOPASSWD: /usr/bin/tee /sys/power/state
    # Enable Wake-on-LAN on your Network Card:
    sudo apt update && sudo apt install ethtool -y
    # Find the WS_MAC_ADDRESS of your network card interface:
    ip link
    # Tell the card to listen for the Magic Packet:
    # (Note: You will also want to ensure that "Wake on LAN" is enabled inside your physical Dell Precision BIOS settings).
    sudo ethtool -s <WS_MAC_ADDRESS> wol g
    # SLEEP Command sent by Loxone Virtual Output:
    echo -n "sleep_ws" > /dev/udp/192.168.88.202/5005
    # SLEEP Command sent from linux:
    ssh <ws_username>@<ws_ip_address> 'ssh <ws_username>@<ws_ip_address> "echo mem | sudo tee /sys/power/state"'
    # SLEEP Command sent from linux by UDP:
    echo -n "sleep_ws" > /dev/udp/192.168.88.202/5005  
    # WOL Command sent by Loxone Virtual Output:
    wol://WS_MAC_ADDRESS
    # WOL Command sent from linux:
    wakeonlan WS_MAC_ADDRESS
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
    sudo chown -R <username>:<username> /mnt/shared_ws
    ```

3. Securely mount the folder over the network (No `sudo` required!):
    ```bash
    sshfs -o reconnect,ServerAliveInterval=15 <ws_username>@<ws_ip_address>:/home/<ws_username>/98_loxone /mnt/shared_ws
    ```
    Now you can open `/mnt/shared_ws` in VS Code on your PC to manage all files live on the server.

4. When you want unmount point cleanly from your local file system, run this on your PC:  
    ```bash
    fusermount -u /mnt/shared_ws
    ```

5. When sshfs freezes. This typically happens if your WS went to sleep.
Kill the Hanging Process, run this on your PC:  
    ```bash
    sudo killall -9 sshfs
    sudo umount -l /mnt/shared_ws
    ```


### 4. 🚀 How to Login from PC to WS and Run the App

Whenever you want to run the assistant framework manually or look at standard logging cycles:

1. Open your terminal on your PC and SSH directly into the processing hardware pool of WS:
    ```bash
    ssh <ws_username>@<ws_ip_address>
    ```
2. Jump into the project scope, activate the native compiler context, and trigger execution:
    ```bash
    cd ~/98_loxone
    source .venv/bin/activate
    python3 app.py
    ```


## 🤖 Intent Architecture & Commands
**Loxone Block Names:** must be a single continuous string—using dots (.), underscores (_), or camelCase `!!!`

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
