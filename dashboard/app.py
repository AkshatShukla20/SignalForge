from datetime import datetime
import time
import pandas as pd
import plotly.express as px
import streamlit as st
from serial_data import WiFiSerialReader, generate_mock_scan, list_serial_ports

st.set_page_config(
    page_title="SignalForge — 2.4 GHz Spectrum Analyzer",
    page_icon="📡",
    layout="wide",
)

st.title("📡 SignalForge — 2.4 GHz Wi-Fi Spectrum & Telemetry Dashboard")

# --- Session State Initialization ---
if "reader" not in st.session_state:
    st.session_state.reader = None
if "connected" not in st.session_state:
    st.session_state.connected = False
if "latest_df" not in st.session_state:
    st.session_state.latest_df = pd.DataFrame()
if "scan_count" not in st.session_state:
    st.session_state.scan_count = 0
if "rssi_history" not in st.session_state:
    st.session_state.rssi_history = []

# --- Sidebar Controls ---
with st.sidebar:
    st.header("Telemetry Source")
    use_mock = st.checkbox("Use Mock Mode (Offline Test)", value=True)

    available_ports = list_serial_ports()
    selected_port = st.selectbox("Hardware COM Port", available_ports)
    baudrate = st.selectbox("Baud Rate", [115200, 9600], index=0)
    refresh_sec = st.slider("Refresh Interval (sec)", 1.0, 5.0, 2.0, 0.5)
    auto_stream = st.toggle("Live Stream", value=True)

    if not use_mock:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Connect"):
                if st.session_state.reader:
                    st.session_state.reader.close()
                reader = WiFiSerialReader(port=selected_port, baudrate=baudrate)
                ok, msg = reader.connect()
                if ok:
                    st.session_state.reader = reader
                    st.session_state.connected = True
                    st.success(msg)
                else:
                    st.session_state.connected = False
                    st.error(f"Port Error: {msg}")
        with col2:
            if st.button("Disconnect"):
                if st.session_state.reader:
                    st.session_state.reader.close()
                st.session_state.connected = False
                st.info("Disconnected")

    st.markdown("---")
    if st.button("Clear RSSI History"):
        st.session_state.rssi_history = []

# --- Data Acquisition ---
new_batch_received = False

if use_mock:
    st.session_state.latest_df = generate_mock_scan()
    st.session_state.scan_count += 1
    new_batch_received = True
    st.caption("Source: Synthetic Mock Telemetry (Uncheck 'Use Mock Mode' in sidebar for live hardware)")
elif st.session_state.connected and st.session_state.reader:
    new_df = st.session_state.reader.read_latest_scan()
    if not new_df.empty:
        st.session_state.latest_df = new_df
        st.session_state.scan_count += 1
        new_batch_received = True
    st.caption(f"Source: Live Serial ({selected_port}) | Batches Received: {st.session_state.scan_count}")
else:
    st.warning("Hardware mode active — select your COM port in the sidebar and click Connect.")

df = st.session_state.latest_df

# Record rolling RSSI history (last 30 batches) for time-series tracking
if new_batch_received and not df.empty:
    ts = datetime.now().strftime("%H:%M:%S")
    for _, row in df.iterrows():
        st.session_state.rssi_history.append(
            {"time": ts, "ssid": row["ssid"], "bssid": row["bssid"], "rssi": row["rssi"]}
        )
    max_entries = 30 * max(len(df), 10)
    if len(st.session_state.rssi_history) > max_entries:
        st.session_state.rssi_history = st.session_state.rssi_history[-max_entries:]

# --- Dashboard Visuals ---
if not df.empty:
    # 1. Top KPI Metric Cards
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Detected APs", len(df))
    m2.metric("Strongest RSSI", f"{df['rssi'].max()} dBm", df.iloc[0]["ssid"])

    busiest_ch = int(df["channel"].mode()[0])
    busiest_count = int((df["channel"] == busiest_ch).sum())
    m3.metric("Most Crowded Channel", f"Ch {busiest_ch}", f"{busiest_count} APs")

    open_nets = int((df["security"].str.upper() == "OPEN").sum())
    m4.metric("Open / Unsecured APs", open_nets)

    st.markdown("---")

    # 2. Channel Congestion & Security Split Charts
    chart_left, chart_right = st.columns([3, 2])

    with chart_left:
        st.subheader("2.4 GHz Channel Congestion (Channels 1–13)")
        ch_counts = (
            df.groupby("channel")
            .size()
            .reindex(range(1, 14), fill_value=0)
            .reset_index(name="ap_count")
        )
        fig_ch = px.bar(
            ch_counts,
            x="channel",
            y="ap_count",
            labels={"channel": "Wi-Fi Channel", "ap_count": "Access Points"},
            color="ap_count",
            color_continuous_scale="Turbo",
        )
        fig_ch.update_xaxes(dtick=1)
        st.plotly_chart(fig_ch)

    with chart_right:
        st.subheader("Encryption / Security Split")
        sec_counts = df["security"].value_counts().reset_index()
        sec_counts.columns = ["security", "count"]
        fig_sec = px.pie(sec_counts, names="security", values="count", hole=0.45)
        st.plotly_chart(fig_sec)

    # 3. Live RSSI Time-Series Tracker
    st.subheader("Live RSSI Signal Strength Tracker")
    ssid_options = df["ssid"].unique().tolist()
    selected_ssid = st.selectbox("Select Target SSID to Track", ssid_options)

    if st.session_state.rssi_history:
        hist_df = pd.DataFrame(st.session_state.rssi_history)
        target_hist = hist_df[hist_df["ssid"] == selected_ssid]
        if not target_hist.empty:
            fig_rssi = px.line(
                target_hist,
                x="time",
                y="rssi",
                color="bssid",
                markers=True,
                labels={"time": "Timestamp", "rssi": "Signal Strength (dBm)", "bssid": "BSSID"},
                range_y=[-100, -25],
            )
            st.plotly_chart(fig_rssi)

    # 4. Live Access Point Telemetry Table
    st.subheader("Live Access Point Telemetry")
    st.dataframe(
        df[["ssid", "bssid", "rssi", "channel", "security", "estimated_distance_m"]],
        hide_index=True,
    )

if auto_stream:
    time.sleep(refresh_sec)
    st.rerun()