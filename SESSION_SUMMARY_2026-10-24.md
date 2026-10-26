# Trinetra project handoff summary

Date: 2026-10-24  
Timezone: Asia/Kolkata

## Project purpose

Trinetra is a portable network-diagnostic system combining:

- Nothing phone cellular telemetry for the active SIM/carrier.
- ESP32 Wi-Fi measurements.
- Raspberry Pi WAN measurements.
- MQTT transport and InfluxDB storage.
- A live dashboard that explains likely faults using only reported data.

The system is intended to be carried to different locations, such as a college campus, to compare Jio and BSNL under the same conditions.

## Completed today

### Raspberry Pi services

- Raspberry Pi SSH access was verified through the Tailscale address.
- Mosquitto is running on port 1883.
- InfluxDB 1.x is running on port 8086.
- The Trinetra dashboard/proxy is running on port 8888.
- Existing tmux sessions are `piprobe-dash`, `piprobe-mqtt`, and `piprobe-wan`.
- The dashboard was confirmed to return HTTP 200.

The Pi Wi-Fi address used by the phone and ESP32 is site-specific and may change after restarting the hotspot. Use `hostname -I` on the Pi before each field run.

### Phone telemetry

Termux and Termux:API are installed on the Nothing phone. Real Jio data was obtained:

- Carrier/network: Jio 4G / LTE.
- Data state: connected.
- Registered LTE cell ID: approximately `36231952`.
- RSRP: approximately `-111 dBm`.
- RSRQ: approximately `-10 dB` to `-13 dB`.
- LTE band: 40.
- Network location: approximately `18.45787, 73.88045`, accuracy about 100 m.
- SINR and SIM slot were not provided by Android/Termux and are correctly shown as unavailable.

GPS did not return a fix, but network location worked with:

```bash
termux-location -p network -r once
```

Do not use `-t`; this Termux version reports `illegal option -t`.

### MQTT and InfluxDB

- Phone-to-Pi MQTT was tested successfully.
- A complete real phone payload was sent to `piprobe/phone/telemetry`.
- The payload was ingested into InfluxDB as probe `phone_1`.
- The stored record included real carrier, LTE network, location, cell ID, RSRP, RSRQ, site, session, and location identifiers.
- Partial payloads without supported numeric telemetry are ignored rather than displayed as fake data.

### Dashboard

The dashboard now:

- Reads live InfluxDB data only.
- Shows a live-error state when the data source is unavailable.
- Shows the phone telemetry card for `phone_1`.
- Displays carrier, network type, location, cell ID, RSRP, RSRQ, and SINR.
- Shows `Unavailable` when a value is not actually reported.
- Shows live/stale age for phone telemetry.
- Does not fabricate Wi-Fi spectrum data for the phone.
- Correctly classifies the current Jio reading as `COVERAGE WEAK`, not WAN degradation.
- Labels the phone node as phone telemetry instead of Wi-Fi.
- Keeps `esp_probe_1`, `phone_1`, and `pi5_gateway` available as discovered probes.
- Supports live refresh, probe selection, time ranges, history, CSV export, fault analysis, and recovery instructions.

Current dashboard observation:

```text
JIO 4G · LTE
RSRP -111 dBm
RSRQ -10 dB
Cell ID 36231952
Location 18.45787, 73.88045 ±100m
COVERAGE WEAK
LIVE · 13s
9 samples in 5m window
```

This is authentic live data. Gateway RTT, Pi RTT, frame loss, SINR, and SIM slot are unavailable for the phone because the phone agent does not report those fields. The ESP32 and Pi probes provide the local Wi-Fi and WAN evidence.

## Files changed

- `pi_scripts/mqtt_to_influx.py`
  - Added phone numeric fields and phone tags.
  - Added phone ingestion logging.
  - Ignores payloads with no supported numeric telemetry.
- `dashboard/index.html`
  - Added phone telemetry display and live/stale status.
  - Added phone-specific parsing, history, classification, and no-fabrication messages.
  - Added live-error and recovery messaging.

Both files were deployed to the Raspberry Pi using legacy SCP mode where required.

## Opening the dashboard

Direct address:

```text
http://<PI_HOST>:8888/
```

Optional local SSH tunnel:

```bash
ssh -o ConnectTimeout=10 -o ExitOnForwardFailure=yes -N \
  -L 8888:127.0.0.1:8888 \
  <PI_USER>@<PI_HOST>
```

Then open:

```text
http://127.0.0.1:8888/
```

If raw HTML source appears, open the normal URL—not `view-source:` and not the HTML file directly. Use `Cmd+Shift+R` for a hard refresh.

## Next work

The Jio phone baseline is working. The next task is cross-layer validation, not another code change:

1. Export the current Jio phone results.
2. Select `pi5_gateway` and verify live Internet RTT, loss, DNS, and HTTP measurements.
3. Export the Jio WAN results.
4. Select `esp_probe_1` and verify Wi-Fi RSSI, gateway RTT, and Pi RTT.
5. Export the ESP32 results.
6. Later, switch the phone’s active mobile-data SIM to BSNL and repeat the same test at the same location.
7. Compare Jio and BSNL using the same site, location, duration, and measurement fields.

## Interpretation for the final demonstration

- Weak phone RSRP plus poor WAN metrics: likely cellular coverage or carrier radio problem.
- Weak phone RSRP plus normal WAN metrics: weak radio signal, but no demonstrated Internet-path failure.
- Good phone signal plus poor WAN metrics: likely carrier congestion or upstream Internet problem.
- Good WAN metrics plus poor ESP32 metrics: likely local Wi-Fi/interference problem.
- Poor gateway/Pi RTT: local network or hotspot path problem.
- Missing fields must remain unavailable; never replace them with guessed values.

## Operating notes

- The phone and Pi must be on the same hotspot network for phone MQTT to reach the broker.
- If MQTT stops working, verify the Pi’s current Wi-Fi IP and update the `mosquitto_pub -h` address.
- Keep the phone telemetry sender running for several minutes so the dashboard shows a fresh stream instead of `STALE`.
- Do not store passwords in project notes, source files, or screenshots.
