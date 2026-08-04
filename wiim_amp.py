import requests
from util import get_config, initialize_var

initialize_var()
cfg = get_config()
WIIM_IP = cfg["WIIM_IP"]
url = f"https://{WIIM_IP}/httpapi.asp?" 

def send_wiim_cmd(cmd):
    try:
      preset_number = int(cmd)
      if not (1 <= preset_number <= 12):
        print("❌ Preset number must be between 1 and 12")
        return None
      cmd = f"command=MCUKeyShortClick:{preset_number}"
      info = f"🎵 Playing WiiM Preset #{preset_number}"
    except ValueError:
      cmd = "command=setPlayerCmd:pause"
      info = "🛑 WiiM Amp stopped."

    full_cmd = f"{url}{cmd}"
    try:
        response = requests.get(full_cmd, timeout=3, verify=False)
        if response.status_code == 200:
            print(info)
            return "OK"
    except Exception as e:
        print(f"❌ Failed to reach WiiM Amp: {e}")
    return None
  
  
if __name__ == "__main__":
    # Testing 
    # initialize_var()
    # cfg = get_config()
    send_wiim_cmd("x")
    # send_wiim_cmd(1)
    # send_wiim_cmd(f"command=MCUKeyShortClick:{preset_number}", f"🎵 Playing WiiM Preset #{preset_number}") 
    # send_wiim_cmd("command=MCUKeyShortClick:30", "🌙 WiiM Amp set to standby.") 
    # send_wiim_cmd("command=setPlayerCmd:pause", "🛑 WiiM Amp stopped.") 
