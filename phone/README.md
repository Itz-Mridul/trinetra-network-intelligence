# Trinetra Phone Carrier Tests

Use the same phone, location, hotspot position, and five-minute collection window for both carriers.

## Jio

Select Jio as the Android mobile-data SIM, restart the hotspot if Android asks, check the Pi address, and run:

```bash
PI_IP=<PI_IP> PIPROBE_CARRIER=AUTO SESSION_ID=jio_college_gate_001 bash termux_sender.sh
```

## BSNL

Select BSNL as the Android mobile-data SIM, restart the hotspot if Android asks, check the Pi address again, and run:

```bash
PI_IP=<PI_IP> PIPROBE_CARRIER=AUTO SESSION_ID=bsnl_college_gate_001 bash termux_sender.sh
```

The Pi address can change after switching the mobile-data SIM. Check it on the Pi with:

```bash
hostname -I
```

The sender detects the carrier from the public-IP network owner. It also stores Android's reported operator separately because that field can be stale on dual-SIM phones. The sender collects the registered LTE/WCDMA cell, RSRP, RSRQ, cell ID, band, location, and carrier evidence. It publishes every 15 seconds to `piprobe/phone/telemetry`.

The Raspberry Pi WAN process should be started with the same carrier label and session ID:

```bash
PIPROBE_CARRIER=BSNL bash pi_scripts/start_survey.sh COLLEGE college_gate bsnl_college_gate_001
```

The dashboard compares radio signal, HTTPS success, and measured download throughput. It reports insufficient evidence when a carrier session is incomplete.
