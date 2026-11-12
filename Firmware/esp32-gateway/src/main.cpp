
#include <Arduino.h>

#include "display.h"

constexpr unsigned long STATUS_INTERVAL_MS = 3000;

unsigned long lastStatusUpdate = 0;

bool oledInitialized = false;

void setup() {

    Serial.begin(115200);
    delay(500);

    Serial.println();
    Serial.println("================================");
    Serial.println(" SIGNALFORGE GATEWAY v0.1");
    Serial.println(" ESP32 DevKit V1");
    Serial.println("================================");

    // Initialize OLED and verify success
    oledInitialized = initializeDisplay();

    if (oledInitialized) {

        showBootScreen();

        delay(1500);

        showGatewayStatus(
            "READY",
            "PENDING"
        );

        Serial.println("[BOOT] Gateway initialization complete");
        Serial.println("[STATUS] System: READY");
        Serial.println("[STATUS] ESP-NOW: PENDING");

    } else {

        Serial.println("[FATAL] OLED unavailable");
        Serial.println("[FATAL] Check I2C wiring and address");
    }

    lastStatusUpdate = millis();
}

void loop() {

    if (!oledInitialized) {
        delay(1000);
        return;
    }

    unsigned long currentTime = millis();

    if (
        currentTime - lastStatusUpdate >=
        STATUS_INTERVAL_MS
    ) {

        lastStatusUpdate = currentTime;

        Serial.println("[HEARTBEAT] Gateway running");

        showGatewayStatus(
            "READY",
            "PENDING"
        );
    }
}
