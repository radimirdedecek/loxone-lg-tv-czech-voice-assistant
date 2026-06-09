import requests
from requests.auth import HTTPBasicAuth
import asyncio
import xml.etree.ElementTree as ET

# --- CONFIG ---
LOX_IP = "192.168.88.6"
LOX_USER = "budulin33"
LOX_PASS = "aafd134*zvc@57"


def get_blind_position(target):
    """Parses StatePos from the /all XML response"""
    url = f"http://{LOX_IP}/dev/sps/io/{target}/all"
    try:
        response = requests.get(url, auth=HTTPBasicAuth(LOX_USER, LOX_PASS), timeout=2)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            # Find StatePos in the XML attributes
            pos = root.attrib.get("StatePos")
            if pos is not None:
                return float(pos)
    except Exception as e:
        print(f"⚠️ Error reading {target}: {e}")
    return None


async def async_send_lox_cmd(targets, actions):
    print(f"🏠 Loxone: Sending {actions} to {targets}...")
    target_list = targets.split()
    action_list = actions.split()
    # print(targets + actions)
    if "down" in action_list and "shade" in action_list:
        # 1. Start the movement
        for target in target_list:
            try:
                response = requests.get(
                    f"http://{LOX_IP}/dev/sps/io/{target}/down", auth=HTTPBasicAuth(LOX_USER, LOX_PASS), timeout=2
                )
                if response.status_code == 200:
                    print(f"⬇️ {target} is moving down...")
                else:
                    print(f"⚠️ Error {response.status_code}: {response.text}")
                    return "KO"
            except Exception as e:
                print(f"❌ Connection failed: {e}")
                return "KO"
        # 2. Wait for each blind to land
        for target in target_list:
            print(f"⏳ Monitoring {target} until StatePos is 1.000...")

            # Safety timeout of 40 seconds so we don't loop forever
            for _ in range(40):
                pos = get_blind_position(target)
                if pos is not None:
                    print(f"📊 {target} Position: {pos:.3f}")
                    if pos >= 1.0:  # 1.000 is the bottom
                        break
                await asyncio.sleep(1.5)

            # 3. Tilt the slats
            requests.get(
                f"http://{LOX_IP}/dev/sps/io/{target}/shade", auth=HTTPBasicAuth(LOX_USER, LOX_PASS), timeout=2
            )
            print(f"🌗 {target} is now shaded (tilted).")

    else:
        # Standard logic for up/on/off
        for target in target_list:
            for action in action_list:
                requests.get(
                    f"http://{LOX_IP}/dev/sps/io/{target}/{action}", auth=HTTPBasicAuth(LOX_USER, LOX_PASS), timeout=2
                )
                await asyncio.sleep(0.2)
    print(f"✅ async_send_lox_cmd OK!")
    return "OK"


if __name__ == "__main__":
    # Test SHADING
    # send_lox_cmd("z.kuchyn", "down")
    # send_lox_cmd("z.kuchyn", "up")
    # send_lox_cmd("z.kuchyn", "shade")
    # send_lox_cmd("z.kuchyn z.obyvak z.terasa", "down shade")
    # asyncio.run(async_send_lox_cmd("z.obyvak", "down shade"))
    # asyncio.run(async_send_lox_cmd("z.kuchyn z.obyvak z.terasa", "down shade"))
    # asyncio.run(async_send_lox_cmd("z.kuchyn z.obyvak z.terasa", "up"))
    # print(get_blind_position("z.obyvak"))

    # Test LIGHTS
    # asyncio.run(async_send_lox_cmd("sv.obyvak", "changeTo/3"))
    # asyncio.run(async_send_lox_cmd("sv.obyvak", "AI1/off AI5/off AI7/off AI8/off"))

    # Test GATE
    asyncio.run(async_send_lox_cmd("brana", "pulse"))
