import json
import os
import time
from pywebostv.connection import WebOSClient
from pywebostv.controls import SystemControl, MediaControl, TvControl
from wakeonlan import send_magic_packet
from util import get_config, initialize_var


def send_lg_cmd(cmd):  # +,-,off,on,mute on, mute off,1,2,3,...
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
        print(f"❌ Connection failed: {e}. Is the TV on?")
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
    tv = TvControl(client)
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
            elif cmd == "up":
                tv.channel_up()
            elif cmd == "down":
                tv.channel_down()
            elif cmd.isdigit():
                # print(f"📺 TV Tuner: switch to channel {cmd}...")
                tv.request("ssap://tv/openChannel", {"channelNumber": str(cmd)})
            elif cmd == "+":
                for _ in range(VOLUME_STEP):
                    media.volume_up()
                    time.sleep(VOLUME_PAUSE)
            elif cmd == "-":
                for _ in range(VOLUME_STEP):
                    media.volume_down()
                    time.sleep(VOLUME_PAUSE)

            print(f"📺 TV: Command '{cmd}' processed successfully.")
            return ["Processed successfully", "OK"]
        except Exception as e:
            print(f"⚠️ Attempt {i + 1} failed: {e}. Retrying...")
            time.sleep(0.5)
            continue
    return ["❌ Command failed after 3 attempts", None]


if __name__ == "__main__":
    # Testing +,-,off,on,mute on, mute off,1,2,3,...
    initialize_var()
    # send_lg_cmd("off")
    # send_lg_cmd("mute on")
    # time.sleep(0.5)
    # send_lg_cmd("mute off")
    # time.sleep(0.5)
    print("1.")
    send_lg_cmd("1")
    print("2.")
