
#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <cstring>

#include "wifi_scanner.h"

static void copyText(
    char* destination,
    size_t capacity,
    const char* source
) {
    if (capacity == 0) return;

    strncpy(destination, source, capacity - 1);
    destination[capacity - 1] = '\0';
}

static const char* securityName(uint8_t type) {

    switch (type) {
        case ENC_TYPE_NONE:
            return "OPEN";

        case ENC_TYPE_WEP:
            return "WEP";

        case ENC_TYPE_TKIP:
            return "WPA_TKIP";

        case ENC_TYPE_CCMP:
            return "WPA2_CCMP";

        case ENC_TYPE_AUTO:
            return "AUTO";

        default:
            return "UNKNOWN";
    }
}

uint8_t scanNetworks(
    AccessPoint* results,
    uint8_t capacity
) {
    Serial.println("[INFO] Starting Wi-Fi scan");

    int discovered = WiFi.scanNetworks(false, true);

    if (discovered == WIFI_SCAN_FAILED) {
        Serial.println("[ERROR] Wi-Fi scan failed");
        WiFi.scanDelete();
        return 0;
    }

    uint8_t stored = 0;

    for (int i = 0; i < discovered && stored < capacity; i++) {

        AccessPoint& ap = results[stored];

        String networkName = WiFi.SSID(i);
        String macAddress = WiFi.BSSIDstr(i);

        ap.hidden = (networkName.length() == 0);

        if (ap.hidden) {
            copyText(ap.ssid, sizeof(ap.ssid), "<Hidden>");
        } else {
            copyText(
                ap.ssid,
                sizeof(ap.ssid),
                networkName.c_str()
            );
        }

        copyText(
            ap.bssid,
            sizeof(ap.bssid),
            macAddress.c_str()
        );

        ap.rssi = WiFi.RSSI(i);
        ap.channel = WiFi.channel(i);
        ap.encryption = WiFi.encryptionType(i);

        stored++;
    }

    Serial.printf(
        "[INFO] Discovered: %d | Stored: %u\n",
        discovered,
        stored
    );

    if (discovered > capacity) {
        Serial.println(
            "[WARN] Network limit reached; some results omitted"
        );
    }

    WiFi.scanDelete();

    return stored;
}

static void printJsonString(const char* value) {

    Serial.print('"');

    while (*value) {

        unsigned char c = *value++;

        switch (c) {

            case '"':
                Serial.print("\\\"");
                break;

            case '\\':
                Serial.print("\\\\");
                break;

            case '\n':
                Serial.print("\\n");
                break;

            case '\r':
                Serial.print("\\r");
                break;

            case '\t':
                Serial.print("\\t");
                break;

            default:
                if (c < 0x20) {
                    Serial.print(' ');
                } else {
                    Serial.write(c);
                }
                break;
        }
    }

    Serial.print('"');
}

void printScanResults(
    const AccessPoint* results,
    uint8_t count,
    uint32_t scanId
) {

    for (uint8_t i = 0; i < count; i++) {

        const AccessPoint& ap = results[i];

        Serial.print("{\"protocol_version\":1");
        Serial.printf(",\"scan_id\":%lu", (unsigned long)scanId);

        Serial.printf(",\"index\":%u", i);
        Serial.printf(",\"total\":%u", count);

        Serial.print(",\"ssid\":");
        printJsonString(ap.ssid);

        Serial.print(",\"bssid\":");
        printJsonString(ap.bssid);

        Serial.printf(",\"rssi\":%d", ap.rssi);
        Serial.printf(",\"channel\":%u", ap.channel);

        Serial.print(",\"security\":");
        printJsonString(securityName(ap.encryption));

        Serial.printf(
            ",\"hidden\":%s",
            ap.hidden ? "true" : "false"
        );

        Serial.printf(
            ",\"timestamp_ms\":%lu",
            (unsigned long)millis()
        );

        Serial.println("}");
    }
}
