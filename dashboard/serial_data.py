import json
import random
import time
import pandas as pd
import serial
import serial.tools.list_ports

# Baseline RSSI values for realistic Mock Mode jitter across scans
_MOCK_BASELINE = {
    "Excitel_Fiber_2.4G": ("7C:A9:6B:B7:39:55", 1, "WPA2", -52),
    "Airtel_Xstream_Home": ("44:99:5B:04:6E:41", 6, "WPA2", -61),
    "JioFiber_GroundFloor": ("88:A6:8D:99:65:87", 6, "WPA3", -67),
    "Neighbor_Mesh_Net": ("F0:ED:B8:85:37:38", 11, "WPA2", -76),
    "Free_Guest_WiFi": ("D2:83:94:B7:5F:3D", 3, "OPEN", -71),
    "TP-Link_Office_AP": ("AA:10:07:9C:E7:74", 6, "WPA2", -58),
    "<HIDDEN>": ("68:79:C4:93:A6:48", 9, "WPA2", -82),
}


def list_serial_ports() -> list[str]:
    """Returns available system COM ports, or default Windows placeholders."""
    ports = serial.tools.list_ports.comports()
    return [p.device for p in ports] if ports else ["COM3", "COM4", "COM5"]


def generate_mock_scan() -> pd.DataFrame:
    """Generates realistic synthetic 2.4 GHz Wi-Fi scan records for offline UI testing."""
    rows = []
    for ssid, (bssid, ch, sec, base_rssi) in _MOCK_BASELINE.items():
        jittered_rssi = max(-95, min(-30, base_rssi + random.randint(-3, 3)))
        rows.append(
            {
                "ssid": ssid,
                "bssid": bssid,
                "rssi": jittered_rssi,
                "channel": ch,
                "security": sec,
                "hidden": 1 if ssid == "<HIDDEN>" else 0,
            }
        )
    return _enrich_dataframe(pd.DataFrame(rows))


def _enrich_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Normalizes columns, sanitizes hidden SSIDs, and computes path-loss distance."""
    if df.empty:
        return df

    defaults = {
        "ssid": "<HIDDEN>",
        "bssid": "00:00:00:00:00:00",
        "rssi": -90,
        "channel": 1,
        "security": "UNKNOWN",
    }
    for col, default_val in defaults.items():
        if col not in df.columns:
            df[col] = default_val

    df["ssid"] = df["ssid"].fillna("").astype(str).str.strip().replace("", "<HIDDEN>")
    df["bssid"] = df["bssid"].fillna("00:00:00:00:00:00").astype(str)
    df["security"] = df["security"].fillna("UNKNOWN").astype(str).str.upper()
    df["rssi"] = pd.to_numeric(df["rssi"], errors="coerce").fillna(-90).astype(int)
    df["channel"] = pd.to_numeric(df["channel"], errors="coerce").fillna(1).astype(int)

    # Log-Distance Path Loss Model: d = 10 ^ ((A - RSSI) / (10 * n)), A = -40 dBm, n = 3.0
    df["estimated_distance_m"] = (10 ** ((-40 - df["rssi"]) / (10 * 3.0))).round(2)

    return df.sort_values(by="rssi", ascending=False).reset_index(drop=True)


class WiFiSerialReader:
    """Non-blocking USB Serial reader supporting ESP32 arrays and ESP8266 JSON lines."""

    def __init__(self, port: str = "COM5", baudrate: int = 115200, timeout: float = 0.5):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = None
        self._batch_buffer: list[dict] = []
        self._active_scan_id = None

    def connect(self) -> tuple[bool, str]:
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
            time.sleep(1.5)
            self.ser.reset_input_buffer()
            return True, f"Connected to {self.port} @ {self.baudrate} baud"
        except serial.SerialException as exc:
            return False, str(exc)

    def read_latest_scan(self) -> pd.DataFrame:
        """Drains incoming serial lines and returns the newest complete scan DataFrame."""
        if not self.ser or not self.ser.is_open:
            return pd.DataFrame()

        latest_df = pd.DataFrame()
        while self.ser.in_waiting > 0:
            raw_line = self.ser.readline().decode("utf-8", errors="ignore").strip()
            if not raw_line:
                continue
            try:
                payload = json.loads(raw_line)

                # Format A: ESP32 Gateway JSON array per complete scan batch
                if isinstance(payload, list) and len(payload) > 0:
                    latest_df = _enrich_dataframe(pd.DataFrame(payload))

                # Format B: ESP8266 Direct line-by-line JSON objects
                elif isinstance(payload, dict) and "ssid" in payload:
                    scan_id = payload.get("scan_id", 0)
                    total = payload.get("total", 1)
                    if scan_id != self._active_scan_id:
                        self._active_scan_id = scan_id
                        self._batch_buffer = []
                    self._batch_buffer.append(payload)
                    if len(self._batch_buffer) >= total:
                        latest_df = _enrich_dataframe(pd.DataFrame(self._batch_buffer))
                        self._batch_buffer = []
            except json.JSONDecodeError:
                # Ignore plain-text firmware boot logs (e.g., [GATEWAY]...)
                continue

        return latest_df

    def close(self) -> None:
        if self.ser and self.ser.is_open:
            self.ser.close()