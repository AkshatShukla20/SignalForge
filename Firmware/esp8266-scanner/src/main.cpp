
#include <Arduino.h>
#include <ESP8266WiFi.h>

#include "wifi_scanner.h"
#include "display.h"

// Timing configuration
constexpr unsigned long SCAN_INTERVAL_MS = 10000;
constexpr unsigned long DISPLAY_INTERVAL_MS = 2000;

// Fixed-size access point storage
AccessPoint networks[MAX_NETWORKS];

uint8_t networkCount = 0;
uint8_t displayIndex = 0;

uint32_t scanId = 0;

unsigned long lastScanTime = 0;
unsigned long lastDisplayTime = 0;

void performScan() {

    scanId++;

    showScannerStatus("Scanning WiFi...");

    networkCount = scanNetworks(
        networks,
        MAX_NETWORKS
    );

    Serial.printf(
        "\n[SCAN] Scan ID: %lu\n",
        (unsigned long)scanId
    );

    Serial.printf(
        "[SCAN] Network count: %u\n",
        networkCount
    );

    printScanResults(
        networks,
        networkCount,
        scanId
    );

    showScanSummary(networkCount, scanId);

    displayIndex = 0;

    lastScanTime = millis();
    lastDisplayTime = millis();
}

void setup() {

    Serial.begin(115200);
    delay(500);

    Serial.println();
    Serial.println("================================");
    Serial.println(" SIGNALFORGE SCANNER v0.1");
    Serial.println(" ESP8266 NodeMCU ESP-12E");
    Serial.println("================================");

    initializeDisplay();

    // Wi-Fi station mode without connecting to an AP
    WiFi.mode(WIFI_STA);
    WiFi.disconnect();

    delay(200);

    showScannerStatus("Scanner Ready");

    Serial.println("[BOOT] Scanner initialized");

    performScan();
}

void loop() {

    unsigned long currentTime = millis();

    // Perform periodic scans
    if (currentTime - lastScanTime >= SCAN_INTERVAL_MS) {

        performScan();

        return;
    }

    // Cycle through discovered networks
    if (
        networkCount > 0 &&
        currentTime - lastDisplayTime >= DISPLAY_INTERVAL_MS
    ) {

        showAccessPoint(
            networks[displayIndex],
            displayIndex,
            networkCount
        );

        displayIndex++;

        if (displayIndex >= networkCount) {
            displayIndex = 0;
        }

        lastDisplayTime = currentTime;
    }
}
