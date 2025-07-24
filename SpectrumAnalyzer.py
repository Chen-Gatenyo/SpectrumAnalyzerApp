import pyvisa
import time
import datetime
import os
import numpy as np


class SpectrumAnalyzer:
    """
    Keysight N9020B Spectrum Analyzer wrapper.
    - VISA connect/disconnect
    - SCPI write/query helpers (incl. binary)
    - Basic getters/setters
    - Measurements (peaks, band power, OBW)
    - fetch_trace(): real spectrum data
    - capture_screen(): grab PNG via IEEE block
    """

    def __init__(self,
                 resource_address: str = "TCPIP0::192.168.1.75::inst0::INSTR",
                 timeout: int = 5000):
        self.resource_address = resource_address
        self.timeout = timeout
        self.rm = None
        self.sa = None

    # ---------- VISA ---------- #
    def connect(self) -> bool:
        try:
            self.rm = pyvisa.ResourceManager()
            self.sa = self.rm.open_resource(self.resource_address)
            self.sa.timeout = self.timeout
            print(f"[SpectrumAnalyzer] Connected to {self.resource_address}")
            return True
        except Exception as e:
            print(f"[SpectrumAnalyzer] ERROR connecting: {e}")
            self.sa = None
            return False

    def disconnect(self) -> None:
        try:
            if self.sa:
                self.sa.close()
            if self.rm:
                self.rm.close()
            print("[SpectrumAnalyzer] Disconnected")
        except Exception as e:
            print(f"[SpectrumAnalyzer] ERROR while disconnecting: {e}")

    # ---------- Low-level ---------- #
    def write(self, cmd: str) -> None:
        if not self.sa:
            raise ValueError("Analyzer not connected")
        print(f"[SA.write]  >> {cmd}")
        self.sa.write(cmd)

    def query(self, cmd: str) -> str:
        if not self.sa:
            raise ValueError("Analyzer not connected")
        print(f"[SA.query]  >> {cmd}")
        resp = self.sa.query(cmd).strip()
        print(f"[SA.query]  << {resp}")
        return resp

    def query_binary_values(self, cmd: str, **kwargs):
        if not self.sa:
            raise ValueError("Analyzer not connected")
        print(f"[SA.qbin]   >> {cmd}")
        return self.sa.query_binary_values(cmd, **kwargs)

    def wait_for_opc(self) -> None:
        _ = self.query("*OPC?")

    # ---------- Controls ---------- #
    def set_center_frequency(self, freq_hz: float) -> None:
        self.write(f"FREQ:CENT {freq_hz} Hz")

    def get_center_frequency(self) -> str:
        return self.query("FREQ:CENT?")

    def set_span(self, span_hz: float) -> None:
        self.write(f"FREQ:SPAN {span_hz} Hz")

    def get_span(self) -> str:
        return self.query("FREQ:SPAN?")

    def set_rbw(self, rbw_hz: float) -> None:
        self.write(f"BAND {rbw_hz} Hz")

    def get_rbw(self) -> str:
        return self.query("BAND?")

    def set_ref_level(self, ref_dbm: float) -> None:
        self.write(f"DISP:WIND:TRACE:Y:SCAL:RLEV {ref_dbm} dBm")

    def get_ref_level(self) -> str:
        return self.query("DISP:WIND:TRACE:Y:SCAL:RLEV?")

    # ---------- Measurements ---------- #
    def get_current_high_peak(self) -> str | None:
        try:
            self.write("CALC:MARK:MAX")
            return self.query("CALC:MARK:Y?")
        except Exception as e:
            print(f"[SpectrumAnalyzer] ERROR high-peak: {e}")
            return None

    def get_current_low_peak(self) -> str | None:
        try:
            self.write("CALC:MARK:MIN")
            return self.query("CALC:MARK:Y?")
        except Exception as e:
            print(f"[SpectrumAnalyzer] ERROR low-peak: {e}")
            return None

    def get_band_power(self, band_span_hz: float) -> str | None:
        if not self.sa:
            raise ValueError("Analyzer not connected")
        old_timeout = self.sa.timeout
        self.sa.timeout = 10000
        try:
            self.write("CALC:MARK1:STAT ON")
            time.sleep(0.5)
            self.write("CALC:MARK1:FUNC:BAND ON")
            time.sleep(0.5)
            status = self.query("CALC:MARK1:FUNC?")
            print(f"[band_power] Marker func status = {status}")
            self.write(f"CALC:MARK1:FUNC:BAND:SPAN {band_span_hz}")
            span_rb = self.query("CALC:MARK1:FUNC:BAND:SPAN?")
            print(f"[band_power] Span set→ {span_rb}")
            try:
                _ = self.query("CALC:MARK:FUNC BPOW")
            except Exception as e:
                print(f"[band_power] Warning: timeout on BPOW select ({e}) – continuing")
            power = self.query("CALC:MARK1:Y?")
            print(f"[band_power] Measured power = {power}")
            return power
        except Exception as e:
            print(f"[SpectrumAnalyzer] ERROR band-power: {e}")
            return None
        finally:
            self.sa.timeout = old_timeout

    def read_obwidth(self,
                     ob_symbol_rate: float = None,
                     ob_spread_factor: int = None,
                     ob_tx_roll_off: float = None) -> str | None:
        try:
            if None in (ob_symbol_rate, ob_spread_factor, ob_tx_roll_off):
                span_hz = 10e6
                print("[OBWidth] Using default 10 MHz span")
            else:
                span_hz = (ob_symbol_rate * 1e3 *
                           ob_spread_factor *
                           (1 + ob_tx_roll_off) * 2)
                print(f"[OBWidth] Adaptive span = {span_hz} Hz")
            self.write(f":SENSe:OBWidth:FREQ:SPAN {span_hz} Hz")
            readback = self.query(":SENSe:OBWidth:FREQ:SPAN?")
            print(f"[OBWidth] Span readback = {readback}")
            result = self.query(":READ:OBWidth?")
            print(f"[OBWidth] Result = {result}")
            return result
        except Exception as e:
            print(f"[SpectrumAnalyzer] ERROR OBWidth: {e}")
            return None

    def set_trace_average(self) -> None:
        self.write(":TRAC:TYPE AVER")

    def set_sanalyzer(self) -> None:
        self.write(":CONF:SAN")

    # ---------- TRACE ---------- #
    def fetch_trace(self, trace_name: str = "TRACE1") -> tuple[np.ndarray, np.ndarray]:
        if not self.sa:
            raise ValueError("Analyzer not connected")
        try:
            self.write(":FORM REAL,32")
            self.write(":FORM:BORD SWAP")
        except Exception as e:
            print(f"[fetch_trace] Warning setting format: {e}")

        try:
            pts = int(float(self.query("SWE:POIN?")))
        except Exception:
            pts = 1001

        trace = self.query_binary_values(f"TRAC:DATA? {trace_name}",
                                         datatype='f', container=np.array)
        if trace is None or len(trace) == 0:
            raise RuntimeError("No trace data returned")

        if len(trace) != pts:
            pts = len(trace)

        cf = float(self.get_center_frequency() or 0.0)
        span = float(self.get_span() or 1.0)
        freqs = np.linspace(cf - span/2, cf + span/2, pts)
        return freqs, trace

    # ---------- Screenshot ---------- #
    def _read_ieee_block(self) -> bytes:
        hdr = self.sa.read_bytes(2)  # "#<n>"
        if not hdr or hdr[0] != ord('#'):
            raise RuntimeError("Not an IEEE block")
        n_digits = int(chr(hdr[1]))
        len_str = self.sa.read_bytes(n_digits).decode()
        total = int(len_str)
        print(f"[ieee_block] Expecting {total} bytes …")
        data, remaining = bytearray(), total
        while remaining:
            chunk = self.sa.read_bytes(min(1_048_576, remaining))
            data.extend(chunk)
            remaining -= len(chunk)
        return bytes(data)

    def capture_screen(self, local_filename: str = None) -> tuple[str | None, str | None]:
        if not self.sa:
            raise ValueError("Analyzer not connected")

        attempts = [
            (r"D:\\Users\\Instrument\\Documents\\SA\\screen", "hiSky instrument SA screen folder"),
            (r"SA\\screen", "default subdir"),
            (r"C:\\temp", "root temp dir"),
            (r"D:\\", "root D drive"),
            (r"C:\\", "root C drive"),
        ]
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        if local_filename is None:
            local_filename = f"screenshot_{timestamp}.png"

        last_error = None
        for subdir, desc in attempts:
            try:
                remote_name = f"Screenshot_{timestamp}.PNG"
                remote_path = rf"{subdir}\{remote_name}"
                print(f"[capture_screen] Trying {desc}: {remote_path}")
                self.write(f':MMEM:STOR:SCR "{remote_path}"')
                self.wait_for_opc()
                time.sleep(2.0)

                try:
                    cat = self.query(f':MMEM:CAT? "{subdir}"')
                    print(f"[capture_screen] Directory listing: {cat}")
                    if remote_name not in cat:
                        print("[capture_screen] File not found in directory listing!")
                        continue
                except Exception as e:
                    print(f"[capture_screen] Directory listing failed: {e}")

                old_timeout = self.sa.timeout
                old_chunk = getattr(self.sa, "chunk_size", 20000)
                self.sa.timeout = 120000
                self.sa.chunk_size = 1_048_576
                try:
                    print("[capture_screen] Request file …")
                    self.write(f':MMEM:DATA? "{remote_path}"')
                    data = self._read_ieee_block()
                    print(f"[capture_screen] Writing {len(data)} bytes → {local_filename}")
                    with open(local_filename, "wb") as f:
                        f.write(data)
                    print("[capture_screen] SUCCESS")
                    return local_filename, remote_path
                except Exception as e:
                    print(f"[capture_screen] ERROR (fetch): {e}")
                    last_error = e
                finally:
                    self.sa.timeout = old_timeout
                    self.sa.chunk_size = old_chunk
            except Exception as e:
                print(f"[capture_screen] ERROR (store): {e}")
                last_error = e

        print(f"[capture_screen] All attempts failed. Last error: {last_error}")
        return None, None

    def delete_remote_file(self, remote_path: str) -> bool:
        try:
            self.write(f':MMEM:DEL "{remote_path}"')
            self.wait_for_opc()
            print(f"[delete_remote_file] Deleted {remote_path}")
            return True
        except Exception as e:
            print(f"[delete_remote_file] ERROR: {e}")
            return False
