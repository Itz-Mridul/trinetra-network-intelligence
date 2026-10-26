#!/data/data/com.termux/files/usr/bin/bash
# Trinetra phone telemetry sender for Termux and Termux:API.
# Usage:
#   PI_IP=<PI_IP> PIPROBE_CARRIER=JIO SESSION_ID=jio_001 ./termux_sender.sh
#   PI_IP=<PI_IP> PIPROBE_CARRIER=BSNL SESSION_ID=bsnl_001 ./termux_sender.sh

set -u

PI_IP="${PI_IP:-}"
MQTT_PORT="${MQTT_PORT:-1883}"
MQTT_TOPIC="${MQTT_TOPIC:-piprobe/phone/telemetry}"
PIPROBE_CARRIER="${PIPROBE_CARRIER:-AUTO}"
SESSION_ID="${SESSION_ID:-phone_$(date -u +%Y%m%dT%H%M%SZ)}"
SITE_ID="${SITE_ID:-COLLEGE}"
LOCATION_ID="${LOCATION_ID:-college_gate}"
INTERVAL_SEC="${INTERVAL_SEC:-15}"

if [ -z "$PI_IP" ]; then
  echo "Set PI_IP to the Raspberry Pi address before starting." >&2
  exit 2
fi

detect_carrier() {
  DETECTED_ORG=""
  local response org normalized
  response="$(curl -4 -fsS --max-time 5 https://ipinfo.io/json 2>/dev/null || true)"
  org="$(printf '%s' "$response" | jq -r '.org // ""' 2>/dev/null || true)"
  if [ -z "$org" ]; then
    org="$(curl -4 -fsS --max-time 5 https://ipapi.co/org/ 2>/dev/null || true)"
  fi
  DETECTED_ORG="$org"
  normalized="$(printf '%s' "$org" | tr '[:upper:]' '[:lower:]')"
  case "$normalized" in
    *"9829"*|*"national internet backbone"*|*"bsnl"*) DETECTED_CARRIER="BSNL" ;;
    *"jio"*|*"reliance"*) DETECTED_CARRIER="JIO" ;;
    *) DETECTED_CARRIER="UNKNOWN" ;;
  esac
}

while true; do
  DEV="$(termux-telephony-deviceinfo 2>/dev/null || echo '{}')"
  LOC="$(termux-location -p network -r once 2>/dev/null || echo '{}')"
  CELL="$(termux-telephony-cellinfo 2>/dev/null || echo '[]')"

  [ -n "$DEV" ] || DEV='{}'
  [ -n "$LOC" ] || LOC='{}'
  [ -n "$CELL" ] || CELL='[]'

  detect_carrier
  if [ "$DETECTED_CARRIER" = "UNKNOWN" ] && [ "$PIPROBE_CARRIER" != "AUTO" ]; then
    DETECTED_CARRIER="$PIPROBE_CARRIER"
  fi

  jq -n -c \
    --argjson d "$DEV" \
    --argjson l "$LOC" \
    --argjson c "$CELL" \
    --arg carrier "$DETECTED_CARRIER" \
    --arg requested "$PIPROBE_CARRIER" \
    --arg session "$SESSION_ID" \
    --arg site "$SITE_ID" \
    --arg location "$LOCATION_ID" '
    ($c | map(select((.registered == true) or (.registered == "true"))) |
      sort_by(if .type == "lte" then 0 else 1 end) | .[0] //
      ($c | map(select(.type == "lte")) | .[0]) // {}) as $cell |
    {
      timestamp: now,
      probe_id: "phone_1",
      layer: "phone",
      site_id: $site,
      session_id: $session,
      location_id: $location,
      selected_carrier: $carrier,
      requested_carrier: $requested,
      carrier_name: $carrier,
      telemetry_received: 1,
      reported_operator_name: ($d.network_operator_name // null),
      network_type: ($cell.type // $d.network_type // null),
      data_state: ($d.data_state // null),
      cell_id: ($cell.ci // $cell.cid // null),
      rsrp_dbm: ($cell.rsrp // $cell.dbm // null),
      rsrq_db: ($cell.rsrq // null),
      mcc: ($cell.mcc // null),
      mnc: ($cell.mnc // null),
      band: (($cell.bands // [null]) | .[0]),
      pci: ($cell.pci // null),
      tac: ($cell.tac // null),
      latitude: ($l.latitude // null),
      longitude: ($l.longitude // null),
      accuracy_m: ($l.accuracy // null)
    }' |
    mosquitto_pub -h "$PI_IP" -p "$MQTT_PORT" -t "$MQTT_TOPIC" -s

  echo "Telemetry sent: detected_carrier=$DETECTED_CARRIER requested_carrier=$PIPROBE_CARRIER public_org=${DETECTED_ORG:-Unavailable} session=$SESSION_ID"
  sleep "$INTERVAL_SEC"
done
