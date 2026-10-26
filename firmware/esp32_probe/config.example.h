#ifndef PIPROBE_CONFIG_H
#define PIPROBE_CONFIG_H

// Trinetra ESP32 Probe Configuration Template
// Copy this file to config.h and fill in your actual credentials.
// NEVER commit config.h to version control.

#define WIFI_SSID         "Your_WiFi_SSID"
#define WIFI_PASSWORD     "Your_WiFi_Password"

#define MQTT_BROKER       "192.168.43.120"  // Replace with the Pi's current hotspot IP; mDNS is optional.
#define MQTT_PORT         1883

#define PROBE_ID          "esp_probe_1"     // Stable hardware identity
#define SITE_ID           "site_001"        // Building/customer/site identifier
#define SESSION_ID        ""                // Empty = generate a new session on boot; set per field run for repeatability.
#define LOCATION_ID       "location_001"    // Room, floor, vehicle, or survey point; update through the setup portal when moving.
#define ROOM_ID           LOCATION_ID        // Backward-compatible field name
#define CALIBRATION_BIAS  0.0  // Individual board RSSI calibration offset in dBm

#endif // PIPROBE_CONFIG_H
