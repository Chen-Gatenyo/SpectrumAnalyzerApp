import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import os
import datetime
import sys
from streamlit_autorefresh import st_autorefresh
from SpectrumAnalyzer import SpectrumAnalyzer

# -------- Resource helper -------- #
def resource_path(rel_path: str) -> str:
    """Return absolute path to resource (dev & PyInstaller)."""
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel_path)

# -------- Helpers -------- #
def format_result(val, unit=None):
    try:
        if val is None or str(val).strip() == '' or str(val).lower() == 'none':
            return "N/A"
        f = float(val)
        if abs(f) >= 1e4 or (abs(f) < 1e-2 and f != 0):
            s = f"{f:.3e}"
        else:
            s = f"{f:.3f}".rstrip('0').rstrip('.')
        return f"{s} {unit}" if unit else s
    except Exception:
        return "N/A"

def log_debug(msg: str):
    if st.session_state.get("debug_on", False):
        st.write(f":mag_right: **[DEBUG]** {msg}")

def section_divider():
    st.markdown('<hr class="section-hr">', unsafe_allow_html=True)

# -------- Page & CSS -------- #
st.set_page_config(page_title="Spectrum Analyzer App",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
/* Wider (but still compact) widget boxes */
div[data-testid="stNumberInput"],
div[data-testid="stTextInput"],
div[data-testid="stSelectbox"],
div[data-testid="stDateInput"],
div[data-testid="stTimeInput"]{
    max-width: 170px !important;
}
div[data-testid="stNumberInput"] input,
div[data-testid="stTextInput"] input{
    width: 100% !important;
    font-size: 0.9rem !important;
}

/* Buttons */
.small-btn button{
    padding:4px 10px !important;
    font-size:0.8rem !important;
    line-height:1.1 !important;
}
.stop-btn button{
    background-color:#d9534f !important;
    color:#ffffff !important;
}
.small-dl button{
    padding:4px 10px !important;
    font-size:0.8rem !important;
    line-height:1.1 !important;
}

/* Alerts */
div.stAlert{ padding:6px 10px !important; }

/* Title */
.modern-title{
    font-family:'Segoe UI', Roboto, sans-serif;
    font-size:3rem;
    font-weight:800;
    background:linear-gradient(90deg,#00bcd4,#673ab7);
    -webkit-background-clip:text;
    -webkit-text-fill-color:transparent;
    margin:0 0 0.6rem 0;
}

/* Thick divider */
.section-hr{
    border:0;
    border-top:6px solid #444;
    margin:22px 0 18px 0;
}
h3{ margin-top:0.6rem; }
</style>
""", unsafe_allow_html=True)

# -------- Session defaults -------- #
defaults = {
    'analyzer': None,
    'connected': False,
    'address': "TCPIP0::192.168.1.75::inst0::INSTR",
    'last_address': None,
    'sidebar_collapsed': False,
    'debug_on': False,
    'last_img_bytes': None,
    'last_img_name': None,
    'auto_capture': False,
    'auto_interval_ms': 10000,
    'live_trace_on': False,
    'lt_interval_ms': 1000,
    'auto_connect_done': False,
}
for k, v in defaults.items():
    st.session_state.setdefault(k, v)

# Auto refreshers
if st.session_state['auto_capture']:
    st_autorefresh(interval=st.session_state['auto_interval_ms'], key="auto_cap_tick")
if st.session_state['live_trace_on']:
    st_autorefresh(interval=st.session_state['lt_interval_ms'], key="lt_tick")

# -------- Sidebar -------- #
st.sidebar.title("Spectrum Analyzer")
st.sidebar.markdown("Control and monitor your Keysight N9020B Spectrum Analyzer.")
st.session_state.debug_on = st.sidebar.checkbox("Show debug prints", value=False, key="chk_debug")

address = st.sidebar.text_input("Resource Address",
                                st.session_state['address'],
                                key="addr_input")

def try_connect(addr: str):
    with st.spinner(f"Connecting to Spectrum Analyzer at {addr}..."):
        analyzer = SpectrumAnalyzer(resource_address=addr, timeout=5000)
        if analyzer.connect():
            st.session_state['analyzer'] = analyzer
            st.session_state['connected'] = True
            st.session_state['address'] = addr
            st.session_state['last_address'] = addr
            log_debug("Connection successful.")
            if not st.session_state.get("sidebar_collapsed", False):
                st.markdown(
                    """
                    <script>
                    setTimeout(function(){
                        let sb = window.parent.document.querySelector('section[data-testid="stSidebar"]');
                        if (sb){
                            let btn = sb.querySelector('button[title="Close sidebar"]') ||
                                      sb.querySelector('button[aria-label="collapse"]');
                            if (btn){ btn.click(); }
                        }
                    },500);
                    </script>
                    """, unsafe_allow_html=True
                )
                st.session_state['sidebar_collapsed'] = True
        else:
            st.session_state['analyzer'] = None
            st.session_state['connected'] = False
            st.sidebar.error("Connection failed.")
            log_debug("Connection failed – check VISA address / network.")

def connect_toggle():
    if st.session_state['connected']:
        with st.spinner("Disconnecting..."):
            if st.session_state['analyzer']:
                st.session_state['analyzer'].disconnect()
            st.session_state['connected'] = False
            st.session_state['analyzer'] = None
            log_debug("Disconnected by user.")
    else:
        try_connect(address)

# Auto connect FIRST TIME only
if (not st.session_state['connected']) and (not st.session_state['auto_connect_done']):
    st.session_state['auto_connect_done'] = True
    try_connect(address)

# Toggle button
if st.session_state['connected']:
    st.markdown('<div class="small-btn stop-btn">', unsafe_allow_html=True)
    if st.sidebar.button("Disconnect", use_container_width=True, key="btn_connect_toggle"):
        connect_toggle()
        st.experimental_rerun()
    st.markdown("</div>", unsafe_allow_html=True)
else:
    st.markdown('<div class="small-btn">', unsafe_allow_html=True)
    if st.sidebar.button("Connect", use_container_width=True, key="btn_connect_toggle"):
        connect_toggle()
        st.experimental_rerun()
    st.markdown("</div>", unsafe_allow_html=True)

st.sidebar.markdown("---")

# -------- Header -------- #
col_logo, col_title = st.columns([1,5])
with col_logo:
    logo_path = resource_path("logo.png")
    if os.path.exists(logo_path):
        st.image(logo_path, width=220)
with col_title:
    st.markdown('<div class="modern-title">Spectrum Analyzer App</div>', unsafe_allow_html=True)

st.markdown("Use the sidebar to connect and configure the instrument. Controls and measurements are below.")

if not st.session_state['connected']:
    st.info(":arrow_left: Click **Connect** in the sidebar to begin.")
    st.stop()

analyzer: SpectrumAnalyzer = st.session_state['analyzer']

# =========================================================
# ⚙️ Controls & Advanced
# =========================================================
st.header("⚙️ Controls & Advanced")

# --- Basic Controls ---
st.subheader("Basic Controls")
bc1, bc2, bc3, bc4 = st.columns(4)

with bc1:
    cf_val = float(analyzer.get_center_frequency() or 1e9)
    center_freq = st.number_input("Center Frequency (Hz)", 1e3, 40e9, cf_val, 1e6,
                                  format="%.0f", key="num_cf")
    if st.button("Set CF", key="btn_set_cf"):
        with st.spinner("Setting center frequency..."):
            analyzer.set_center_frequency(center_freq)
            st.success(f"CF set to {center_freq:.0f} Hz")
            log_debug(f"CF set → {center_freq}")

with bc2:
    span_val = float(analyzer.get_span() or 10e6)
    span = st.number_input("Span (Hz)", 1e3, 40e9, span_val, 1e6,
                           format="%.0f", key="num_span")
    if st.button("Set Span", key="btn_set_span"):
        with st.spinner("Setting span..."):
            analyzer.set_span(span)
            st.success(f"Span set to {span:.0f} Hz")
            log_debug(f"Span set → {span}")

with bc3:
    rbw_val = float(analyzer.get_rbw() or 1e3)
    rbw = st.number_input("RBW (Hz)", 1.0, 10e6, rbw_val, 1e2,
                          format="%.0f", key="num_rbw")
    if st.button("Set RBW", key="btn_set_rbw"):
        with st.spinner("Setting RBW..."):
            analyzer.set_rbw(rbw)
            st.success(f"RBW set to {rbw:.0f} Hz")
            log_debug(f"RBW set → {rbw}")

with bc4:
    ref_val = float(analyzer.get_ref_level() or 0)
    ref_level = st.number_input("Ref Level (dBm)", -100.0, 30.0, ref_val, 1.0,
                                format="%.1f", key="num_ref")
    if st.button("Set Ref", key="btn_set_ref"):
        with st.spinner("Setting reference level..."):
            analyzer.set_ref_level(ref_level)
            st.success(f"Ref set to {ref_level:.1f} dBm")
            log_debug(f"Ref set → {ref_level}")

# --- Advanced Actions ---
st.subheader("Advanced Actions")
aa1, aa2 = st.columns(2)
with aa1:
    if st.button("SA Mode", key="btn_sa_mode"):
        with st.spinner("Setting Spectrum Analyzer mode..."):
            try:
                analyzer.set_sanalyzer()
                st.success("Spectrum Analyzer mode set!")
                log_debug("set_sanalyzer() executed.")
            except Exception as e:
                st.error(f"Error: {e}")
                log_debug(f"set_sanalyzer error: {e}")

with aa2:
    if st.button("Trace Average", key="btn_trace_avg"):
        with st.spinner("Setting trace average..."):
            try:
                analyzer.set_trace_average()
                st.success("Trace average set!")
                log_debug("set_trace_average() executed.")
            except Exception as e:
                st.error(f"Error: {e}")
                log_debug(f"set_trace_average error: {e}")

# --- Quick Reads ---
st.subheader("Quick Reads")
qr1, qr2 = st.columns(2)
with qr1:
    if st.button("Get CF", key="btn_qr_cf"):
        with st.spinner("Reading CF..."):
            try:
                cf = analyzer.get_center_frequency()
                st.info(f"CF: {format_result(cf, 'Hz')}")
                log_debug(f"CF read: {cf}")
            except Exception as e:
                st.error(f"Error: {e}")
                log_debug(f"Get CF error: {e}")

    if st.button("Get Span", key="btn_qr_span"):
        with st.spinner("Reading span..."):
            try:
                span_r = analyzer.get_span()
                st.info(f"Span: {format_result(span_r, 'Hz')}")
                log_debug(f"Span read: {span_r}")
            except Exception as e:
                st.error(f"Error: {e}")
                log_debug(f"Get span error: {e}")

with qr2:
    if st.button("Get RBW", key="btn_qr_rbw"):
        with st.spinner("Reading RBW..."):
            try:
                rbw_r = analyzer.get_rbw()
                st.info(f"RBW: {format_result(rbw_r, 'Hz')}")
                log_debug(f"RBW read: {rbw_r}")
            except Exception as e:
                st.error(f"Error: {e}")
                log_debug(f"Get RBW error: {e}")

    if st.button("Get Ref", key="btn_qr_ref"):
        with st.spinner("Reading ref level..."):
            try:
                ref_r = analyzer.get_ref_level()
                st.info(f"Ref: {format_result(ref_r, 'dBm')}")
                log_debug(f"Ref level read: {ref_r}")
            except Exception as e:
                st.error(f"Error: {e}")
                log_debug(f"Get Ref error: {e}")

section_divider()

# =========================================================
# 📊 Measurements
# =========================================================
st.header("📊 Measurements")

# Row 1: Peaks & Band Power
r1c1, r1c2 = st.columns(2)

with r1c1:
    st.subheader("Peaks")
    colp1, colp2 = st.columns(2)
    with colp1:
        if st.button("High Peak", key="btn_high_peak"):
            with st.spinner("Measuring high peak..."):
                try:
                    peak = analyzer.get_current_high_peak()
                    st.success(f"High Peak: {format_result(peak, 'dBm')}")
                    log_debug(f"High peak measured: {peak}")
                except Exception as e:
                    st.error(f"Error: {e}")
                    log_debug(f"High peak error: {e}")
    with colp2:
        if st.button("Low Peak", key="btn_low_peak"):
            with st.spinner("Measuring low peak..."):
                try:
                    low_peak = analyzer.get_current_low_peak()
                    st.success(f"Low Peak: {format_result(low_peak, 'dBm')}")
                    log_debug(f"Low peak measured: {low_peak}")
                except Exception as e:
                    st.error(f"Error: {e}")
                    log_debug(f"Low peak error: {e}")

with r1c2:
    st.subheader("Band Power")
    band_span = st.number_input("Band Power Span (Hz)", 1e3, 40e6, 1e6, 1e5,
                                format="%.0f", key="num_band_span")
    if st.button("Measure Band Power", key="btn_band_power"):
        with st.spinner("Measuring band power..."):
            try:
                power = analyzer.get_band_power(band_span)
                st.success(f"Band Power: {format_result(power, 'dBm')}")
                log_debug(f"Band power ({band_span} Hz): {power}")
            except Exception as e:
                st.error(f"Error: {e}")
                log_debug(f"Band power error: {e}")

# Row 2: OBW & Readbacks
r2c1, r2c2 = st.columns([2, 1])

with r2c1:
    st.subheader("Occupied Bandwidth (OBW)")
    obw_col1, obw_col2, obw_col3 = st.columns(3)
    obw_sr = obw_col1.number_input("Symbol Rate (Ksps)", 1.0, 100000.0, 1000.0, 100.0,
                                   format="%.1f", key="num_obw_sr")
    obw_sf = obw_col2.number_input("Spread Factor", 1.0, 20.0, 7.0, 1.0,
                                   format="%.0f", key="num_obw_sf")
    obw_ro = obw_col3.number_input("Roll-off", 0.0, 1.0, 0.35, 0.01,
                                   format="%.2f", key="num_obw_ro")
    if st.button("Get OBW", key="btn_obw"):
        with st.spinner("Measuring occupied bandwidth..."):
            try:
                obw = analyzer.read_obwidth(obw_sr, obw_sf, obw_ro)
                obw_val = obw.split(",")[0] if obw else obw
                st.success(f"Occupied Bandwidth: {format_result(obw_val, 'Hz')}")
                log_debug(f"OBW result raw: {obw}")
            except Exception as e:
                st.error(f"Error: {e}")
                log_debug(f"OBW error: {e}")

with r2c2:
    st.subheader("Read Back Params")
    rb1, rb2 = st.columns(2)
    with rb1:
        if st.button("Get CF (RB)", key="btn_read_cf"):
            with st.spinner("Reading CF..."):
                try:
                    cf = analyzer.get_center_frequency()
                    st.info(f"CF: {format_result(cf, 'Hz')}")
                    log_debug(f"CF read: {cf}")
                except Exception as e:
                    st.error(f"Error: {e}")
                    log_debug(f"Get CF error: {e}")

        if st.button("Get RBW (RB)", key="btn_read_rbw"):
            with st.spinner("Reading RBW..."):
                try:
                    rbw_r = analyzer.get_rbw()
                    st.info(f"RBW: {format_result(rbw_r, 'Hz')}")
                    log_debug(f"RBW read: {rbw_r}")
                except Exception as e:
                    st.error(f"Error: {e}")
                    log_debug(f"Get RBW error: {e}")

    with rb2:
        if st.button("Get Span (RB)", key="btn_read_span"):
            with st.spinner("Reading span..."):
                try:
                    span_r = analyzer.get_span()
                    st.info(f"Span: {format_result(span_r, 'Hz')}")
                    log_debug(f"Span read: {span_r}")
                except Exception as e:
                    st.error(f"Error: {e}")
                    log_debug(f"Get span error: {e}")

        if st.button("Get Ref (RB)", key="btn_read_ref"):
            with st.spinner("Reading ref level..."):
                try:
                    ref_r = analyzer.get_ref_level()
                    st.info(f"Ref: {format_result(ref_r, 'dBm')}")
                    log_debug(f"Ref level read: {ref_r}")
                except Exception as e:
                    st.error(f"Error: {e}")
                    log_debug(f"Get Ref error: {e}")

section_divider()

# =========================================================
# 📡 Spectrum Trace
# =========================================================
st.header("📡 Spectrum Trace")

lt_c1, lt_c2, lt_c3 = st.columns([1,1,1])

with lt_c1:
    if st.session_state['live_trace_on']:
        st.markdown('<div class="small-btn stop-btn">', unsafe_allow_html=True)
        lt_toggle = st.button("STOP Live Trace", key="btn_lt_toggle")
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="small-btn">', unsafe_allow_html=True)
        lt_toggle = st.button("START Live Trace", key="btn_lt_toggle")
        st.markdown('</div>', unsafe_allow_html=True)

with lt_c2:
    st.session_state['lt_interval_ms'] = st.number_input("Interval (ms)", 200, 10000,
                                                          st.session_state['lt_interval_ms'], 100,
                                                          key="num_lt_interval")

with lt_c3:
    fetch_once = st.button("Fetch Trace Once", key="btn_trace_once")

def show_trace():
    try:
        freqs, trace = analyzer.fetch_trace("TRACE1")
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(freqs, trace, linewidth=1.2)
        ax.set_xlabel("Frequency (Hz)")
        ax.set_ylabel("Amplitude (dBm)")
        title = "Spectrum Trace"
        if st.session_state['live_trace_on']:
            title += " (LIVE)"
        ax.set_title(title)
        ax.grid(True, alpha=0.3)
        st.pyplot(fig)

        if (not st.session_state['live_trace_on'] and
                st.checkbox("Enable CSV download", key="chk_trace_csv")):
            import pandas as pd
            df = pd.DataFrame({"Frequency_Hz": freqs, "Amplitude_dBm": trace})
            csv_bytes = df.to_csv(index=False).encode()
            st.download_button("Download Trace CSV", csv_bytes,
                               "spectrum_trace.csv", "text/csv",
                               key="btn_trace_csv")
    except Exception as e:
        st.error(f"Error fetching trace: {e}")
        log_debug(f"Trace error: {e}")

if lt_toggle:
    st.session_state['live_trace_on'] = not st.session_state['live_trace_on']
    st.rerun()

if st.session_state['live_trace_on'] or fetch_once:
    show_trace()

section_divider()

# =========================================================
# 📷 Instrument Screenshot
# =========================================================
st.header("📷 Instrument Screenshot")

cap_cols = st.columns([1, 1, 1])

with cap_cols[0]:
    interval_sec = st.number_input("Interval (s)", 1, 3600,
                                   int(st.session_state['auto_interval_ms'] / 1000),
                                   1, key="num_interval")
    if interval_sec * 1000 != st.session_state['auto_interval_ms']:
        st.session_state['auto_interval_ms'] = interval_sec * 1000
        if st.session_state['auto_capture']:
            st.rerun()

with cap_cols[1]:
    if st.session_state['auto_capture']:
        st.markdown('<div class="small-btn stop-btn">', unsafe_allow_html=True)
        toggle_clicked = st.button("STOP Auto Capture", key="btn_toggle_auto")
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="small-btn">', unsafe_allow_html=True)
        toggle_clicked = st.button("START Auto Capture", key="btn_toggle_auto")
        st.markdown('</div>', unsafe_allow_html=True)

with cap_cols[2]:
    st.markdown('<div class="small-btn">', unsafe_allow_html=True)
    capture_clicked = st.button("Capture Screen", key="btn_capture_once")
    st.markdown('</div>', unsafe_allow_html=True)

toast_placeholder = st.empty()

def do_capture():
    try:
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        screenshot_path = f"screenshot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        local_file, remote_path = analyzer.capture_screen(screenshot_path)
        log_debug(f"capture_screen returned local='{local_file}', remote='{remote_path}'")

        if local_file and os.path.exists(local_file):
            with open(local_file, "rb") as f:
                img_bytes = f.read()
            st.session_state["last_img_bytes"] = img_bytes
            st.session_state["last_img_name"] = os.path.basename(local_file)

            toast_placeholder.markdown(
                f"""
                <div style="text-align:right; font-size:0.8rem; color:#36a300; font-weight:600;">
                    Screenshot captured! <span style="opacity:0.7;">[{now_str}]</span>
                </div>
                """,
                unsafe_allow_html=True
            )

            try:
                os.remove(local_file)
                log_debug(f"Local screenshot deleted: {local_file}")
            except Exception as e:
                log_debug(f"Local delete failed: {e}")
            try:
                if remote_path:
                    analyzer.delete_remote_file(remote_path)
                    log_debug(f"Remote screenshot deleted: {remote_path}")
            except Exception as e:
                log_debug(f"Remote delete failed: {e}")
        else:
            st.warning("Failed to capture screenshot or no image returned.")
            log_debug("capture_screen failed or file missing.")
    except Exception as ex:
        st.error(f"Error capturing screen: {ex}")
        log_debug(f"Capture screen error: {ex}")

if toggle_clicked:
    st.session_state['auto_capture'] = not st.session_state['auto_capture']
    st.rerun()

if capture_clicked:
    with st.spinner("Capturing screen..."):
        do_capture()

if st.session_state['auto_capture'] and not capture_clicked and not toggle_clicked:
    do_capture()

if st.session_state["last_img_bytes"] is not None:
    st.markdown('<div class="small-dl">', unsafe_allow_html=True)
    st.download_button(
        label="Download Screenshot",
        data=st.session_state["last_img_bytes"],
        file_name=st.session_state["last_img_name"],
        mime="image/png",
        key=f"btn_dl_{st.session_state['last_img_name']}"
    )
    st.markdown('</div>', unsafe_allow_html=True)

    st.image(
        st.session_state["last_img_bytes"],
        caption=st.session_state["last_img_name"],
        use_container_width=True
    )

section_divider()

st.markdown("👑 chen is the king! 👑")
