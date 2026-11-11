# 📡 Edge Wi-Fi Spectrum & Signal Analyzer

An **End-to-End Hardware & Data Science Project** combining dual-microcontroller RF scanning, serial telemetry serialization, and a real-time Python analytics dashboard.

---

## 📌 Project Overview
This project transforms embedded microcontroller hardware (ESP32 / ESP32-C3 Super Mini & ESP8266) into a high-speed 2.4 GHz spectrum sniffer. Scanned telemetry—including Received Signal Strength Indicator (RSSI), BSSIDs, channel allocations, and security protocols—is outputted as structured JSON frames over USB Serial. A Python-powered analytics engine ingests this stream in real-time, leveraging **Pandas** for data processing and **Streamlit + Plotly** for interactive web visualizations.

---

## 🛠 Hardware & Software Stack

### Hardware Layer
* **Primary RF Sniffer & Scanner:** ESP32 / ESP32-C3 Super Mini (runs `WiFi.scanNetworks()` engine).
* **On-Device Diagnostics Display:** 0.91" I2C OLED Display (`SSD1306` 128x32) for live RSSI metrics.
* **Secondary Telemetry Node:** ESP8266 driving a 16x2 LCD display for status outputs.

### Software & Data Analytics Layer
* **Language:** Python 3.x
* **Firmware Framework:** C++ / Arduino / PlatformIO
* **Core Python Libraries:**
  * `pyserial` — Non-blocking USB Serial connection and raw packet stream buffering.
  * `pandas` — In-memory data manipulation, clean-up, time-series aggregation, and metrics calculation.
  * `streamlit` — Lightweight, responsive web frontend framework.
  * `plotly` — Dynamic, interactive data visualization (zoomable line charts, bar graphs, donut charts).

---

## 🏗 System Architecture & Telemetry Pipeline

```
┌───────────────────────────────────────┐
│     ESP32 / ESP32-C3 Super Mini       │
│  (Scans 2.4GHz Wi-Fi Channels 1-13)   │
└──────────────────┬────────────────────┘
                   │
         [0.91" OLED Display] ── Local RSSI Signal Meter
                   │
          (USB Serial Stream)
                   │
                   ▼
┌───────────────────────────────────────┐
│       pyserial Ingestion Engine       │
│         (dashboard/serial_data.py)    │
└──────────────────┬────────────────────┘
                   │
         [Data Cleaning & Pandas] ── Computes Log-Distance Path Loss
                   │
                   ▼
┌───────────────────────────────────────┐
│     Streamlit + Plotly Frontend       │
│           (dashboard/app.py)          │
└───────────────────────────────────────┘
```

---

## 📦 Data Transmission Protocol (JSON Schema)

The microcontroller emits formatted JSON array strings over standard serial at **115200 baud** following every scan cycle:

```json
[
  {
    "ssid": "Home_Network_5G",
    "bssid": "AA:BB:CC:DD:EE:FF",
    "rssi": -55,
    "channel": 6,
    "security": "WPA2"
  },
  {
    "ssid": "Guest_Wi-Fi",
    "bssid": "11:22:33:44:55:66",
    "rssi": -82,
    "channel": 11,
    "security": "OPEN"
  }
]
```

---

## 📊 Dashboard Modules & Feature Specs

The Python dashboard features **5 interactive analytics modules**:

1. **Channel Congestion Heatmap (Bar Chart):** 
   * Maps active network counts per channel (Channels 1 to 13).
   * Identifies co-channel interference and congested frequency bands.
2. **Real-Time Signal Strength Tracker (Line Graph):**
   * Live time-series plot tracking RSSI degradation over time for targeted SSIDs.
3. **Security Audit Breakdown (Donut Chart):**
   * Categorizes detected networks by encryption protocol (`WPA2`, `WPA3`, `OPEN`, `WEP`).
4. **Log-Distance Path Loss Distance Estimator:**
   * Converts raw dBm RSSI into estimated physical distance in meters using the RF propagation formula:
     $$\text{Distance} = 10^{\frac{A - \text{RSSI}}{10 \cdot n}}$$
     *(Where $A$ is reference RSSI at 1m, and $n$ is path loss exponent).*
5. **Live Telemetry Data Table:**
   * Filterable, searchable Pandas dataframe output with color-coded RSSI status tags.

---

## 📁 Repository Directory Structure

```text
wifi-spectrum-analyzer/
├── firmware/                 # C++ Microcontroller Code (PlatformIO / Arduino)
│   ├── src/
│   │   └── main.cpp          # ESP32 channel scanner & JSON serializer
│   └── platformio.ini        # Hardware targets & environment configuration
│
├── dashboard/                # Python Analytics & Web App
│   ├── app.py                # Main Streamlit interface & Plotly dashboard
│   ├── serial_data.py        # PySerial connection & Pandas pipeline class
│   └── requirements.txt      # Dependency list
│
├── data_logs/                # Auto-saved CSV logs of spectrum scans
└── README.md                 # Complete project documentation & AI prompt spec
```

---

## 🚀 Quickstart & Setup Guide

### 1. Installation
Clone the repository and install required packages:
```bash
pip install pyserial pandas streamlit plotly
```

### 2. Microcontroller Setup
Upload `firmware/src/main.cpp` to your ESP32 board using PlatformIO or Arduino IDE. Ensure the baud rate is set to `115200`.

### 3. Running the Dashboard
Launch the Streamlit web dashboard directly from your terminal:
```bash
streamlit run dashboard/app.py
```
*Or using explicit Python module invocation:*
```bash
python -m streamlit run dashboard/app.py
```

---

## 🤖 Context Briefing for LLM / GPT Assistants

> **Note for GPT Context:**  
> When assisting with this repository, keep the following rules in mind:
> 1. All C++ microcontroller code must parse Wi-Fi scan data cleanly into a compact JSON array emitted via `Serial.println()`.
> 2. The Python backend uses a class `WiFiSerialReader` in `serial_data.py` to continuously parse USB serial JSON lines into `pandas.DataFrame` objects.
> 3. The frontend interface relies entirely on **Streamlit** and **Plotly** for UI components and interactive charts inside `app.py`.
> 4. Ensure all serial handling accounts for non-blocking execution, buffer timeouts, and corrupted frame handling (`json.JSONDecodeError`).