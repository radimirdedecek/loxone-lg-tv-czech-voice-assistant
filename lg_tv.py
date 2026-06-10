import json
import os
import time
from pywebostv.connection import WebOSClient
from pywebostv.controls import SystemControl, MediaControl
from wakeonlan import send_magic_packet
from util import get_config


def send_lg_cmd(cmd):  # +,-,off,on,mute on, mute off
    cfg = get_config()
    TOKEN_FILE = "tv_token.json"
    VOLUME_STEP = 10
    VOLUME_PAUSE = 0.5

    if cmd == "on":
        send_magic_packet(cfg["TV_MAC"])
        print(f"send_magic_packet to turn TV ON")
        return ["Processed successfully", "OK"]

    client = WebOSClient(cfg["TV_IP"])
    try:
        client.connect()
    except Exception as e:
        # print(f"❌ Connection failed: {e}. Is the TV on?")
        return ["❌ Connection failed: {e}. Is the TV on?", None]

    # Load existing token or start pairing
    store = {}
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            store = json.load(f)

    # Registration/Pairing
    for status in client.register(store):
        if status == WebOSClient.PROMPTED:
            print(">>> PLEASE CLICK 'YES' ON YOUR TV SCREEN <<<")
        elif status == WebOSClient.REGISTERED:
            # print("✅ Connection Authorized.")
            with open(TOKEN_FILE, "w") as f:
                json.dump(store, f)

    # CONTROL ACTIONS
    system = SystemControl(client)
    media = MediaControl(client)
    time.sleep(0.2)
    # EXECUTION WITH RETRY LOGIC
    attempts = 3
    for i in range(attempts):
        try:
            if cmd == "mute on":
                media.mute(True)
            elif cmd == "mute off":
                media.mute(False)
            elif cmd == "off":
                system.power_off()
            elif cmd == "+":
                for _ in range(VOLUME_STEP):
                    media.volume_up()
                    time.sleep(VOLUME_PAUSE)
            elif cmd == "-":
                for _ in range(VOLUME_STEP):
                    media.volume_down()
                    time.sleep(VOLUME_PAUSE)

            # print(f"📺 TV: Command '{cmd}' processed successfully.")
            return ["Processed successfully", "OK"]

        except Exception as e:
            # print(f"⚠️ Attempt {i+1} failed: {e}. Retrying...")
            time.sleep(0.5)
            continue

    return ["❌ Command failed after 3 attempts", None]


if __name__ == "__main__":
    # Testing
    # send_lg_cmd("off")  # +,-,off,on,mute on, mute off
    send_lg_cmd("mute on")  # +,-,off,on,mute on, mute off
