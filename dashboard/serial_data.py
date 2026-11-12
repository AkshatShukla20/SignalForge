"""SignalForge data layer: serial I/O, parsing, mock generator, channel analytics."""

from __future__ import annotations

import json
import random
import threading
import time

import numpy as np
import pandas as pd
import serial
import serial.tools.list_ports

CHANNELS = list(range(1, 14))
RECOMMENDED_CANDIDATES = (1, 6, 11)  # the only non-overlapping 2.4 GHz trio
MAX_RX_BYTES = 262_144  # drop the buffer if a line never terminates (garbage on the wire)

# Firmware key aliases -> canonical column names.
_KEY_ALIASES = {
    "ch": "channel",
    "chan": "channel",
    "enc": "security",
    "encryption": "security",
    "auth": "security",
    "sec": "security",
    "name": "ssid",
    "mac": "bssid",
}

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


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------
def _normalize_record(rec) -> dict | None:
    """Lower-cases keys, applies aliases, and rejects records without rssi/channel."""
    if not isinstance(rec, dict):
        return None
    out = {}
    for key, value in rec.items():
        name = str(key).strip().lower()
        out[_KEY_ALIASES.get(name, name)] = value
    if "rssi" not in out or "channel" not in out:
        return None
    return out


def _enrich_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Validates columns, sanitizes SSID/BSSID, and computes path-loss distance.

    Records with no usable rssi/channel are dropped rather than filled with
    defaults, so a firmware key mismatch can never silently fake data.
    """
    if df.empty or not {"rssi", "channel"} <= set(df.columns):
        return pd.DataFrame()

    df = df.copy()
    for col, default in {"ssid": "", "bssid": "", "security": "UNKNOWN"}.items():
        if col not in df.columns:
            df[col] = default

    df["rssi"] = pd.to_numeric(df["rssi"], errors="coerce")
    df["channel"] = pd.to_numeric(df["channel"], errors="coerce")
    df = df.dropna(subset=["rssi", "channel"])
    df = df[(df["channel"] >= 1) & (df["channel"] <= 14)]
    if df.empty:
        return pd.DataFrame()

    df["rssi"] = df["rssi"].clip(-100, -1).astype(int)
    df["channel"] = df["channel"].astype(int)

    ssid = df["ssid"].fillna("").astype(str).str.strip()
    hidden = ssid.eq("") | ssid.str.upper().eq("<HIDDEN>")
    df["ssid"] = ssid.mask(hidden, "<HIDDEN>")
    df["hidden"] = hidden.astype(int)

    bssid = df["bssid"].fillna("").astype(str).str.strip().str.upper()
    fallback = "NOBSSID-" + df["ssid"] + "-" + df["channel"].astype(str)
    df["bssid"] = bssid.mask(bssid.eq(""), fallback)

    df["security"] = (
        df["security"]
        .fillna("UNKNOWN")
        .astype(str)
        .str.strip()
        .str.upper()
        .replace({"NONE": "OPEN", "": "UNKNOWN"})
    )

    # Unique, human-readable handle: mesh nodes share SSIDs, hidden APs have none.
    df["label"] = df["ssid"] + " (" + df["bssid"].str[-5:] + ")"

    # Log-Distance Path Loss Model: d = 10 ^ ((A - RSSI) / (10 * n)), A = -40 dBm, n = 3.0
    # Rough estimate only; RSSI is noisy indoors.
    df["estimated_distance_m"] = (10 ** ((-40 - df["rssi"]) / (10 * 3.0))).round(2)

    return df.sort_values(by="rssi", ascending=False).reset_index(drop=True)


def _build_scan(records: list) -> tuple[pd.DataFrame, int]:
    """Builds one scan DataFrame; returns (df, number_of_dropped_records)."""
    normalized = [r for r in (_normalize_record(x) for x in records) if r]
    if not normalized:
        return pd.DataFrame(), len(records)
    df = _enrich_dataframe(pd.DataFrame(normalized))
    return df, len(records) - len(df)


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
            }
        )
    return _enrich_dataframe(pd.DataFrame(rows))


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------
def channel_congestion(df: pd.DataFrame) -> pd.DataFrame:
    """Per-channel AP count and signal-weighted congestion for channels 1-13.

    2.4 GHz channels are 22 MHz wide but only 5 MHz apart, so an AP on channel 6
    also loads channels 2-10. Each AP contributes a weight (-95 dBm -> 0,
    -30 dBm -> 1) spread over neighbouring channels with a linear overlap factor.
    """
    channels = np.array(CHANNELS)
    score = np.zeros(len(channels))
    counts = np.zeros(len(channels), dtype=int)

    if not df.empty:
        for ap_ch, rssi in zip(df["channel"], df["rssi"]):
            weight = float(np.clip((rssi + 95) / 65, 0, 1))
            overlap = np.clip(1 - np.abs(channels - ap_ch) * 5 / 22, 0, 1)
            score += weight * overlap
            if 1 <= ap_ch <= 13:
                counts[ap_ch - 1] += 1

    return pd.DataFrame(
        {"channel": channels, "ap_count": counts, "congestion": score.round(2)}
    )


def recommend_channel(congestion: pd.DataFrame) -> int:
    """Least congested of the non-overlapping channels 1, 6 and 11."""
    candidates = congestion[congestion["channel"].isin(RECOMMENDED_CANDIDATES)]
    return int(candidates.loc[candidates["congestion"].idxmin(), "channel"])


# ---------------------------------------------------------------------------
# Serial reader
# ---------------------------------------------------------------------------
class WiFiSerialReader:
    """Non-blocking USB Serial reader supporting ESP32 arrays and ESP8266 JSON lines.

    Incoming bytes are buffered and only complete newline-terminated lines are
    parsed, so a read that lands mid-print never loses data. Safe to share
    between Streamlit sessions (guarded by a lock) and survives unplugging.
    """

    def __init__(self, flush_after: float = 1.5):
        self.ser: serial.Serial | None = None
        self.port: str | None = None
        self.baudrate: int | None = None
        self.flush_after = flush_after
        self._lock = threading.Lock()
        self._reset_state()

    # -- state -------------------------------------------------------------
    def _reset_state(self) -> None:
        self._rx = bytearray()
        self._batch: list[dict] = []
        self._batch_total: int | None = None
        self._active_scan_id = None
        self._last_line_time = 0.0
        self.error: str | None = None
        self.problem: str | None = None
        self.stats = {
            "lines": 0,
            "scans": 0,
            "dropped_records": 0,
            "incomplete_scans": 0,
            "ignored_lines": 0,
            "last_line": "",
            "last_ignored": "",
        }

    @property
    def is_open(self) -> bool:
        return self.ser is not None and self.ser.is_open

    # -- connection --------------------------------------------------------
    def connect(self, port: str, baudrate: int = 115200) -> tuple[bool, str]:
        with self._lock:
            self._close_locked()
            self._reset_state()
            try:
                self.ser = serial.Serial(port, baudrate, timeout=0)
            except (serial.SerialException, OSError, ValueError) as exc:
                self.ser = None
                self.error = str(exc)
                return False, str(exc)
            self.port, self.baudrate = port, baudrate
            time.sleep(1.5)  # ESP32 auto-resets when the port opens; let it boot
            try:
                self.ser.reset_input_buffer()
            except (serial.SerialException, OSError):
                pass
            return True, f"Connected to {port} @ {baudrate} baud"

    def close(self) -> None:
        with self._lock:
            self._close_locked()

    def _close_locked(self) -> None:
        if self.ser is not None:
            try:
                if self.ser.is_open:
                    self.ser.close()
            except (serial.SerialException, OSError):
                pass
        self.ser = None

    # -- reading -----------------------------------------------------------
    def read_latest_scan(self) -> pd.DataFrame:
        """Drains the port and returns the newest complete scan (empty if none)."""
        with self._lock:
            if not self.is_open:
                return pd.DataFrame()

            try:
                waiting = self.ser.in_waiting
                if waiting:
                    self._rx.extend(self.ser.read(waiting))
            except (serial.SerialException, OSError) as exc:
                self.error = f"Serial connection lost: {exc}"
                self._close_locked()
                return pd.DataFrame()

            completed: list[pd.DataFrame] = []

            while b"\n" in self._rx:
                line, _, rest = self._rx.partition(b"\n")
                self._rx = bytearray(rest)
                self._handle_line(line.decode("utf-8", errors="ignore").strip(), completed)

            if len(self._rx) > MAX_RX_BYTES:
                self._rx = bytearray()

            # Per-AP lines without a usable "total": flush once the stream goes quiet.
            if self._batch and time.monotonic() - self._last_line_time > self.flush_after:
                self._flush_batch(completed)

            return completed[-1] if completed else pd.DataFrame()

    def _handle_line(self, text: str, completed: list) -> None:
        if not text:
            return
        self.stats["lines"] += 1
        self.stats["last_line"] = text[:300]

        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            self._ignore(text)  # firmware boot logs such as [GATEWAY] ...
            return

        # Wrapped array, e.g. {"aps": [...]}
        if isinstance(payload, dict):
            for key in ("aps", "networks", "scan"):
                if isinstance(payload.get(key), list):
                    payload = payload[key]
                    break

        if isinstance(payload, list):
            # Format A: ESP32 gateway sends one JSON array per complete scan.
            if payload:
                self._emit(payload, completed)
        elif isinstance(payload, dict) and ("ssid" in payload or "bssid" in payload):
            # Format B: ESP8266 sends one JSON object per AP, grouped by scan_id/total.
            self._handle_ap_line(payload, completed)
        else:
            self._ignore(text)

    def _handle_ap_line(self, payload: dict, completed: list) -> None:
        scan_id = payload.get("scan_id")
        if self._batch and scan_id != self._active_scan_id:
            self._flush_batch(completed)  # new scan started; emit what we have
        self._active_scan_id = scan_id
        self._batch.append(payload)
        self._last_line_time = time.monotonic()

        try:
            self._batch_total = int(payload.get("total"))
        except (TypeError, ValueError):
            self._batch_total = None

        if self._batch_total and len(self._batch) >= self._batch_total:
            self._flush_batch(completed)

    def _flush_batch(self, completed: list) -> None:
        records, total = self._batch, self._batch_total
        self._batch, self._batch_total = [], None
        if total and len(records) < total:
            self.stats["incomplete_scans"] += 1
        self._emit(records, completed)

    def _emit(self, records: list, completed: list) -> None:
        df, dropped = _build_scan(records)
        if dropped:
            self.stats["dropped_records"] += dropped
            seen = sorted({str(k) for r in records if isinstance(r, dict) for k in r})
            self.problem = (
                f"{dropped} record(s) dropped: each needs 'rssi' and 'channel' "
                f"(aliases 'ch'/'chan' accepted). Keys seen in firmware output: {seen}"
            )
        elif not df.empty:
            self.problem = None
        if not df.empty:
            self.stats["scans"] += 1
            completed.append(df)

    def _ignore(self, text: str) -> None:
        self.stats["ignored_lines"] += 1
        self.stats["last_ignored"] = text[:300]

    # -- diagnostics -------------------------------------------------------
    def diagnostics(self) -> dict:
        with self._lock:
            return {
                "connected": self.is_open,
                "port": self.port,
                "baudrate": self.baudrate,
                "error": self.error,
                "problem": self.problem,
                **self.stats,
            }