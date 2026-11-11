
#pragma once

#include <Arduino.h>
#include "wifi_scanner.h"

void initializeDisplay();

void showScannerStatus(const char* message);

void showScanSummary(uint8_t count, uint32_t scanId);

void showAccessPoint(
    const AccessPoint& ap,
    uint8_t index,
    uint8_t total
);
