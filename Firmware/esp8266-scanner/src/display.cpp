
#include <Arduino.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

#include "display.h"

#define LCD_ADDRESS 0x27
#define LCD_SDA_PIN 4
#define LCD_SCL_PIN 5

static LiquidCrystal_I2C lcd(
    LCD_ADDRESS,
    16,
    2
);

void initializeDisplay() {

    Wire.begin(LCD_SDA_PIN, LCD_SCL_PIN);

    lcd.init();
    lcd.backlight();
    lcd.clear();

    lcd.setCursor(0, 0);
    lcd.print("SIGNALFORGE");

    lcd.setCursor(0, 1);
    lcd.print("Initializing...");
}

void showScannerStatus(const char* message) {

    lcd.clear();

    lcd.setCursor(0, 0);
    lcd.print("SIGNALFORGE");

    lcd.setCursor(0, 1);
    lcd.print(message);
}

void showScanSummary(uint8_t count, uint32_t scanId) {

    char line1[17];
    char line2[17];

    snprintf(
        line1,
        sizeof(line1),
        "Networks: %02u",
        count
    );

    snprintf(
        line2,
        sizeof(line2),
        "Scan ID: %lu",
        (unsigned long)scanId
    );

    lcd.clear();

    lcd.setCursor(0, 0);
    lcd.print(line1);

    lcd.setCursor(0, 1);
    lcd.print(line2);
}


void showAccessPoint(
    const AccessPoint& ap,
    uint8_t index,
    uint8_t total
) {

    char line1[17];
    char line2[17];

    snprintf(
        line1,
        sizeof(line1),
        "%02u/%02u %s",
        index + 1,
        total,
        ap.ssid
    );

    snprintf(
        line2,
        sizeof(line2),
        "RSSI: %d dBm",
        ap.rssi
    );

    lcd.clear();

    lcd.setCursor(0, 0);
    lcd.print(line1);

    lcd.setCursor(0, 1);
    lcd.print(line2);
}