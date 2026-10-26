// Trinetra ESP32 Wi-Fi probe
//
// Measures the local Wi-Fi path and publishes evidence to the Raspberry Pi.
// Runtime settings are stored in ESP32 Preferences, so moving to another
// hotspot does not require a new firmware upload.

#include <WiFi.h>
#include <PubSubClient.h>
#include <WebServer.h>
#include <Preferences.h>
#include <time.h>
#include <math.h>
#include <string.h>

#if __has_include("config.h")
  #include "config.h"
#else
  #define WIFI_SSID ""
  #define WIFI_PASSWORD ""
  #define MQTT_BROKER ""
  #define MQTT_PORT 1883
  #define PROBE_ID ""
  #define ROOM_ID "unassigned"
  #define SITE_ID ""
  #define SESSION_ID ""
  #define LOCATION_ID ""
  #define CALIBRATION_BIAS 0.0
#endif

#ifndef SITE_ID
  #define SITE_ID ""
#endif
#ifndef SESSION_ID
  #define SESSION_ID ""
#endif
#ifndef LOCATION_ID
  #define LOCATION_ID ""
#endif

WiFiClient espClient;
PubSubClient mqttClient(espClient);
WebServer configServer(80);
Preferences configPrefs;

char active_wifi_ssid[96] = "";
char active_wifi_password[96] = "";
char active_mqtt_broker[96] = "";
uint16_t active_mqtt_port = MQTT_PORT;
char active_probe_id[32] = "";
char active_site_id[64] = "";
char active_session_id[64] = "";
char active_location_id[64] = "";
char active_fault_class[32] = "normal";
char active_run_id[64] = "run_baseline";
char active_split[32] = "train";

bool config_portal_active = false;
bool config_button_triggered = false;
unsigned long config_button_started_ms = 0;
unsigned long last_telemetry_ms = 0;
unsigned long reconnect_count = 0;
unsigned int mqtt_failure_count = 0;

const uint8_t CONFIG_BUTTON_PIN = 0;
const unsigned long TELEMETRY_INTERVAL_MS = 10000;
const unsigned long CONFIG_BUTTON_HOLD_MS = 2500;

IPAddress gateway_ip;
IPAddress pi_ip;

struct RttResult {
  float mean_ms;
  float jitter_ms;
  float loss_pct;
};

void copySetting(char *destination, size_t destination_size,
                 const char *fallback, const char *key) {
  size_t copied = configPrefs.getString(key, destination, destination_size);
  if (copied == 0 && fallback != nullptr) {
    strncpy(destination, fallback, destination_size - 1);
    destination[destination_size - 1] = '\0';
  }
  destination[destination_size - 1] = '\0';
}

void loadRuntimeConfig() {
  configPrefs.begin("settings", true);
  copySetting(active_wifi_ssid, sizeof(active_wifi_ssid), WIFI_SSID, "wifi_ssid");
  copySetting(active_wifi_password, sizeof(active_wifi_password), WIFI_PASSWORD, "wifi_password");
  copySetting(active_mqtt_broker, sizeof(active_mqtt_broker), MQTT_BROKER, "mqtt_broker");
  copySetting(active_probe_id, sizeof(active_probe_id), PROBE_ID, "probe_id");
  copySetting(active_site_id, sizeof(active_site_id), SITE_ID, "site_id");
  copySetting(active_session_id, sizeof(active_session_id), SESSION_ID, "session_id");
  copySetting(active_location_id, sizeof(active_location_id), LOCATION_ID, "location_id");
  active_mqtt_port = configPrefs.getUShort("mqtt_port", MQTT_PORT);
  configPrefs.end();
}

String configPage() {
  String html = F(
    "<!doctype html><html><head><meta name='viewport' content='width=device-width,initial-scale=1'>"
    "<title>Trinetra setup</title><style>body{font-family:Arial;max-width:620px;margin:24px auto;padding:0 16px;"
    "line-height:1.45}input{width:100%;box-sizing:border-box;padding:10px;margin:5px 0 14px}"
    "button{padding:12px 18px;font-size:16px}small{color:#555}</style></head><body>"
    "<h1>Trinetra ESP32 setup</h1>"
    "<p>Enter the Wi-Fi and Raspberry Pi details for this location. The ESP32 will save them and restart.</p>"
    "<p><small>After saving, reconnect the phone to its normal hotspot. You do not need to upload the code again when the location changes.</small></p>"
    "<form method='POST' action='/save'>"
    "Wi-Fi name<input name='wifi_ssid' value='%WIFI_SSID%' required>"
    "Wi-Fi password<input name='wifi_password' type='password' value='%WIFI_PASSWORD%'>"
    "Raspberry Pi IP or hostname<input name='mqtt_broker' value='%MQTT_BROKER%' required>"
    "MQTT port<input name='mqtt_port' type='number' value='%MQTT_PORT%' min='1' max='65535'>"
    "Probe ID<input name='probe_id' value='%PROBE_ID%' required>"
    "Site name or ID<input name='site_id' value='%SITE_ID%'>"
    "Session ID<input name='session_id' value='%SESSION_ID%'>"
    "Room or location ID<input name='location_id' value='%LOCATION_ID%'>"
    "<button type='submit'>Save and restart</button></form>"
    "<p><small>Setup address: http://192.168.4.1/</small></p></body></html>"
  );
  html.replace("%WIFI_SSID%", active_wifi_ssid);
  html.replace("%WIFI_PASSWORD%", active_wifi_password);
  html.replace("%MQTT_BROKER%", active_mqtt_broker);
  html.replace("%MQTT_PORT%", String(active_mqtt_port));
  html.replace("%PROBE_ID%", active_probe_id);
  html.replace("%SITE_ID%", active_site_id);
  html.replace("%SESSION_ID%", active_session_id);
  html.replace("%LOCATION_ID%", active_location_id);
  return html;
}

void saveRuntimeConfig() {
  configPrefs.begin("settings", false);
  configPrefs.putString("wifi_ssid", configServer.arg("wifi_ssid"));
  configPrefs.putString("wifi_password", configServer.arg("wifi_password"));
  configPrefs.putString("mqtt_broker", configServer.arg("mqtt_broker"));
  configPrefs.putUShort("mqtt_port", (uint16_t)configServer.arg("mqtt_port").toInt());
  configPrefs.putString("probe_id", configServer.arg("probe_id"));
  configPrefs.putString("site_id", configServer.arg("site_id"));
  configPrefs.putString("session_id", configServer.arg("session_id"));
  configPrefs.putString("location_id", configServer.arg("location_id"));
  configPrefs.end();
  configServer.send(200, "text/html",
                   "<h2>Saved.</h2><p>Trinetra is restarting and will use the new settings.</p>");
  delay(1200);
  ESP.restart();
}

void startConfigPortal() {
  if (config_portal_active) return;

  uint32_t chip_id = (uint32_t)(ESP.getEfuseMac() & 0xFFFFFF);
  String ap_name = String("Trinetra-Setup-") + String(chip_id, HEX);
  WiFi.disconnect(false, false);
  WiFi.mode(WIFI_AP);
  WiFi.softAP(ap_name.c_str(), "trinetra123");

  configServer.on("/", HTTP_GET, []() {
    configServer.send(200, "text/html", configPage());
  });
  configServer.on("/save", HTTP_POST, saveRuntimeConfig);
  configServer.onNotFound([]() {
    configServer.sendHeader("Location", "/");
    configServer.send(302, "text/plain", "Redirecting");
  });
  configServer.begin();
  config_portal_active = true;

  Serial.println();
  Serial.println("[SETUP] Configuration portal started");
  Serial.print("[SETUP] Wi-Fi network: ");
  Serial.println(ap_name);
  Serial.println("[SETUP] Password: trinetra123");
  Serial.println("[SETUP] Open http://192.168.4.1/");
}

void handleConfigButton() {
  if (config_portal_active) return;

  if (digitalRead(CONFIG_BUTTON_PIN) == LOW) {
    if (config_button_started_ms == 0) config_button_started_ms = millis();
    if (!config_button_triggered && millis() - config_button_started_ms >= CONFIG_BUTTON_HOLD_MS) {
      config_button_triggered = true;
      Serial.println("[SETUP] BOOT button held; opening configuration portal");
      startConfigPortal();
    }
  } else {
    config_button_started_ms = 0;
    config_button_triggered = false;
  }
}

bool extractJsonString(const char *json, const char *key, char *out, size_t out_size) {
  String needle = String("\"") + key + "\"";
  const char *start = strstr(json, needle.c_str());
  if (start == nullptr) return false;
  start = strchr(start + needle.length(), ':');
  if (start == nullptr) return false;
  start++;
  while (*start == ' ' || *start == '\t') start++;
  if (*start != '"') return false;
  start++;
  const char *end = strchr(start, '"');
  if (end == nullptr) return false;
  size_t length = (size_t)(end - start);
  if (length >= out_size) length = out_size - 1;
  memcpy(out, start, length);
  out[length] = '\0';
  return true;
}

void mqttCallback(char *topic, byte *payload, unsigned int length) {
  (void)topic;
  char message[512];
  size_t copy_length = length < sizeof(message) - 1 ? length : sizeof(message) - 1;
  memcpy(message, payload, copy_length);
  message[copy_length] = '\0';

  char value[96];
  if (extractJsonString(message, "fault_class", value, sizeof(value))) {
    strncpy(active_fault_class, value, sizeof(active_fault_class) - 1);
    active_fault_class[sizeof(active_fault_class) - 1] = '\0';
  }
  if (extractJsonString(message, "run_id", value, sizeof(value))) {
    strncpy(active_run_id, value, sizeof(active_run_id) - 1);
    active_run_id[sizeof(active_run_id) - 1] = '\0';
  }
  if (extractJsonString(message, "split", value, sizeof(value))) {
    strncpy(active_split, value, sizeof(active_split) - 1);
    active_split[sizeof(active_split) - 1] = '\0';
  }
}

void connectWiFi() {
  if (config_portal_active || WiFi.status() == WL_CONNECTED) return;
  if (strlen(active_wifi_ssid) == 0 || strlen(active_mqtt_broker) == 0) {
    startConfigPortal();
    return;
  }

  Serial.print("[Wi-Fi] Connecting to ");
  Serial.println(active_wifi_ssid);
  WiFi.mode(WIFI_STA);
  WiFi.begin(active_wifi_ssid, active_wifi_password);
  for (int attempt = 0; attempt < 30 && WiFi.status() != WL_CONNECTED; attempt++) {
    delay(500);
    Serial.print('.');
  }
  Serial.println();

  if (WiFi.status() != WL_CONNECTED) {
    reconnect_count++;
    Serial.println("[Wi-Fi] Connection failed; hold BOOT to open setup");
    startConfigPortal();
    return;
  }

  gateway_ip = WiFi.gatewayIP();
  pi_ip = IPAddress();
  IPAddress numeric_broker;
  if (numeric_broker.fromString(active_mqtt_broker)) {
    pi_ip = numeric_broker;
  } else if (WiFi.hostByName(active_mqtt_broker, pi_ip) != 1) {
    Serial.println("[MQTT] Could not resolve broker hostname");
  }

  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  Serial.print("[Wi-Fi] IP: ");
  Serial.println(WiFi.localIP());
  Serial.print("[Wi-Fi] Gateway: ");
  Serial.println(gateway_ip);
}

void initializeIdentity() {
  uint32_t chip_id = (uint32_t)(ESP.getEfuseMac() & 0xFFFFFF);
  char generated[32];

  if (strlen(active_probe_id) == 0) {
    snprintf(generated, sizeof(generated), "esp_%06lX", (unsigned long)chip_id);
    strncpy(active_probe_id, generated, sizeof(active_probe_id) - 1);
  }
  if (strlen(active_site_id) == 0) strncpy(active_site_id, "site_unassigned", sizeof(active_site_id) - 1);
  if (strlen(active_location_id) == 0) strncpy(active_location_id, "location_unassigned", sizeof(active_location_id) - 1);
  if (strlen(active_session_id) == 0) {
    snprintf(generated, sizeof(generated), "run_%08lX_%06lX",
             (unsigned long)millis(), (unsigned long)chip_id);
    strncpy(active_session_id, generated, sizeof(active_session_id) - 1);
  }
  active_probe_id[sizeof(active_probe_id) - 1] = '\0';
  active_site_id[sizeof(active_site_id) - 1] = '\0';
  active_location_id[sizeof(active_location_id) - 1] = '\0';
  active_session_id[sizeof(active_session_id) - 1] = '\0';

  Serial.print("[Identity] probe=");
  Serial.print(active_probe_id);
  Serial.print(" site=");
  Serial.print(active_site_id);
  Serial.print(" location=");
  Serial.println(active_location_id);
}

bool validAddress(const IPAddress &address) {
  return !(address[0] == 0 && address[1] == 0 && address[2] == 0 && address[3] == 0);
}

RttResult measureTargetRtt(const IPAddress &target, uint16_t port) {
  RttResult result = {0.0f, 0.0f, 100.0f};
  if (!validAddress(target)) return result;

  const int attempts = 3;
  float values[attempts];
  int successful = 0;
  for (int i = 0; i < attempts; i++) {
    WiFiClient test_client;
    unsigned long started = millis();
    if (test_client.connect(target, port)) {
      values[successful++] = (float)(millis() - started);
      test_client.stop();
    }
    delay(20);
  }
  if (successful == 0) return result;

  float sum = 0.0f;
  for (int i = 0; i < successful; i++) sum += values[i];
  result.mean_ms = sum / successful;
  float variance = 0.0f;
  for (int i = 0; i < successful; i++) {
    float difference = values[i] - result.mean_ms;
    variance += difference * difference;
  }
  result.jitter_ms = sqrtf(variance / successful);
  result.loss_pct = 100.0f * (attempts - successful) / attempts;
  return result;
}

int countSameChannelAccessPoints(int current_channel, int &total) {
  int raw_total = WiFi.scanNetworks(false, true);
  total = raw_total > 0 ? raw_total : 0;
  int same_channel = 0;
  for (int i = 0; i < total; i++) {
    if (WiFi.channel(i) == current_channel) same_channel++;
  }
  WiFi.scanDelete();
  return same_channel;
}

void reconnectMQTT() {
  if (config_portal_active || WiFi.status() != WL_CONNECTED || mqttClient.connected()) return;

  for (int attempt = 0; attempt < 3 && !mqttClient.connected(); attempt++) {
    String client_id = String(active_probe_id) + "_" + String((uint32_t)ESP.getEfuseMac(), HEX);
    Serial.print("[MQTT] Connecting to broker at ");
    Serial.print(active_mqtt_broker);
    Serial.print(" ... ");
    if (mqttClient.connect(client_id.c_str())) {
      Serial.println("connected");
      mqttClient.subscribe("piprobe/control/state");
      mqtt_failure_count = 0;
      return;
    }
    Serial.print("failed, rc=");
    Serial.println(mqttClient.state());
    mqtt_failure_count++;
    delay(500);
  }

  if (mqtt_failure_count >= 3) {
    Serial.println("[MQTT] Repeated failures; hold BOOT to open setup");
  }
}

void publishTelemetry() {
  int ap_total = 0;
  int ap_same_channel = countSameChannelAccessPoints(WiFi.channel(), ap_total);

  RttResult gateway_rtt = measureTargetRtt(gateway_ip, 53);
  if (gateway_rtt.loss_pct >= 100.0f) gateway_rtt = measureTargetRtt(gateway_ip, 80);
  RttResult pi_rtt = measureTargetRtt(pi_ip, active_mqtt_port);
  if (gateway_rtt.loss_pct >= 100.0f && pi_rtt.loss_pct < 100.0f) gateway_rtt = pi_rtt;

  time_t now = time(nullptr);
  if (now < 100000) now = 0;
  String bssid = WiFi.BSSIDstr();
  float raw_rssi = (float)WiFi.RSSI();
  float calibrated_rssi = raw_rssi + (float)CALIBRATION_BIAS;
  unsigned long uptime_seconds = millis() / 1000UL;

  char payload[1400];
  int length = snprintf(
    payload, sizeof(payload),
    "{\"timestamp\":%lu,\"probe_id\":\"%s\",\"site_id\":\"%s\","
    "\"session_id\":\"%s\",\"layer\":\"wifi\",\"room_id\":\"%s\","
    "\"location_id\":\"%s\",\"rssi_raw_dbm\":%.1f,\"rssi_calibrated_dbm\":%.1f,"
    "\"channel\":%d,\"bssid\":\"%s\",\"ap_count_total\":%d,"
    "\"ap_count_on_channel\":%d,\"gw_rtt_mean_ms\":%.2f,\"gw_rtt_jitter_ms\":%.2f,"
    "\"gw_loss_pct\":%.1f,\"pi_rtt_mean_ms\":%.2f,\"pi_rtt_jitter_ms\":%.2f,"
    "\"pi_loss_pct\":%.1f,\"uptime_sec\":%lu,\"free_heap_bytes\":%lu,"
    "\"reconnect_count\":%lu,\"fault_class\":\"%s\",\"run_id\":\"%s\","
    "\"split\":\"%s\"}",
    (unsigned long)now, active_probe_id, active_site_id, active_session_id,
    active_location_id, active_location_id, raw_rssi, calibrated_rssi, WiFi.channel(), bssid.c_str(),
    ap_total, ap_same_channel, gateway_rtt.mean_ms, gateway_rtt.jitter_ms,
    gateway_rtt.loss_pct, pi_rtt.mean_ms, pi_rtt.jitter_ms, pi_rtt.loss_pct,
    uptime_seconds, (unsigned long)ESP.getFreeHeap(), reconnect_count,
    active_fault_class, active_run_id, active_split);

  if (length <= 0 || length >= (int)sizeof(payload)) {
    Serial.println("[MQTT] Telemetry payload was too large");
    return;
  }

  String topic = String("piprobe/") + active_probe_id + "/wifi";
  bool published = mqttClient.publish(topic.c_str(), payload);
  Serial.print("[MQTT] ");
  Serial.print(published ? "published " : "publish failed ");
  Serial.println(payload);
}

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println();
  Serial.println("=== Trinetra ESP32 probe ===");

  pinMode(CONFIG_BUTTON_PIN, INPUT_PULLUP);
  loadRuntimeConfig();
  initializeIdentity();
  mqttClient.setServer(active_mqtt_broker, active_mqtt_port);
  mqttClient.setCallback(mqttCallback);
  mqttClient.setBufferSize(1024);
  connectWiFi();
}

void loop() {
  handleConfigButton();
  if (config_portal_active) {
    configServer.handleClient();
    delay(2);
    return;
  }

  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
    delay(50);
    return;
  }

  if (!mqttClient.connected()) reconnectMQTT();
  mqttClient.loop();

  if (mqttClient.connected() && millis() - last_telemetry_ms >= TELEMETRY_INTERVAL_MS) {
    last_telemetry_ms = millis();
    publishTelemetry();
  }
  delay(5);
}
