# Trinetra Operator Guide

This guide explains what the live dashboard means in simple language.

## How to read the main result

The top status is the first thing to read:

- **LIVE · NOMINAL** — the Pi, ESP32, local Wi-Fi, and current WAN evidence look healthy.
- **COVERAGE WEAK · REVIEW** — the sensor is receiving weak Wi-Fi signal and the local response is also slow. Move the sensor closer to the router or improve antenna placement.
- **INTERFERENCE · REVIEW** — the signal is strong, but several networks share the same channel and the local link is losing packets or becoming unstable. Change the router channel or reduce nearby radio interference.
- **LAN CONGESTED · REVIEW** — the router/local network is slow for more than one path. Check heavy downloads, too many active clients, or router overload.
- **WAN DEGRADED · REVIEW** — Wi-Fi and the router may be healthy, but the outside Internet is slow. Repeat the test; if the high latency continues, check the ISP, hotspot, or mobile-data network.
- **WAN DOWN · REVIEW** — the local router responds but the outside Internet does not. Check the ISP/mobile-data connection and the router’s uplink.
- **PROBE FAULT · REVIEW** — the sensor stopped reporting or is repeatedly reconnecting. Check ESP32 power, Wi-Fi credentials, and MQTT connection.
- **INCONCLUSIVE · REVIEW** — the measurements disagree or there is not enough evidence. Keep the test running before blaming a device or provider.
- **LIVE ERROR · NO DATA** — the website cannot read current data. Check Pi Wi-Fi, MQTT, InfluxDB, and the dashboard service.

## What the numbers mean

- **Wi-Fi signal / RSSI:** closer to zero is stronger. Around −30 dBm is excellent; below −75 dBm needs attention.
- **Gateway RTT:** time to reach the local router. High or unstable values usually indicate a local Wi-Fi or router problem.
- **Pi loopback:** time for the ESP32 to reach the Raspberry Pi. This confirms whether the local path is healthy.
- **Frame loss:** missing test packets. Sustained loss is more important than one isolated lost packet.
- **Internet RTT:** time to reach an outside destination. High Internet RTT with healthy local values points outside the room.
- **DNS and HTTP:** extra evidence about name lookup and web response. They are supporting evidence, not a diagnosis by themselves.

## Recommended response sequence

1. Read the status and the sentence under **System confidence**.
2. Check whether the last several samples agree. Do not decide from one spike.
3. Compare the layers: Wi-Fi signal, gateway RTT, Pi loopback, and WAN.
4. If only Wi-Fi is bad, move or reorient the ESP32 and check the router channel.
5. If local values are good but Internet values are bad, test another device and check the ISP/hotspot.
6. If the status says no data, restore the Pi/ESP32 connection before interpreting old measurements.
7. Export the selected history window before changing the network so the evidence is preserved.

## Moving an ESP32 to a new hotspot

The firmware includes a manual setup mode so the code does not need to be uploaded for every visit. After the updated firmware has been uploaded once, hold the ESP32 **BOOT** button for about 2.5 seconds while the board is running. It creates the `Trinetra-Setup-XXXX` Wi-Fi network. Connect the phone to that network, open `http://192.168.4.1/`, enter the new Pi IP as the MQTT broker, update the session/location fields, and save. The ESP32 stores the settings in its flash memory and restarts.

This one-time firmware update is required only to add the manual setup trigger. Future location changes use the setup page and do not require another upload.

## Current live check

During the latest check, the ESP32 repeatedly reported strong RSSI, 0% local loss, and a stable Pi path. The WAN probe reported 0% loss but occasional latency spikes. Therefore the correct conclusion is: **the local Wi-Fi path is healthy; continue monitoring the outside Internet path before calling it an ISP fault.**

The dashboard is designed to explain the result, but terms such as RTT, RSSI, and WAN remain visible for technical verification. The plain-language sentence and this guide are the non-technical interpretation.
