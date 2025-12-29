# SignalAssistant

<b>Home Assistant → SignalRGB Bridge</b>

SignalAssistant emulates WLED lights to allow <b>SignalRGB</b> to control your smart lights via <b>Home Assistant</b>. SignalRGB sees virtual WLED devices, while the script forwards color and state updates to Home Assistant, which controls your Zigbee or other HA-supported lights.

## Features
<ul>
  <li>Supports multiple lights.</li>

  <li>Exposes a WLED-compatible HTTP API (/json/state, /json/info).</li>
  
  <li>Responds to mDNS and SSDP for auto-discovery.</li>
  
  <li>Sends real-time color updates via UDP or HTTP to SignalRGB.</li>
  
  <li>Configurable via environment variables: light names, HA connection, LED counts.</li>
</ul>


## Requirements
<ul>
  <li>Python 3.12+</li>

  <li>Home Assistant instance with lights configured</li>
  
  <li>SignalRGB installed on your PC</li>
  
  <li>Dependencies (install via requirements.txt)</li>
</ul>

## Environment Variables
<table>
  <tr>
    <th>Variable</th>
    <th>Description</th>
    <th>Example</th>
  </tr>
  <tr>
    <td>HA_IP</td>
    <td>IP address of Home Assistant</td>
    <td>192.168.0.200</td>
  </tr>
  <tr>
    <td>HA_TOKEN</td>
    <td>Long-lived access token for Home Assistant</td>
    <td>YOUR_TOKEN_HERE</td>
  </tr>
  <tr>
    <td>ENTITY_NAMES</td>
    <td>Comma-separated list of HA light entity names</td>
    <td>living_room,kitchen,bedroom</td>
  </tr>
  <tr>
    <td>ENTITY_COUNT</td>
    <td>Number of lights to emulate</td>
    <td>3</td>
  </tr>
  <tr>
    <td>WLED_NAME</td>
    <td>Name of the virtual WLED device</td>
    <td>HomeAssistantBridge</td>
  </tr>
</table>
		
## Running Locally
```bash
export HA_IP="192.168.0.200"
export HA_TOKEN="YOUR_TOKEN"
export ENTITY_NAMES="living_room,kitchen"
export ENTITY_COUNT=2
export WLED_NAME="HomeAssistantBridge"

python emulator.py
```
## Running with Docker
### Build the image
```bash
docker build -t signalassistant .
```
### Run container (host network required for mDNS/SSDP/UDP)
```bash
docker run -d \
  --name signalassistant \
  --network host \
  -e HA_IP="192.168.0.200" \
  -e HA_TOKEN="YOUR_TOKEN" \
  -e ENTITY_NAMES="living_room,kitchen" \
  -e ENTITY_COUNT=2 \
  -e WLED_NAME="HomeAssistantBridge" \
  signalassistant
```
> Note: Host networking is required for proper LAN discovery of virtual WLED lights. Works best on Linux.

## How It Works

<ol>
  <li>The script registers a virtual WLED device on the network (mDNS/SSDP).</li>
  <li>SignalRGB discovers it and sends real-time color updates.</li>
  <li>The script receives updates via UDP or HTTP and forwards them to Home Assistant using WebSocket commands.</li>
  <li>Home Assistant then controls your actual lights (Zigbee, Wi-Fi, etc.).</li>
</ol>
