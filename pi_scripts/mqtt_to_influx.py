#!/usr/bin/env python3
"""
Trinetra - MQTT to InfluxDB bridge.
Subscribes to all telemetry topics under ``piprobe/<node>/<layer>`` and writes
to either InfluxDB 1.x or 2.x, selected from the server's /ping response.
"""
import os, json, time, sys, logging, requests
import paho.mqtt.client as mqtt

MQTT_BROKER    = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT      = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC     = os.getenv("MQTT_TOPIC", "piprobe/+/+")

INFLUX_HOST    = os.getenv("INFLUX_HOST", "localhost")
INFLUX_PORT    = int(os.getenv("INFLUX_PORT", 8086))
INFLUX_ORG     = os.getenv("INFLUX_ORG", "piprobe_org")
INFLUX_BUCKET  = os.getenv("INFLUX_BUCKET", "telemetry")
INFLUX_TOKEN   = os.getenv("INFLUX_TOKEN", "")
INFLUX_DB_V1   = os.getenv("INFLUX_DB", "piprobe")
MEASUREMENT    = "network_telemetry"

FLOAT_FIELDS = {
    "timestamp",
    "rssi_raw_dbm","rssi_calibrated_dbm",
    "gw_rtt_mean_ms","gw_rtt_jitter_ms","gw_loss_pct",
    "pi_rtt_mean_ms","pi_rtt_jitter_ms","pi_loss_pct",
    "ap_count_total","ap_count_on_channel",
    "uptime_sec","free_heap_bytes","reconnect_count","tput_kbps",
    "gw_rtt_std_ms","inet_rtt_mean_ms","inet_rtt_std_ms","inet_loss_pct",
    "dns_latency_ms","http_ttfb_ms","wan_tput_dl_mbps","wan_tput_ul_mbps",
    "wan_http_success_pct","wan_http_success_count","wan_http_target_count",
    "wan_tput_dl_bytes",
    "cpu_temp_c","mem_used_pct","pi_cpu_temp_c","pi_mem_used_pct",
    "latitude","longitude","accuracy_m","altitude","vertical_accuracy",
    "bearing","speed","rsrp_dbm","rsrq_db","sinr_db",
    "cell_id","mcc","mnc","tac","pci","band",
    "telemetry_received",
    "public_latitude","public_longitude"
}
TAG_KEYS = {
    "probe_id","site_id","session_id","layer","room_id","location_id",
    "bssid","channel","fault_class","run_id","split",
    "carrier_name","network_type","data_state","provider","sim_slot",
    "cell_type","selected_carrier","reported_operator_name","requested_carrier",
    "local_ip","gateway_ip","interface_name","router_mac","wifi_ssid",
    "public_ip","isp_org","isp_asn","public_city","public_region",
    "public_country","public_timezone"
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)
write_count = 0
error_count = 0
influx_version = 2
influx_write_url = ""
influx_headers = {}

def init_influx_target():
    global influx_version, influx_write_url, influx_headers
    base_url = f"http://{INFLUX_HOST}:{INFLUX_PORT}"
    try:
        r = requests.get(f"{base_url}/ping", timeout=3)
        v = r.headers.get("X-Influxdb-Version", "")
        if v.startswith("1."):
            influx_version = 1
            influx_write_url = f"{base_url}/write?db={INFLUX_DB_V1}&precision=s"
            influx_headers = {}
            requests.post(f"{base_url}/query", params={"q": f"CREATE DATABASE {INFLUX_DB_V1}"}, timeout=3)
            log.info(f"[InfluxDB] Detected InfluxDB v1 ({v}). Target DB: '{INFLUX_DB_V1}'")
        else:
            influx_version = 2
            influx_write_url = f"{base_url}/api/v2/write?org={INFLUX_ORG}&bucket={INFLUX_BUCKET}&precision=s"
            influx_headers = {"Authorization": f"Token {INFLUX_TOKEN}"}
            log.info(f"[InfluxDB] Detected InfluxDB v2 ({v or '2.x'}). Org: '{INFLUX_ORG}', Bucket: '{INFLUX_BUCKET}'")
    except Exception as e:
        log.warning(f"[InfluxDB] Ping check failed ({e}). Defaulting to InfluxDB v2 with fallback.")
        influx_version = 2
        influx_write_url = f"{base_url}/api/v2/write?org={INFLUX_ORG}&bucket={INFLUX_BUCKET}&precision=s"
        influx_headers = {"Authorization": f"Token {INFLUX_TOKEN}"}

def ensure_db():
    init_influx_target()

def json_to_lp(topic, data):
    tags = {
        k: str(data[k]).replace(" ", r"\ ").replace(",", r"\,").replace("=", r"\=")
        for k in TAG_KEYS if k in data and data[k] is not None
    }
    fields = {
        k: float(data[k]) for k in FLOAT_FIELDS
        if k in data and isinstance(data[k], (int, float)) and not isinstance(data[k], bool)
    }
    if not fields: return ""
    # ESP32 may publish timestamp=0 briefly while NTP is still synchronizing.
    # Never write that sentinel as an Influx epoch timestamp: use the Pi's
    # receive time so the sample remains visible in the live dashboard.
    raw_timestamp = data.get("timestamp")
    try:
        ts = int(raw_timestamp)
    except (TypeError, ValueError):
        ts = 0
    if ts < 1000000000:
        ts = int(time.time())
    tag_str   = ",".join(f"{k}={v}" for k,v in sorted(tags.items()))
    field_str = ",".join(f"{k}={v}" for k,v in sorted(fields.items()))
    return f"{MEASUREMENT},{tag_str} {field_str} {ts}" if tag_str else f"{MEASUREMENT} {field_str} {ts}"

def write(line):
    global write_count, error_count
    try:
        r = requests.post(influx_write_url, data=line.encode(), headers=influx_headers, timeout=5)
        if r.status_code in (200, 204):
            write_count += 1
            if write_count % 5 == 0: log.info(f"[InfluxDB v{influx_version}] {write_count} points written")
        else:
            error_count += 1
            log.warning(f"[InfluxDB] Status {r.status_code}: {r.text[:80]}")
    except Exception as e:
        error_count += 1
        log.error(f"[InfluxDB] Write error: {e}")

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        log.info(f"[MQTT] Connected. Subscribing to {MQTT_TOPIC}")
        client.subscribe(MQTT_TOPIC)
    else:
        log.error(f"[MQTT] rc={rc}")

def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
        line = json_to_lp(msg.topic, data)
        if line:
            write(line)
            if data.get("layer") == "phone":
                log.info(
                    f"[Ingested] {msg.topic}: carrier={data.get('carrier_name')}, "
                    f"network={data.get('network_type')}, RSRP={data.get('rsrp_dbm')} dBm, "
                    f"cell={data.get('cell_id')}"
                )
            else:
                log.info(f"[Ingested] {msg.topic}: RSSI={data.get('rssi_raw_dbm')} dBm, GW RTT={data.get('gw_rtt_mean_ms')}ms")
        else:
            log.warning(f"[Ignored] {msg.topic}: no supported numeric telemetry fields")
    except Exception as e:
        log.error(f"[Msg] {e}")

def on_disconnect(client, userdata, rc):
    if rc != 0: log.warning(f"[MQTT] Disconnected rc={rc}. Reconnecting...")

if __name__ == "__main__":
    log.info("=" * 50)
    log.info("   Trinetra MQTT → InfluxDB Bridge v1.0")
    log.info("=" * 50)
    ensure_db()
    c = mqtt.Client(client_id="piprobe_bridge")
    c.on_connect = on_connect
    c.on_message = on_message
    c.on_disconnect = on_disconnect
    c.connect(MQTT_BROKER, MQTT_PORT, 60)
    try:
        c.loop_forever()
    except KeyboardInterrupt:
        log.info(f"Stopped. Written: {write_count}, Errors: {error_count}")
        c.disconnect()
