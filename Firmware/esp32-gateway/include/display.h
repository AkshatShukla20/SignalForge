
#pragma once

#include <Arduino.h>

bool initializeDisplay();

void showBootScreen();

void showGatewayStatus(
    const char* systemStatus,
    const char* espNowStatus
);

void showMessage(
    const char* line1,
    const char* line2
);
