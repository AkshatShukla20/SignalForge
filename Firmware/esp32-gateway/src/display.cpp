
#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#include "display.h"

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 32

#define OLED_SDA 21
#define OLED_SCL 22
#define OLED_ADDRESS 0x3C
#define OLED_RESET -1

static Adafruit_SSD1306 display(
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    &Wire,
    OLED_RESET
);

static bool displayReady = false;

bool initializeDisplay() {

    Wire.begin(OLED_SDA, OLED_SCL);

    displayReady = display.begin(
        SSD1306_SWITCHCAPVCC,
        OLED_ADDRESS
    );

    if (!displayReady) {
        Serial.println("[ERROR] OLED initialization failed");
        return false;
    }

    display.clearDisplay();
    display.setTextColor(SSD1306_WHITE);
    display.setTextSize(1);
    display.setTextWrap(false);

    display.display();

    Serial.println("[DISPLAY] SSD1306 initialized");

    return true;
}

void showBootScreen() {

    if (!displayReady) return;

    display.clearDisplay();

    display.setTextSize(2);

    display.setCursor(0, 0);
    display.println("SIGNAL");

    display.setCursor(0, 16);
    display.println("FORGE");

    display.display();
}

void showGatewayStatus(
    const char* systemStatus,
    const char* espNowStatus
) {

    if (!displayReady) return;

    display.clearDisplay();

    display.setTextSize(1);

    display.setCursor(0, 0);
    display.println("SIGNALFORGE GATEWAY");

    display.drawLine(0, 10, 127, 10, SSD1306_WHITE);

    display.setCursor(0, 13);
    display.print("SYSTEM: ");
    display.println(systemStatus);

    display.setCursor(0, 23);
    display.print("ESP-NOW: ");
    display.println(espNowStatus);

    display.display();
}

void showMessage(
    const char* line1,
    const char* line2
) {

    if (!displayReady) return;

    display.clearDisplay();

    display.setTextSize(1);

    display.setCursor(0, 5);
    display.println(line1);

    display.setCursor(0, 19);
    display.println(line2);

    display.display();
}
