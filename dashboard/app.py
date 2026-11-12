from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from serial_data import (
    WiFiSerialReader,
    channel_congestion,
    generate_mock_scan,
    list_serial_ports,
    recommend_channel,
)

HISTORY_WINDOW = timedelta(minutes=10)

st.set_page_config(
    page_title="SignalForge — 2.4 GHz Spectrum Analyzer",
    page_icon="📡",
    layout="wide",
)

st.title("📡 SignalForge — 2.4 GHz Wi-Fi Spectrum & Telemetry Dashboard")


@st.cache_resource
def get_reader() -> WiFiSerialReader:
    """One process-wide reader, so a browser refresh never orphans the open COM port."""
    return WiFiSerialReader()


reader = get_reader()

# --- Session State Initialization ---
if "latest_df" not in st.session_state:
    st.session_state.latest_df = pd.DataFrame()
if "scan_count" not in st.session_state:
    st.session_state.scan_count = 0
if "rssi_history" not in st.session_state:
    st.session_state.rssi_history = []
if "last_mode_mock" not in st.session_state:
    st.session_state.last_mode_mock = None


def clear_data() -> None:
    st.session_state.latest_df = pd.DataFrame()
    st.session_state.rssi_history = []
    st.session_state.scan_count = 0


# --- Sidebar Controls ---
with st.sidebar:
    st.header("Telemetry Source")
    use_mock = st.checkbox("Use Mock Mode (Offline Test)", value=True)

    selected_port = st.selectbox("Hardware COM Port", list_serial_ports(), disabled=use_mock)
    baudrate = st.selectbox("Baud Rate", [115200, 9600], index=0, disabled=use_mock)
    refresh_sec = st.slider("Refresh Interval (sec)", 1.0, 5.0, 2.0, 0.5)
    auto_stream = st.toggle("Live Stream", value=True)
    refresh_now = st.button("Refresh now", disabled=auto_stream)

    if not use_mock:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Connect"):
                ok, msg = reader.connect(selected_port, baudrate)
                clear_data()
                if ok:
                    st.success(msg)
                else:
                    st.error(f"Port Error: {msg}")
        with col2:
            if st.button("Disconnect"):
                reader.close()
                clear_data()
                st.info("Disconnected")
        if reader.is_open:
            st.caption(f"Connected: {reader.port} @ {reader.baudrate}")
        else:
            st.caption("Not connected")

    st.markdown("---")
    if st.button("Clear RSSI History"):
        st.session_state.rssi_history = []

# Switching between mock and hardware: close the port and drop the other source's data.
if st.session_state.last_mode_mock is not None and st.session_state.last_mode_mock != use_mock:
    reader.close()
    clear_data()
st.session_state.last_mode_mock = use_mock


# --- Data Acquisition ---
def record_history(df: pd.DataFrame) -> None:
    """Appends this scan to the rolling RSSI history (last 10 minutes)."""
    now = datetime.now()
    cutoff = now - HISTORY_WINDOW
    kept = [row for row in st.session_state.rssi_history if row["time"] >= cutoff]
    kept.extend(
        {"time": now, "bssid": bssid, "label": label, "rssi": rssi}
        for bssid, label, rssi in zip(df["bssid"], df["label"], df["rssi"])
    )
    st.session_state.rssi_history = kept


def acquire() -> None:
    if use_mock:
        df = generate_mock_scan()
    else:
        df = reader.read_latest_scan()
    if df.empty:
        return
    st.session_state.latest_df = df
    st.session_state.scan_count += 1
    record_history(df)


# Manual refresh runs here (outside the fragment) so a widget click inside the
# fragment never triggers a second acquisition.
if refresh_now and not auto_stream:
    acquire()


# --- Dashboard Visuals ---
def live_view() -> None:
    if auto_stream:
        acquire()

    df = st.session_state.latest_df

    if use_mock:
        st.caption("Source: Synthetic Mock Telemetry (uncheck 'Use Mock Mode' in the sidebar for live hardware)")
    else:
        diag = reader.diagnostics()
        if reader.error:
            st.error(reader.error)
        elif not reader.is_open:
            st.warning("Hardware mode active — select your COM port in the sidebar and click Connect.")
        else:
            st.caption(f"Source: Live Serial ({reader.port}) | Scans received: {diag['scans']}")
        if diag["problem"]:
            st.warning(diag["problem"])

    if df.empty:
        if use_mock or reader.is_open:
            st.info("Waiting for the first scan — turn on Live Stream or press Refresh now.")
        if not use_mock:
            with st.expander("Serial diagnostics"):
                st.json(reader.diagnostics())
        return

    cong = channel_congestion(df)

    # 1. Top KPI Metric Cards
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Detected APs", len(df))

    top = df.iloc[0]
    m2.metric("Strongest RSSI", f"{top['rssi']} dBm", top["ssid"], delta_color="off")

    busiest = cong.loc[cong["congestion"].idxmax()]
    m3.metric(
        "Most Congested Channel",
        f"Ch {int(busiest['channel'])}",
        f"{int(busiest['ap_count'])} APs on channel",
        delta_color="off",
    )

    rec = recommend_channel(cong)
    rec_row = cong[cong["channel"] == rec].iloc[0]
    m4.metric(
        "Suggested Channel",
        f"Ch {rec}",
        f"load {rec_row['congestion']:.1f} (best of 1/6/11)",
        delta_color="off",
    )

    open_nets = int((df["security"] == "OPEN").sum())
    m5.metric("Open / Unsecured APs", open_nets)

    st.markdown("---")

    # 2. Channel Congestion & Security Split Charts
    chart_left, chart_right = st.columns([3, 2])

    with chart_left:
        st.subheader("2.4 GHz Channel Congestion (Channels 1–13)")
        fig_ch = px.bar(
            cong,
            x="channel",
            y="congestion",
            color="congestion",
            color_continuous_scale="Turbo",
            hover_data={"ap_count": True},
            labels={
                "channel": "Wi-Fi Channel",
                "congestion": "Congestion Score",
                "ap_count": "APs on channel",
            },
        )
        fig_ch.update_xaxes(dtick=1)
        st.plotly_chart(fig_ch)
        st.caption(
            "Score weights each AP by signal strength and spreads it onto overlapping "
            "neighbour channels, so channel 6 traffic also loads channels 4–8."
        )

    with chart_right:
        st.subheader("Encryption / Security Split")
        sec_counts = df["security"].value_counts().reset_index()
        sec_counts.columns = ["security", "count"]
        fig_sec = px.pie(sec_counts, names="security", values="count", hole=0.45)
        st.plotly_chart(fig_sec)

    # 3. Live RSSI Time-Series Tracker (per BSSID, so mesh nodes and hidden APs stay separate)
    st.subheader("Live RSSI Signal Strength Tracker")
    labels = dict(zip(df["bssid"], df["label"]))
    options = sorted(labels, key=lambda b: labels[b])
    selected_bssid = st.selectbox(
        "Select access point to track",
        options,
        format_func=lambda b: labels.get(b, b),
        key="track_bssid",
    )

    if st.session_state.rssi_history:
        hist_df = pd.DataFrame(st.session_state.rssi_history)
        target_hist = hist_df[hist_df["bssid"] == selected_bssid]
        if len(target_hist) > 1:
            fig_rssi = px.line(
                target_hist,
                x="time",
                y="rssi",
                markers=True,
                labels={"time": "Time", "rssi": "Signal Strength (dBm)"},
                range_y=[-100, -25],
            )
            st.plotly_chart(fig_rssi)
        else:
            st.caption("Collecting samples for this access point…")

    # 4. Live Access Point Telemetry Table
    st.subheader("Live Access Point Telemetry")
    st.dataframe(
        df[["ssid", "bssid", "rssi", "channel", "security", "estimated_distance_m"]],
        hide_index=True,
    )

    if not use_mock:
        with st.expander("Serial diagnostics"):
            st.json(reader.diagnostics())


live_fragment = st.fragment(run_every=refresh_sec if auto_stream else None)(live_view)
live_fragment()