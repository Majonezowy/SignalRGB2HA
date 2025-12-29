#!/usr/bin/env python3
import asyncio
import json
import socket
import threading
import time
from typing import Tuple

from flask import Flask, jsonify, request
from zeroconf import Zeroconf, ServiceInfo
import websockets

from dotenv import load_dotenv
import os
import sys

load_dotenv()

# --- Config ---
HOST = "0.0.0.0"
HTTP_PORT = 80
THROTTLE = float(os.getenv("THROTTLE", 0.1))

WLED_NAME = os.getenv("WLED_NAME", "HomeAssistantBridge")
LIGHT_NAMES = os.getenv("ENTITY_NAMES", "wled").split(",")
WLED_LED_COUNT = int(os.getenv("ENTITY_COUNT", 1))

WLED_UDP_PORT_REALTIME = 21324
MAC_ADDRESS = "44:1d:64:f4:00:00"

SSDP_ADDR = "239.255.255.250"
SSDP_PORT = 1900

HA_IP = os.getenv("HA_IP", "")
HA_WS = f"ws://{HA_IP}:8123/api/websocket"
HA_TOKEN = os.getenv("HA_TOKEN", "")

if not LIGHT_NAMES or not HA_IP or not HA_TOKEN:
    print("[ERROR] Missing env variables")
    sys.exit(1)

# --- Flask app ---
app = Flask(__name__)

# --- Utilities ---
def get_local_ip() -> str:
    """Return the local IP address of this machine."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


IP_ADDRESS = get_local_ip()


# --- State ---
class WLEDState:
    def __init__(self):
        self.start_time = time.time()

        self.state = {
            "on": True,
            "bri": 255,
            "live": True,
            "seg": [{"id": 0, "start": 0, "stop": WLED_LED_COUNT, "len": WLED_LED_COUNT}],
        }

        self.info = {
            "ver": "<b>Majon3z</b>",
            "vid": 251013,
            "cn": "Kōsen",
            "release": "ESP32",
            "leds": {
                "count": WLED_LED_COUNT,
                "pwr": 0,
                "fps": 32,
                "maxpwr": 0,
                "maxseg": 32,
                "bootps": 0,
                "seglc": [1],
                "lc": 1,
                "rgbw": False,
                "wv": 0,
                "cct": 0,
            },
            "name": WLED_NAME,
            "udpport": WLED_UDP_PORT_REALTIME,
            "liveseg": -1,
            "wifi": {
                "bssid": "D4:DA:21:75:00:00",
                "rssi": -60,
                "signal": 100,
                "channel": 1,
                "ap": False,
            },
            "arch": "Made by",
            "brand": "WLED",
            "product": "FOSS",
            "mac": MAC_ADDRESS,
            "ip": IP_ADDRESS,
        }


wled_state = WLEDState()


# --- Flask routes ---
@app.route("/json/info/", methods=["GET"])
def json_info():
    wled_state.info["uptime"] = int(time.time() - wled_state.start_time)
    return jsonify(wled_state.info)


@app.route("/json/state/", methods=["POST"])
def update_state():
    data = request.get_json(force=True, silent=True)
    print("[HTTP] /json/state data:", data)
    wled_state.state["live"] = True
    wled_state.info["live"] = True
    wled_state.info["udpport"] = WLED_UDP_PORT_REALTIME
    return jsonify(wled_state.state)


@app.route("/json/", methods=["GET"])
def json_root():
    return jsonify({"state": wled_state.state, "info": wled_state.info})


@app.route("/json/live/", methods=["POST"])
def json_live():
    print(f"[LIVE] {len(request.data)} bytes received")
    return "", 200


@app.route("/", methods=["GET"])
def root():
    return f"<html><body><h1>{WLED_NAME}</h1><p>Fake WLED emulator</p></body></html>"


# --- mDNS ---
def register_mdns_service(name: str = WLED_NAME, port: int = HTTP_PORT) -> Tuple[Zeroconf, ServiceInfo]:
    desc = {
        "id": MAC_ADDRESS.replace(":", ""),
        "mac": MAC_ADDRESS.upper(),
        "ip": IP_ADDRESS,
        "fw": "Majon3z",
        "arch": "Made by",
        "json": "true",
        "name": name,
        "leds": str(WLED_LED_COUNT),
    }
    info = ServiceInfo(
        "_wled._tcp.local.",
        f"{name}._wled._tcp.local.",
        addresses=[socket.inet_aton(IP_ADDRESS)],
        port=port,
        properties=desc,
        server=f"{IP_ADDRESS}.local.",
    )
    zc = Zeroconf()
    zc.register_service(info)
    print(f"[mDNS] Registered {name} on port {port}")
    return zc, info


# --- SSDP ---
def ssdp_listener():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("", SSDP_PORT))
    except Exception as e:
        print(f"[SSDP] Could not bind: {e}")
        return

    mreq = socket.inet_aton(SSDP_ADDR) + socket.inet_aton("0.0.0.0")
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    print("[SSDP] Listening for M-SEARCH")

    usn = f"uuid:WLED-{MAC_ADDRESS.replace(':', '')}"
    location = f"http://{IP_ADDRESS}:{HTTP_PORT}/json"

    while True:
        try:
            data, addr = sock.recvfrom(2048)
            text = data.decode(errors="ignore")
            if "M-SEARCH" in text and "ssdp:discover" in text:
                print(f"[SSDP] M-SEARCH from {addr}, responding...")
                resp = "\r\n".join([
                    "HTTP/1.1 200 OK",
                    "CACHE-CONTROL: max-age=1800",
                    "EXT:",
                    f"LOCATION: {location}",
                    "SERVER: WLED/0.15.0 UPnP/1.1",
                    "ST: urn:schemas-upnp-org:device:basic:1",
                    f"USN: {usn}",
                    "",
                    ""
                ])
                sock.sendto(resp.encode("utf-8"), addr)
        except Exception as e:
            print("[SSDP] Error:", e)


# --- Home Assistant websocket ---
async def send_to_ha(rgb_color: list[int], light_name: str):
    async with websockets.connect(HA_WS) as ws:
        await ws.send(json.dumps({"type": "auth", "access_token": HA_TOKEN}))
        await ws.recv()  # auth response

        await ws.send(json.dumps({"id": 2, "type": "get_states"}))
        states_resp = await ws.recv()
        states_msg = json.loads(states_resp)

        # Find the light state
        light_state = next(
            (e for e in states_msg.get("result", []) if e.get("entity_id") == f"light.{light_name}"),
            None
        )

        if light_state:
            current_rgb = light_state.get("attributes", {}).get("rgb_color")
            if current_rgb == rgb_color:
                print(f"[HA WS] Color already {rgb_color}, skipping")
                return

        command = {
            "id": 3,
            "type": "call_service",
            "domain": "light",
            "service": "turn_on",
            "target": {"entity_id": f"light.{light_name}"},
            "service_data": {"rgb_color": rgb_color, "transition": 0}
        }
        await ws.send(json.dumps(command))
        await ws.recv()

async def send_all_colors(colors, light_names):
    for color, light_name in zip(colors, light_names):
        await send_to_ha(list(color), light_name)


# --- UDP listener ---
def udp_realtime_listener(port=WLED_UDP_PORT_REALTIME):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", port))
    print(f"[UDP] Listening on port {port}")

    last_sent = 0
    last_color = (0, 0, 0)

    while True:
        data, _ = sock.recvfrom(65536)
        if not data or data[0] != 4:
            continue

        pixels = data[4:]
        colors = [tuple(pixels[i:i+3]) for i in range(0, len(pixels), 3)]
        if colors[0] == last_color:
            continue

        now = time.time()
        if now - last_sent > THROTTLE:
            asyncio.run(send_all_colors(colors, LIGHT_NAMES))

            print(f"[UDP] {len(colors)} LEDs: {colors[:5]}{'...' if len(colors) > 5 else ''}")
            last_sent, last_color = now, colors[0]


# --- Entrypoint ---
def main():
    # Start UDP listener
    threading.Thread(target=udp_realtime_listener, daemon=True).start()

    # Start Flask server
    threading.Thread(target=lambda: app.run(host=HOST, port=HTTP_PORT, debug=False, threaded=True), daemon=True).start()
    time.sleep(1.5)

    # Start SSDP listener
    threading.Thread(target=ssdp_listener, daemon=True).start()

    # Register mDNS
    try:
        zc, info = register_mdns_service()
    except Exception as e:
        print(f"[mDNS] Could not register: {e}")
        zc, info = None, None

    # Keep alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[Exit] Cleaning up...")
    finally:
        if zc and info:
            zc.unregister_service(info)
            zc.close()


if __name__ == "__main__":
    main()
