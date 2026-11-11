
#pragma once

#include <Arduino.h>

constexpr uint8_t MAX_NETWORKS = 20;

struct AccessPoint {
    char ssid[33];
    char bssid[18];

    int16_t rssi;
    uint8_t channel;
    uint8_t encryption;

    bool hidden;
};

// Performs a scan and fills the supplied array.
// Returns the number of stored access points.
uint8_t scanNetworks(
    AccessPoint* results,
    uint8_t capacity
);

// Prints one JSON object per access point.
void printScanResults(
    const AccessPoint* results,
    uint8_t count,
    uint32_t scanId
);
