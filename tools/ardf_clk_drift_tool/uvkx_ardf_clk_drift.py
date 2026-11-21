#!/usr/bin/env python3

import argparse
import re
import textwrap
import sys
import threading
import time
from collections import deque

import numpy as np
import serial
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Button
from matplotlib.ticker import MultipleLocator

XOR_KEY = bytes([
   0x16, 0x6c, 0x14, 0xe6,
   0x2e, 0x91, 0x0d, 0x40,
   0x21, 0x35, 0xd5, 0x40,
   0x13, 0x03, 0xe9, 0x80,
])


logfile = open("logfile.csv", "w")

# ---------------------------------------------------------------------------
# GUI language (--lang de|en). All texts shown in the window live in TEXTS.
# ---------------------------------------------------------------------------
VERSION = "v0.1"
LANG = "en"


TEXTS = {
   # --- legends / labels -------------------------------------------------
   "drift":            {"en": "Drift (PC - Radio)",
                        "de": "Drift (PC - Funkgerät)"},
   "drift_corr_temp":  {"en": "Drift (PC - Radio), temp corr",
                        "de": "Drift (PC - Funkgerät), temperaturkorrigiert"},
   "drift_corr_fixed": {"en": "Drift (PC - Radio), corrected",
                        "de": "Drift (PC - Funkgerät), korrigiert"},
   "form_temp":        {"en": "new calc. temp. formula (K1 + Tavg * K2)",
                        "de": "neu ber. Temp-Formel (K1 + Tavg * K2)"},
   "form_fixed":       {"en": "new calculated fixed offset K1",
                        "de": "neuer ber. fester Offset K1"},
   "dtime2_temp":      {"en": "active temp. comp. in device",
                        "de": "akt. Temp-Kompensation im Gerät"},
   "dtime2_fixed":     {"en": "active correction in device",
                        "de": "Aktive Korrektur im Gerät"},
   "points":           {"en": "measured (one dot per time window)",
                        "de": "gemessen (ein Punkt je Zeitfenster)"},
   "last_window":      {"en": "latest window",
                        "de": "letztes Fenster"},
   "stored":           {"en": "stored in device",
                        "de": "im Gerät gespeichert"},
   "battery":          {"en": "Battery Voltage",
                        "de": "Batteriespannung"},
   "cpu_temp":         {"en": "CPU Temp",
                        "de": "CPU-Temperatur"},
   "cpu_temp_avg":     {"en": "CPU Temp (avg)",
                        "de": "CPU-Temperatur (Mittel)"},
   "too_fast":         {"en": "too fast", "de": "zu schnell"},
   "too_slow":         {"en": "too slow", "de": "zu langsam"},

   # --- axes / titles ----------------------------------------------------
   "title":            {"en": "UV-Kx ARDF clock drift tool " + VERSION,
                        "de": "UV-Kx ARDF Clock-Drift-Tool " + VERSION},
   "error":            {"en": "Error: {e}", "de": "Fehler: {e}"},
   "xlabel_time":      {"en": "Elapsed Time [s]", "de": "Laufzeit [s]"},
   "ylabel_drift":     {"en": "Drift [s]", "de": "Drift [s]"},
   "ylabel_dtime":     {"en": "Drift in 1h [s]",
                        "de": "Drift in 1h [s]"},
   "title2_temp":      {"en": "Drift extrapolated to one hour",
                        "de": "Drift hochgerechnet auf eine Stunde"},
   "title2_fixed":     {"en": "Drift extrapolated to one hour",
                        "de": "Drift hochgerechnet auf eine Stunde"},
   "title3_temp":      {"en": "Drift vs. temperature: Derivation of K1 + Tavg * K2 (one dot = {w:.0f} s window)",
                        "de": "Drift über Temperatur: Herleitung von K1 + Tavg * K2 (ein Punkt = {w:.0f}-s-Fenster)"},
   "title3_fixed":     {"en": "Drift vs. time (no temperature sensor): Derivation of fixed offset K1 (one dot = {w:.0f} s window)",
                        "de": "Drift über Zeit (ohne Temperaturmessung): Herleitung des festen Offsets K1 (ein Punkt = {w:.0f}-s-Fenster)"},
   "xlabel3_temp":     {"en": "Averaged temperature Tavg [°C]",
                        "de": "Gemittelte Temperatur Tavg [°C]"},
   "ylabel3":          {"en": "Needed corr.\n[ticks/min]",
                        "de": "Nötige Korr.\n[Ticks/min]"},
   "ylabel3_right":    {"en": "Drift in 1h [s]",
                        "de": "Drift in 1 h [s]"},
   "ylabel_bat":       {"en": "Voltage [V]", "de": "Spannung [V]"},
   "ylabel_temp":      {"en": "Temperature [°C]", "de": "Temperatur [°C]"},
   "unit_tpm":         {"en": "ticks/min", "de": "Ticks/min"},
   "unit_tpmk":        {"en": "ticks/min/°C", "de": "Ticks/min/°C"},

   # --- legend texts of plot 3 -------------------------------------------
   "fit_label_fixed":  {"en": "K1 = {k1:+.3f} ticks/min (fixed offset)",
                        "de": "K1 = {k1:+.3f} Ticks/min (fester Offset)"},
   "fit_range":        {"en": "  (seen range {a:.1f}..{b:.1f} °C)",
                        "de": "  (gesehener Bereich {a:.1f}..{b:.1f} °C)"},
   "dev_label_fixed":  {"en": "stored in device: K1 = {k1:+d}",
                        "de": "im Gerät gespeichert: K1 = {k1:+d}"},
   "dev_label_temp":  {"en": "stored in device: {k1:+d} {op} {k2:.2f} * Tavg = {val:+.2f}",
                        "de": "im Gerät gespeichert: {k1:+d} {op} {k2:.2f} * Tavg = {val:+.2f}"},

   # --- info box ---------------------------------------------------------
   "info_head_temp":   {"en": "Correction formula: Additional 10 ms ticks per minute  =  K1 + Tavg * K2",
                        "de": "Korrekturformel: Zusätzliche 10-ms-Ticks pro Minute  =  K1 + Tavg * K2"},
   "info_head_fixed":  {"en": "Correction:   10 ms ticks per minute  =  K1",
                        "de": "Korrektur:   10-ms-Ticks pro Minute  =  K1"},
   "hw_temp":          {"en": "HW with temperature sensor (V3)",
                        "de": "HW mit Temperaturmessung (V3)"},
   "hw_fixed":         {"en": "HW V{v}: no temperature sensor",
                        "de": "HW V{v}: ohne Temperaturmessung"},
   "waiting":          {"en": "Waiting for data ...", "de": "Warte auf Daten ..."},
   "waiting_detail":   {"en": "Waiting for data (at least {p} points and {s:.0f} s) ...",
                        "de": "Warte auf Daten (mind. {p} Punkte und {s:.0f} s) ..."},
   "now_fixed":        {"en": "Recommended: K1 = {k1:+d} {u}   (fixed offset, no temperature compensation possible)",
                        "de": "Empfohlen: K1 = {k1:+d} {u}   (fester Offset, keine Temperaturkompensation möglich)"},
   "now_temp":         {"en": "Current: Tavg = {tavg:.1f} °C => correction {c:+.2f} {u} (rounded {r:+d})",
                        "de": "Aktuell: Tavg = {tavg:.1f} °C => Korrektur {c:+.2f} {u} (gerundet {r:+d})"},
   "basis_fixed":      {"en": "Basis: {n} points, {m:.0f} min measuring time",
                        "de": "Basis: {n} Punkte, {m:.0f} min Messdauer"},
   "basis_temp":       {"en": "Basis: Temperature range {tmin:.1f} .. {tmax:.1f} °C (span {span:.1f} K), {n} points, {m:.0f} min, averaging {avg:.0f} s",
                        "de": "Basis: Temperaturbereich {tmin:.1f} .. {tmax:.1f} °C (Spanne {span:.1f} K), {n} Punkte, {m:.0f} min, Mittelung {avg:.0f} s"},
   "dev_fixed":        {"en": "In device: K1 = {k1:+d} {u}   (K2 is ignored by HW {v})",
                        "de": "Im Gerät: K1 = {k1:+d} {u}   (K2 wird von HW {v} ignoriert)"},
   "dev_temp":         {"en": "In device: K1 = {k1:+d} {u}   K2 = {k2:+.2f} {uk} (raw {raw:+d})",
                        "de": "Im Gerät: K1 = {k1:+d} {u}   K2 = {k2:+.2f} {uk} (Rohwert {raw:+d})"},
   "extrapolation":    {"en": "Formula only valid within the seen temperature range; outside it is extrapolation.",
                        "de": "Formel gilt nur innerhalb des gesehenen Temperaturbereichs; außerhalb ist es Extrapolation."},
   "warn_span":        {"en": "WARNING: Temperature span < {r:.1f} K => K2 not yet determinable (K2 = 0), only K1 fitted.",
                        "de": "ACHTUNG: Temperaturspanne < {r:.1f} K => K2 noch nicht bestimmbar (K2 = 0), nur K1 gefittet."},

   # --- serial port dialog -----------------------------------------------
   "port_title":       {"en": "Select serial port", "de": "Serielle Schnittstelle wählen"},
   "port_hint":        {"en": "Select a port or type its name (e.g. /dev/ttyACM0 or COM3).",
                        "de": "Port auswählen oder Namen eingeben (z. B. /dev/ttyACM0 oder COM3)."},
   "port_label":       {"en": "Port:", "de": "Port:"},
   "port_refresh":     {"en": "Refresh", "de": "Aktualisieren"},
   "port_connect":     {"en": "Connect", "de": "Verbinden"},
   "port_cancel":      {"en": "Cancel", "de": "Abbrechen"},
   "port_none":        {"en": "No serial ports found - connect the device and press Refresh.",
                        "de": "Keine seriellen Ports gefunden - Gerät anschließen und auf Aktualisieren drücken."},
   "port_found":       {"en": "{n} port(s) found", "de": "{n} Port(s) gefunden"},

   # --- write button -----------------------------------------------------
   "btn_waiting":      {"en": "Write {what} to device\nwaiting for data",
                        "de": "{what} ins Gerät schreiben\nwarte auf Daten"},
   "btn_ready":        {"en": "Write {what} to device\n({vals})",
                        "de": "{what} ins Gerät schreiben\n({vals})"},
   "btn_notready":     {"en": "Write {what} to device\nnot ready: {reason}",
                        "de": "{what} ins Gerät schreiben\nnicht bereit: {reason}"},
   "written_temp":     {"en": "written: K1 = {r1:+d}, K2 = {k2:+.2f} (raw {r2:+d})",
                        "de": "geschrieben: K1 = {r1:+d}, K2 = {k2:+.2f} (Rohwert {r2:+d})"},
   "written_fixed":    {"en": "written: K1 = {r1:+d}  (K2 is ignored by HW {v})",
                        "de": "geschrieben: K1 = {r1:+d}  (K2 wird von HW {v} ignoriert)"},
   "write_error":      {"en": "ERROR while writing: {e}",
                        "de": "FEHLER beim Schreiben: {e}"},

   # --- reasons why the button is not ready (fit_reliable) ---------------
   "r_wait":           {"en": "Waiting for data", "de": "Warte auf Daten"},
   "r_duration":       {"en": "Measuring time < {m:.0f} min", "de": "Messdauer < {m:.0f} min"},
   "r_k1err":          {"en": "K1 uncertainty {e:.3f} > {mx:.3f}", "de": "K1-Unsicherheit {e:.3f} > {mx:.3f}"},
   "r_k2err":          {"en": "K2 uncertainty {e:.3f} > {mx:.3f}", "de": "K2-Unsicherheit {e:.3f} > {mx:.3f}"},
   "r_k1range":        {"en": "K1 outside device range ({k1:+d})", "de": "K1 außerhalb Gerätebereich ({k1:+d})"},
   "r_range":          {"en": "Values outside device range (K1 {k1:+d}, K2 {k2:+.2f})",
                        "de": "Werte außerhalb Gerätebereich (K1 {k1:+d}, K2 {k2:+.2f})"},
   "r_trange":         {"en": "Temperature span < {r:.1f} K", "de": "Temperaturspanne < {r:.1f} K"},
}


def tr(key, **kw):
   """Return the GUI text for 'key' in the selected language, formatted with kw."""
   return TEXTS[key][LANG].format(**kw)

ARDFClockCorrAddTicksPerMin = 0

# Temperature compensation: ticks/min = K1 + Tavg * K2
TEMP_AVG_SECONDS = 60.0      # averaging window of the temperature [s] (--tavg)
MIN_TEMP_RANGE = 2.0         # K2 is only fitted once the seen temperature span [K] reaches this (--min-trange)
MIN_FIT_SECONDS = 120.0      # minimum measuring time before a fit is shown
MIN_FIT_POINTS = 10          # minimum number of data points before a fit is shown
RATE_WINDOW_SECONDS = 300.0  # time block for one dot of the drift-rate plot (--rate-window)

# Writing K1/K2 to the device
INFO_EDGE_IDLE = "#9aa5b1"   # frame color of the info box while the data is not reliable
INFO_EDGE_READY = "#4cc22a"  # frame color once the data is reliable (button green)
K2_SCALE = 100               # the device stores K2 in 1/100 ticks/min per degree C (K1 in ticks/min)
S_PER_H_PER_TICK_PER_MIN = 0.6   # 1 tick/min of 10 ms = 0.01 s * 60 min/h = 0.6 s/h of compensated drift
DEVICE_LIMIT = 500           # allowed range of the raw values K1 and K2 in the device
RELIABLE_MIN_SECONDS = 600.0 # minimum measuring time before the button turns green
RELIABLE_MAX_K2_ERR = 0.05   # max. uncertainty (1 sigma) of K2 [ticks/min/degC] to count as reliable (--max-k2-err)

# Older devices without internal temperature sensor report these marker values instead of K2 in message 0542
HW_NO_TEMP_MARKERS = {32701: 1, 32702: 2}        # raw K2 value -> hardware version
RELIABLE_MAX_K1_ERR = 0.25   # without temperature sensor: max. uncertainty (1 sigma) of K1 [ticks/min] (--max-k1-err)
hw_info = {"version": 0, "has_temp": True}       # version 0 = device with temperature sensor

port_lock = threading.Lock()                     # serial port: only one command at a time
device_params = {"k1": None, "k2_raw": None}     # raw values last read from / confirmed by the device



def crc16_xmodem(data):
   crc = 0

   for byte in data:
      crc ^= byte << 8

      for _ in range(8):
         crc <<= 1

         if crc & 0x10000:
            crc ^= 0x1021

   return crc & 0xffff



def xor_data(data):
   data = bytearray(data)

   for i in range(len(data)):
      data[i] ^= XOR_KEY[i % len(XOR_KEY)]

   return bytes(data)



def encode_command(command):
   length = len(command)

   packet = bytearray()

   packet += b"\xab\xcd"
   packet += length.to_bytes(2, "little")
   packet += command

   crc = crc16_xmodem(command)

   packet += crc.to_bytes(2, "little")

   # XOR applies to command + CRC, not header/footer
   encoded = bytearray(packet[:4])
   encoded += xor_data(packet[4:])

   encoded += b"\xdc\xba"

   return bytes(encoded)



def read_exact(port, length, timeout):
   data = bytearray()

   deadline = time.monotonic() + timeout

   while len(data) < length:
      remaining = deadline - time.monotonic()

      if remaining <= 0:
         raise TimeoutError(
            f"timeout while reading {length} bytes"
         )

      port.timeout = remaining

      chunk = port.read(length - len(data))

      if not chunk:
         raise TimeoutError(
            f"timeout while reading {length} bytes"
         )

      data += chunk

   return bytes(data)



def receive_command(port, timeout=2.0):
   # Find packet header.
   while True:
      header = read_exact(port, 2, timeout)

      if header == b"\xab\xcd":
         break

   length_bytes = read_exact(port, 2, timeout)

   length = int.from_bytes(length_bytes, "little")

   payload = read_exact(port, length + 4, timeout)

   encoded = header + length_bytes + payload

   if encoded[-2:] != b"\xdc\xba":
      raise RuntimeError("invalid packet footer")

   encoded_data = encoded[4:-2]

   data = xor_data(encoded_data)

   command = data[:-2]

   received_crc = int.from_bytes(data[-2:], "little")

   calculated_crc = crc16_xmodem(command)

   # The UV-K5 normally returns 0xffff as CRC.
   if received_crc != 0xffff:
      if received_crc != calculated_crc:
         raise RuntimeError(
            f"CRC error: received 0x{received_crc:04x}, "
            f"expected 0x{calculated_crc:04x}"
         )

   return command



def send_command(port, command):
   packet = encode_command(command)

   port.write(packet)
   port.flush()



def hello(port):
   command = bytes([0x14, 0x05, 0x04, 0x00, 0x6a, 0x39, 0x57, 0x64])

   send_command(port, command)

   response = receive_command(port)

   if len(response) < 4:
      raise RuntimeError( f"invalid hello response: {response.hex(' ')}" )

   return response



def fit_temp_model(t_s, drift, tavg, use_temp=True):
   """
   Determines the correction formula  ticks/min = K1 + Tavg * K2.

   Model: drift rate of the uncorrected clock (PC - device) in 10 ms ticks/s
          rate(T) = a + b * (T - Tref)
   => drift(t) = c + a * t + b * S(t),  S(t) = integral (Tavg - Tref) dt
   This is a linear regression over all data points. It also works while the
   temperature changes (no window and no derivative needed).

   Sign convention: positive = insert ticks (clock runs too fast).
   If the seen temperature span is < MIN_TEMP_RANGE only the constant is
   fitted (K2 = 0), because K2 cannot be determined otherwise.

   use_temp=False (device without temperature sensor, HW 1/2): only the fixed
   offset K1 is fitted (K2 = 0); the temperature data is not used.
   """
   result = {"valid": False}

   n = len(t_s)
   if n < MIN_FIT_POINTS:
      return result

   t = np.asarray(t_s, dtype=float)
   y = np.asarray(drift, dtype=float)
   T = np.asarray(tavg, dtype=float)

   if t[-1] - t[0] < MIN_FIT_SECONDS:
      return result

   tmin = float(T.min())
   tmax = float(T.max())
   tref = float(T.mean())
   Tc = T - tref

   S = np.concatenate(([0.0], np.cumsum(0.5 * (Tc[1:] + Tc[:-1]) * np.diff(t))))

   with_temp = use_temp and (tmax - tmin) >= MIN_TEMP_RANGE

   if with_temp:
      X = np.column_stack((np.ones(n), t, S))
   else:
      X = np.column_stack((np.ones(n), t))

   coef, *_ = np.linalg.lstsq(X, y, rcond=None)

   a = float(coef[1])
   b = float(coef[2]) if with_temp else 0.0

   b_err = float("nan")
   a_err = float("nan")
   dof = n - X.shape[1]
   if dof > 0:
      resid = y - X @ coef
      s2 = float(resid @ resid) / dof
      cov = s2 * np.linalg.pinv(X.T @ X)
      if with_temp:
         b_err = float(np.sqrt(max(cov[2, 2], 0.0)))
      else:
         a_err = float(np.sqrt(max(cov[1, 1], 0.0)))

   k2 = -60.0 * b                   # ticks/min per degree C
   k1 = -60.0 * (a - b * tref)      # ticks/min at 0 degree C
   k2_err = 60.0 * b_err
   k1_err = 60.0 * a_err            # only determined in the mode without K2 (pure offset)

   tavg_now = float(T[-1])

   result.update(
      valid=True,
      with_temp=with_temp,
      k1=k1,
      k2=k2,
      k2_err=k2_err,
      k1_err=k1_err,
      legacy=not use_temp,
      tmin=tmin,
      tmax=tmax,
      tavg_now=tavg_now,
      corr_now=k1 + k2 * tavg_now,
      n=n,
      span_s=float(t[-1] - t[0]),
   )

   return result



def drift_with_formula(t_s, drift_ticks, tavg, k1, k2):
   """
   Drift of the uncorrected clock, compensated with the formula
   ticks/min = k1 + Tavg * k2, returned as 1 h drift [s/h].

   The correction is integrated (trapezoid) over the averaged temperature of
   every data point and added to the measured drift:
      drift_comp(t) = drift(t) + integral (k1 + k2*Tavg) / 60 dt
   Then, for every point, the regression slope over all points up to there
   is determined (same as for the other 1 h drift lines).
   The complete curve is always recalculated with the given k1/k2.
   """
   t = np.asarray(t_s, dtype=float)
   y = np.asarray(drift_ticks, dtype=float)
   T = np.asarray(tavg, dtype=float)
   n = len(t)

   out = np.full(n, np.nan)
   if n < 2:
      return out

   corr = k1 + k2 * T   # ticks/min
   added = np.concatenate(([0.0], np.cumsum(0.5 * (corr[1:] + corr[:-1]) * np.diff(t)))) / 60.0
   yc = y + added       # compensated drift [10 ms ticks]

   # cumulative regression slope over points 0..i (centered for numerical stability)
   x = t - t.mean()
   z = yc - yc.mean()
   cnt = np.arange(1, n + 1)
   sx = np.cumsum(x)
   sz = np.cumsum(z)
   sxx = np.cumsum(x * x)
   sxz = np.cumsum(x * z)

   with np.errstate(divide="ignore", invalid="ignore"):
      den = sxx - sx * sx / cnt
      slope = (sxz - sx * sz / cnt) / den   # ticks/s
   slope[~np.isfinite(slope) | (den <= 1e-9)] = np.nan
   slope[0] = np.nan

   # 1 tick/s = 0.01 s/s = 36 s/h
   return slope * 36.0



def rate_vs_temperature(t_s, drift_ticks, tavg, window_s):
   """
   Local drift rate per time block (window_s) over the mean temperature of the block.

   Returns: (mean Tavg [degree C], needed correction [ticks/min], mean time of the block [s])
   The correction is -60 * slope of the drift within the block (same sign
   convention as K1 + Tavg * K2: positive = insert ticks, clock too fast).
   These are the "raw data" from which the correction line is derived.
   """
   t = np.asarray(t_s, dtype=float)
   y = np.asarray(drift_ticks, dtype=float)
   T = np.asarray(tavg, dtype=float)
   n = len(t)

   xs = []
   ys = []
   ts = []
   if n < 3:
      return np.array(xs), np.array(ys), np.array(ts)

   blk = np.floor(t / window_s).astype(int)
   bounds = np.concatenate(([0], np.flatnonzero(np.diff(blk)) + 1, [n]))

   for i in range(len(bounds) - 1):
      a, b = bounds[i], bounds[i + 1]
      if b - a < 3:
         continue
      if t[b - 1] - t[a] < 0.5 * window_s:
         continue
      slope = np.polyfit(t[a:b], y[a:b], 1)[0]   # ticks/s
      xs.append(float(T[a:b].mean()))
      ys.append(-60.0 * slope)
      ts.append(float(t[a:b].mean()))

   return np.array(xs), np.array(ys), np.array(ts)



def to_device_values(k1, k2):
   """Fit values (ticks/min, ticks/min/degC) -> integer raw device values (K2 in 1/100)."""
   return int(round(k1)), int(round(k2 * K2_SCALE))



def fmt_device_values(k1_i, k2_i):
   """Text for device values: K2 (raw / 100) only for devices with temperature sensor."""
   if hw_info["has_temp"]:
      return f"K1 = {k1_i:+d}, K2 = {k2_i / K2_SCALE:+.2f}"
   return f"K1 = {k1_i:+d}"



def fit_reliable(fit):
   """
   Decides whether the currently determined K1/K2 are reliable enough to be
   written into the device. Returns (ok, reason if not ok); the reason is a
   GUI text in the selected language.
   """
   if fit is None or not fit["valid"]:
      return False, tr("r_wait")
   if fit.get("legacy"):
      # device without temperature sensor: fixed offset K1 only
      if fit["span_s"] < RELIABLE_MIN_SECONDS:
         return False, tr("r_duration", m=RELIABLE_MIN_SECONDS / 60.0)
      if not np.isfinite(fit["k1_err"]) or fit["k1_err"] > RELIABLE_MAX_K1_ERR:
         return False, tr("r_k1err", e=fit["k1_err"], mx=RELIABLE_MAX_K1_ERR)
      k1_i = int(round(fit["k1"]))
      if abs(k1_i) > DEVICE_LIMIT:
         return False, tr("r_k1range", k1=k1_i)
      return True, ""
   if not fit["with_temp"]:
      return False, tr("r_trange", r=MIN_TEMP_RANGE)
   if fit["span_s"] < RELIABLE_MIN_SECONDS:
      return False, tr("r_duration", m=RELIABLE_MIN_SECONDS / 60.0)
   if not np.isfinite(fit["k2_err"]) or fit["k2_err"] > RELIABLE_MAX_K2_ERR:
      return False, tr("r_k2err", e=fit["k2_err"], mx=RELIABLE_MAX_K2_ERR)
   k1_i, k2_i = to_device_values(fit["k1"], fit["k2"])
   if abs(k1_i) > DEVICE_LIMIT or abs(k2_i) > DEVICE_LIMIT:
      return False, tr("r_range", k1=k1_i, k2=k2_i / K2_SCALE)
   return True, ""



# ---------------------------------------------------------------------------
# Data shared between the reader thread and the plot (main thread)
# ---------------------------------------------------------------------------

class DriftData:
   def __init__(self):
      self.lock = threading.Lock()
      self.elapsed = []      # runtime in 10 ms units
      self.drift = []        # drift in 10 ms units
      self.correction = []   # recommended correction value (nan = not computable yet)
      self.dtime = []        # 1h drift time 
      self.bat = []
      self.temp = []
      self.tavg = []         # averaged temperature [degree C]
      self.fit = None        # result of fit_temp_model()

      # with temperature correction
      self.correction_corr = []
      self.drift_corr = []   # drift in 10 ms units with temperature correction
      self.dtime_corr = []   # 1h drift time 
      self.dtime_comp_corr = []

      self.error = None      # exception from the reader thread



def read_ardf(port):

   global ARDFClockCorrAddTicksPerMin
   
   command = bytearray([0x42, 0x5, 0x0, 0x0])

   with port_lock:
      send_command(port, command)
      response = receive_command(port)

   if len(response) < 12:
      raise RuntimeError(
         f"short read response: "
         f"got {len(response) - 8} data bytes, "
         f"expected {12}"
      )

   ARDFFoxDuration10ms_corr = int.from_bytes(response[4:8], byteorder='little', signed=True)
   ARDFClockCorrAddTicksPerMin_K1 = int.from_bytes(response[8:10], byteorder='little', signed=True)
   ARDFClockCorrAddTicksPerMin_K2 = int.from_bytes(response[10:12], byteorder='little', signed=True)

   # Detect the hardware: HW 1/2 have no temperature sensor and report a marker value instead of K2
   if ARDFClockCorrAddTicksPerMin_K2 in HW_NO_TEMP_MARKERS:
      hw_info["version"] = HW_NO_TEMP_MARKERS[ARDFClockCorrAddTicksPerMin_K2]
      hw_info["has_temp"] = False
      device_params["k1"] = ARDFClockCorrAddTicksPerMin_K1
      device_params["k2_raw"] = None      # these devices have no K2
      hw_text = f"HW version {hw_info['version']}: no temperature sensor, fixed offset K1 only"
   else:
      hw_info["version"] = 0
      hw_info["has_temp"] = True
      device_params["k1"] = ARDFClockCorrAddTicksPerMin_K1
      device_params["k2_raw"] = ARDFClockCorrAddTicksPerMin_K2
      hw_text = "Hardware with temperature sensor: correction K1 + Tavg * K2"

   print("; Detected hardware: " + hw_text)
   print("; Detected hardware: " + hw_text, file=logfile)

   print("; ARDFFoxDuration10ms_corr " + str(ARDFFoxDuration10ms_corr) + ", ARDFClockCorrAddTicksPerMin_K1: " + str(ARDFClockCorrAddTicksPerMin_K1) + ", ARDFClockCorrAddTicksPerMin_K2: " + str(ARDFClockCorrAddTicksPerMin_K2) , file=logfile)



def read_ardf2(port, data, stop_event):

   first_runtime = 0
   first_drifttime = 0
   first_radiotime = 0
   first_drifttime_corr = 0
   first_radiotime_corr = 0

   lastdrift_t2 = None
   lastdrift_t2_corr = None

   command = bytearray([0x43, 0x5, 0x0, 0x0])

   temp_hist = deque()   # (time, temperature) of all readings for the moving average

   starttime = time.time()

   while not stop_event.is_set():

      with port_lock:
         send_command(port, command)
         response = receive_command(port)

      now = time.time()
      runtime_10ms = round((now - starttime) * 100)

      if len(response) < 16:
         raise RuntimeError(
            f"short read response: "
            f"got {len(response) - 8} data bytes, "
            f"expected {16}"
         )

      ARDFCnt10ms = response[7] << 24 | response[6] << 16 | response[5] << 8 | response[4]
      ARDFCnt10msCorr = response[11] << 24 | response[10] << 16 | response[9] << 8 | response[8]

      BatteryVoltageAverage = response[13] << 8 | response[12]
      temp = int.from_bytes(response[14:16], byteorder='little', signed=True)

      drift_t2 = runtime_10ms - ARDFCnt10ms
      drift_t2_corr = runtime_10ms - ARDFCnt10msCorr

      # temperature averaged over the last TEMP_AVG_SECONDS (all readings, not only drift changes)
      temp_hist.append((now, temp / 10.0))
      while temp_hist and temp_hist[0][0] < now - TEMP_AVG_SECONDS:
         temp_hist.popleft()
      temp_avg = sum(v for _, v in temp_hist) / len(temp_hist)

      if (drift_t2 != lastdrift_t2) or (drift_t2_corr != lastdrift_t2_corr):

         with data.lock:
            if not data.elapsed:
               # first value
               first_runtime = runtime_10ms
               first_drifttime = drift_t2
               first_radiotime = ARDFCnt10ms
               first_drifttime_corr = drift_t2_corr
               first_radiotime_corr = ARDFCnt10msCorr

            data.elapsed.append(runtime_10ms - first_runtime) # [s]

            data.drift.append(drift_t2 - first_drifttime) # [10ms ticks]

            data.drift_corr.append(drift_t2_corr - first_drifttime_corr) # [10ms ticks]

            data.bat.append( float(BatteryVoltageAverage) / 100.0 )
            data.temp.append( float(temp) / 10.0 )
            data.tavg.append( temp_avg )


            if len(data.elapsed) >= 2:
               m, _b = np.polyfit(data.elapsed, data.drift, 1) # 10ms ticks / s
               m2, _b2 = np.polyfit(data.elapsed, data.drift_corr, 1) # 10ms ticks / s

               corr = float(m * 100 * 60 * (-1)) # number 10ms ticks that have to be added/removed in 1 min
               dtime = float(m * 100 * 60 * (3/5)) # drift time in 1h. (ticks/min) / 100 [ticks/s]  * 60 min/h = s/min / 10 * 6 min/h = 3/5 s/h

               corr_corr = float(m2 * 100 * 60 * (-1)) # number 10ms ticks that have to be added/removed in 1 min
               dtime_corr = float(m2 * 100 * 60 * (3/5)) # drift time in 1h. (ticks/min) / 100 [ticks/s]  * 60 min/h = s/min / 10 * 6 min/h = 3/5 s/h
               dtime_comp_corr = dtime_corr # float(m2 * 100 * 60 * (3/5) + ARDFClockCorrAddTicksPerMin/100 * 60  ) # drift time in 1h with current correction factor

               if m >= 0:
                  print(f"\nUncorrected device loses about {m * 100 * 60 * (3/5):+.1f} s per hour (too slow)")
               else:
                  print(f"\nUncorrected device gains about {m * 100 * 60 * (3/5):+.1f} s per hour (too fast)")
               
               print(f"=> Currently needed correction value: {np.round(corr):+.0f} <=")

               if m2 >= 0:
                  print(f"Corrected device loses about {m2 * 100 * 60 * (3/5):+.1f} s per hour (too slow)")
               else:
                  print(f"Corrected device gains about {m2 * 100 * 60 * (3/5):+.1f} s per hour (too fast)")
               
               print(f"=> Correction value deviation: {np.round(corr_corr):+.0f} <=")

               # temperature compensation: ticks/min = K1 + Tavg * K2
               fit = fit_temp_model(
                  np.array(data.elapsed, dtype=float) / 100.0,
                  data.drift,
                  data.tavg,
                  use_temp=hw_info["has_temp"],
               )
               data.fit = fit

               if fit["valid"] and fit["legacy"]:
                  print(f"Ticks/min = K1 = {fit['k1']:+.4f}, {fit['span_s'] / 60.0:.0f} min, HW {hw_info['version']}, fixed offset")
               elif fit["valid"]:
                  print(
                     f"Ticks/min = {fit['k1']:+.4f} {fit['k2']:+.4f} * Tavg = {fit['corr_now']:+.2f}"
                     f" (Tavg {fit['tavg_now']:.1f} C)"
                  )
                  print(f"K1={fit['k1']:+.4f} K2={fit['k2']:+.4f}, {fit['tmin']:.1f}..{fit['tmax']:.1f} C, {fit['span_s'] / 60.0:.0f} min")


            else:
               corr = float("nan")
               dtime = float("nan")

               corr_corr = float("nan")
               dtime_corr = float("nan")
               dtime_comp_corr = float("nan")

            data.correction.append(corr)
            data.dtime.append(dtime)

            data.correction_corr.append(corr_corr)
            data.dtime_corr.append(dtime_corr)
            data.dtime_comp_corr.append(dtime_comp_corr)


         #print(f"{runtime_10ms - first_runtime}, {BatteryVoltageAverage}, {ARDFCnt10ms - first_radiotime}, {drift_t2 - first_drifttime}, {ARDFCnt10msCorr - first_radiotime_corr}, {drift_t2_corr - first_drifttime_corr}, {temp}")
         print(f"{runtime_10ms - first_runtime}, {BatteryVoltageAverage}, {ARDFCnt10ms - first_radiotime}, {drift_t2 - first_drifttime}, {ARDFCnt10msCorr - first_radiotime_corr}, {drift_t2_corr - first_drifttime_corr}, {temp}", file=logfile)

      lastdrift_t2 = drift_t2
      lastdrift_t2_corr = drift_t2_corr

      stop_event.wait(1.01)



def write_ardf_k1k2(port, ARDFClockCorrAddTicksPerMin_K1, ARDFClockCorrAddTicksPerMin_K2):

   if not -500 <= ARDFClockCorrAddTicksPerMin_K1 <= 500:
      raise ValueError("K1 must be -500..500")

   if not -500 <= ARDFClockCorrAddTicksPerMin_K2 <= 500:
      raise ValueError("K2 must be -500..500 [* 1/100]")

   command = bytearray([
      0x44, # header: id
      0x05, # header: id
      (8) & 0xff, # header: size
      0x00, # header: size
      ARDFClockCorrAddTicksPerMin_K1 & 0xff,
      (ARDFClockCorrAddTicksPerMin_K1 >> 8) & 0xff,
      ARDFClockCorrAddTicksPerMin_K2 & 0xff,
      (ARDFClockCorrAddTicksPerMin_K2 >> 8) & 0xff,
   ])

   # the reader thread uses the same port: command + response must run as one transaction
   with port_lock:
      send_command(port, command)
      response = receive_command(port)

   if len(response) < 12:
      raise RuntimeError(
         f"short read response: "
         f"got {len(response) - 8} data bytes, "
         f"expected {12}"
      )

   ARDFFoxDuration10ms_corr = int.from_bytes(response[4:8], byteorder='little', signed=True)
   ARDFClockCorrAddTicksPerMin_K1 = int.from_bytes(response[8:10], byteorder='little', signed=True)
   ARDFClockCorrAddTicksPerMin_K2 = int.from_bytes(response[10:12], byteorder='little', signed=True)

   # values confirmed (read back) by the device; HW 1/2 have no K2 (ignored by the device)
   device_params["k1"] = ARDFClockCorrAddTicksPerMin_K1
   device_params["k2_raw"] = ARDFClockCorrAddTicksPerMin_K2 if hw_info["has_temp"] else None

   print("; ARDFFoxDuration10ms_corr " + str(ARDFFoxDuration10ms_corr) + ", ARDFClockCorrAddTicksPerMin_K1: " + str(ARDFClockCorrAddTicksPerMin_K1) + ", ARDFClockCorrAddTicksPerMin_K2: " + str(ARDFClockCorrAddTicksPerMin_K2) )
   print("; ARDFFoxDuration10ms_corr " + str(ARDFFoxDuration10ms_corr) + ", ARDFClockCorrAddTicksPerMin_K1: " + str(ARDFClockCorrAddTicksPerMin_K1) + ", ARDFClockCorrAddTicksPerMin_K2: " + str(ARDFClockCorrAddTicksPerMin_K2) , file=logfile)

   return ARDFClockCorrAddTicksPerMin_K1, ARDFClockCorrAddTicksPerMin_K2



def reader_thread(port, data, stop_event):
   try:
      read_ardf2(port, data, stop_event)
   except Exception as e:  # pass the error on to the plot
      data.error = e
      print(f"Reader thread terminated: {e!r}")



def run_live_plot(port):

   has_temp = hw_info["has_temp"]   # False: HW 1/2 without temperature sensor -> fixed offset K1 only
   data = DriftData()
   stop_event = threading.Event()

   thread = threading.Thread(
      target=reader_thread,
      args=(port, data, stop_event),
      daemon=True,
   )

   fig = plt.figure(figsize=(11, 9.5))   # default window size; the layout adapts when the window is resized
   # Axes order from top to bottom: plots 1..3 share the time axis, plot 4 has its own temperature axis,
   # then the info box and the button. The positions are set by layout_axes() below.
   ax_drift = fig.add_axes([0.10, 0.80, 0.80, 0.15])
   ax_dtime_comp = fig.add_axes([0.10, 0.60, 0.80, 0.15], sharex=ax_drift)
   ax_bat = fig.add_axes([0.10, 0.40, 0.80, 0.15], sharex=ax_drift)
   ax_fit = fig.add_axes([0.10, 0.20, 0.80, 0.15])      # x = temperature, so no sharex with the time axis
   ax_info = fig.add_axes([0.10, 0.08, 0.80, 0.08])
   ax_info.set_xticks([])
   ax_info.set_yticks([])
   ax_info.set_facecolor("#f4f7fb")
   for sp in ax_info.spines.values():
      sp.set_edgecolor(INFO_EDGE_IDLE)
      sp.set_linewidth(2.5)
   ax_btn = fig.add_axes([0.10, 0.02, 0.80, 0.04])
   ax_temp = ax_bat.twinx()

   # Layout in points instead of fractions of the window: the texts (titles, labels) have a fixed size
   # in points, so the gaps between the plots must have one too. Otherwise a smaller window (e.g. on
   # Windows with display scaling) makes the x label of one plot run into the title of the next.
   # The four plots share the remaining height equally.
   LEFT_PT, RIGHT_PT = 54.0, 60.0      # room for y labels / tick labels (left) and the right axes
   TOP_PT, BOTTOM_PT = 52.0, 12.0      # main title / bottom margin
   GAP_1_2_PT = 32.0                   # title of plot 2
   GAP_2_3_PT = 14.0                   # plots 2 and 3 only touch (no labels in between)
   GAP_3_4_PT = 64.0                   # x label of plot 3 + title of plot 4
   GAP_4_INFO_PT = 44.0                # x label of plot 4
   INFO_PT = 124.0                     # height of the info box and of the button next to it
   INFO_WIDTH_FRAC = 0.70              # share of the content width used by the info box
   BTN_GAP_PT = 10.0                   # gap between the info box and the button
   MIN_PLOT_PT = 34.0                  # below this the info box shrinks first
   MIN_INFO_PT = 70.0

   def layout_axes(_event=None):
      w_pt, h_pt = fig.get_size_inches() * 72.0
      left = LEFT_PT / w_pt
      width = max(0.2, 1.0 - (LEFT_PT + RIGHT_PT) / w_pt)

      gaps = (GAP_1_2_PT, GAP_2_3_PT, GAP_3_4_PT, GAP_4_INFO_PT)
      space = h_pt - (TOP_PT + BOTTOM_PT + sum(gaps))   # left for the plots + the info row
      info_h = INFO_PT
      plot_h = (space - info_h) / 4.0
      if plot_h < MIN_PLOT_PT:
         # small window: shrink the info box first (its fonts adapt), then the plots
         info_h = max(MIN_INFO_PT, space - 4.0 * MIN_PLOT_PT)
         plot_h = max(MIN_PLOT_PT * 0.75, (space - info_h) / 4.0)

      y = h_pt - TOP_PT
      for ax, gap in zip((ax_drift, ax_dtime_comp, ax_bat, ax_fit), gaps):
         ax.set_position([left, (y - plot_h) / h_pt, width, plot_h / h_pt])
         y -= plot_h + gap

      # info box on the left, write button on the right (same height)
      content_pt = width * w_pt
      info_w_pt = content_pt * INFO_WIDTH_FRAC
      btn_w_pt = content_pt - info_w_pt - BTN_GAP_PT
      ax_info.set_position([left, (y - info_h) / h_pt, info_w_pt / w_pt, info_h / h_pt])
      ax_btn.set_position([left + (info_w_pt + BTN_GAP_PT) / w_pt, (y - info_h) / h_pt, btn_w_pt / w_pt, info_h / h_pt])

   layout_axes()
   fig.canvas.mpl_connect("resize_event", layout_axes)

   # create the lines once
   drift_line, = ax_drift.plot(
      [], [],
      color="tab:red",
      linewidth=2,
      label=tr("drift"),
   )

   dtime_form_line, = ax_dtime_comp.plot(
      [], [],
      color="tab:orange",
      linewidth=2,
      label=tr("form_temp") if has_temp else tr("form_fixed"),
   )

   # 3rd plot: drift rate over temperature
   fit_points, = ax_fit.plot(
      [], [],
      linestyle="none",
      marker="o",
      markersize=5,
      color="tab:blue",
      alpha=0.7,
      label=tr("points"),
   )

   fit_last, = ax_fit.plot(
      [], [],
      linestyle="none",
      marker="o",
      markersize=9,
      markerfacecolor="none",
      markeredgecolor="tab:red",
      markeredgewidth=2,
      label=tr("last_window"),
   )

   fit_line, = ax_fit.plot(
      [], [],
      color="tab:orange",
      linewidth=2,
      label="K1 + Tavg * K2",
   )

   dev_line, = ax_fit.plot(
      [], [],
      color="tab:green",
      linewidth=2,
      alpha=0.7,
      label=tr("stored"),
   )

   drift_line_corr, = ax_drift.plot(
      [], [],
      color="tab:green",
      linewidth=2,
      label=tr("drift_corr_temp") if has_temp else tr("drift_corr_fixed"),
   )

   dtime_comp_line_corr, = ax_dtime_comp.plot(
      [], [],
      color="tab:blue",
      linewidth=2,
      label=tr("dtime2_temp") if has_temp else tr("dtime2_fixed"),
   )

   bat_line, = ax_bat.plot(
      [], [],
      color="tab:orange",
      linewidth=2,
      alpha=0.3,
      label=tr("battery"),
   )

   temp_line, = ax_temp.plot(
      [], [],
      color="tab:purple",
      linewidth=2,
      alpha=0.5,
      label=tr("cpu_temp"),
   )

   tavg_line, = ax_temp.plot(
      [], [],
      color="tab:blue",
      linewidth=1.5,
      linestyle="--",
      label=tr("cpu_temp_avg"),
   )

   info_head = ax_info.text(
      0.015, 0.95,
      tr("info_head_temp") if has_temp else tr("info_head_fixed"),
      transform=ax_info.transAxes, va="top", ha="left",
      fontsize=12, fontweight="bold", color="#12355b",
   )

   info_hw = ax_info.text(
      0.985, 0.95,
      tr("hw_temp") if has_temp else tr("hw_fixed", v=hw_info["version"]),
      transform=ax_info.transAxes, va="top", ha="right",
      fontsize=9, fontweight="bold", color="#555555" if has_temp else "#b45f06",
   )

   info_vals = ax_info.text(
      0.015, 0.78,
      "",
      transform=ax_info.transAxes, va="top", ha="left",
      family="monospace", fontsize=15, fontweight="bold", color="#0b5d1e",
   )

   info_now = ax_info.text(
      0.015, 0.58,
      "",
      transform=ax_info.transAxes, va="top", ha="left",
      family="monospace", fontsize=11.5, fontweight="bold", color="#12355b",
   )

   info_text = ax_info.text(
      0.015, 0.40,
      tr("waiting"),
      transform=ax_info.transAxes, va="top", ha="left",
      family="monospace", fontsize=9.5, color="#333333",
   )

   # The info box rows are stacked top to bottom; fit_info() scales their fonts so that
   # everything fits into the box (height and width), whatever the window size is.
   info_rows = [info_head, info_vals, info_now, info_text]
   info_base_size = {info_head: 11.5, info_vals: 14, info_now: 11, info_text: 9, info_hw: 9}
   info_sig = [None]

   def fit_info(force=False):
      try:
         renderer = fig.canvas.get_renderer()
      except Exception:
         return   # backend without renderer access: keep the base sizes

      box = ax_info.get_window_extent(renderer)
      if box.width < 20 or box.height < 20:
         return

      sig = (tuple(t.get_text() for t in info_rows), info_hw.get_text(), round(box.width), round(box.height))
      if sig == info_sig[0] and not force:
         return
      info_sig[0] = sig

      px_per_pt = fig.dpi / 72.0
      pad = 6 * px_per_pt        # top / bottom padding
      gap = 3 * px_per_pt        # gap between the rows
      line = 1.25                # line height / font size
      margin_x = 0.03 * box.width   # left + right margin

      def row_heights():
         heights = []
         for t in info_rows:
            n = t.get_text().count("\n") + 1 if t.get_text() else 0
            heights.append(n * t.get_fontsize() * px_per_pt * line + (gap if n else 0))
         return heights

      scale = 1.0
      for _ in range(4):
         for t, base in info_base_size.items():
            t.set_fontsize(base * scale)
         need_h = 2 * pad + sum(row_heights())
         widest = max(t.get_window_extent(renderer).width for t in info_rows)
         head_row = info_head.get_window_extent(renderer).width + info_hw.get_window_extent(renderer).width + 0.03 * box.width
         need_w = max(widest, head_row) + margin_x
         factor = min(1.0, box.height / need_h, box.width / need_w)
         if factor >= 0.995:
            break
         scale = max(0.35, scale * factor * 0.98)

      y = pad
      for t, h in zip(info_rows, row_heights()):
         t.set_position((0.015, 1.0 - y / box.height))
         y += h

      fig.canvas.draw_idle()
   
   # configure the axes
   # 1st plot
   ax_drift.set_title(tr("title"), fontsize=20, fontweight="bold", pad=14)
   ax_drift.set_xlabel(tr("xlabel_time"))
   ax_drift.set_ylabel(tr("ylabel_drift"))
   ax_drift.grid(True, alpha=0.3)
   ax_drift.legend(loc="upper left")

   # 2nd plot
   ax_dtime_comp.set_xlabel(tr("xlabel_time"))
   ax_dtime_comp.set_ylabel(tr("ylabel_dtime"))
   ax_dtime_comp.grid(True, alpha=0.3)
   ax_dtime_comp.legend(loc="upper left")
   ax_dtime_comp.axhspan(-5, -2.5, color="yellow", alpha=0.3)
   ax_dtime_comp.axhspan(2.5, 5, color="yellow", alpha=0.3)
   ax_dtime_comp.axhspan(-2.5, 2.5, color="green", alpha=0.3)
   ax_dtime_comp.axhline(y=0, color='black', alpha=0.3, linestyle="--")

   if has_temp:
      ax_dtime_comp.set_title(tr("title2_temp"), fontsize=9)
   else:
      ax_dtime_comp.set_title(tr("title2_fixed"), fontsize=9)

   # 3rd plot
   if has_temp:
      ax_fit.set_title(tr("title3_temp", w=RATE_WINDOW_SECONDS), fontsize=9)
      ax_fit.set_xlabel(tr("xlabel3_temp"))
   else:
      ax_fit.set_title(tr("title3_fixed", w=RATE_WINDOW_SECONDS), fontsize=9)
      ax_fit.set_xlabel(tr("xlabel_time"))
   ax_fit.set_ylabel(tr("ylabel3"))

   # right axis: drift per hour that is compensated by the needed correction (left axis).
   # Same sign convention as plot 2: a positive correction (clock too fast) compensates a negative drift.
   ax_fit_right = ax_fit.secondary_yaxis(
      "right",
      functions=(
         lambda c: -S_PER_H_PER_TICK_PER_MIN * c,
         lambda d: -d / S_PER_H_PER_TICK_PER_MIN,
      ),
   )
   ax_fit_right.set_ylabel(tr("ylabel3_right"))
   ax_fit.grid(True, alpha=0.3)
   ax_fit.set_xlim(10, 40) if has_temp else ax_fit.set_xlim(0, 600)    # fixed start limits while there is no data (no autoscale -> no flicker)
   ax_fit.set_ylim(-5, 5)
   ax_fit.legend(loc="upper left", fontsize=8)

   # 4th plot
   ax_bat.set_xlabel(tr("xlabel_time"))
   ax_bat.set_ylabel(tr("ylabel_bat"))
   ax_bat.grid(True, alpha=0.3)
   ax_bat.legend(loc="lower left")

   ax_temp.set_ylabel(tr("ylabel_temp"))
   ax_temp.legend(loc="upper left")
   if not has_temp:
      ax_temp.set_visible(False)   # no temperature sensor available

   text_slow = ax_dtime_comp.text(0.02, -8, tr("too_fast"), transform=ax_dtime_comp.get_yaxis_transform(), ha="left", va="center", alpha=0.6, visible=False)
   text_fast = ax_dtime_comp.text(0.02, 8, tr("too_slow"), transform=ax_dtime_comp.get_yaxis_transform(), ha="left", va="center", alpha=0.6, visible=False)

   # Button: write K1/K2 into the device (green + clickable as soon as the data is reliable)
   BTN_GREY, BTN_GREEN, BTN_GREEN_HOVER = "lightgrey", "#7ed957", "#4cc22a"
   btn_what = "K1/K2" if has_temp else "K1"
   btn = Button(ax_btn, tr("btn_waiting", what=btn_what), color=BTN_GREY, hovercolor=BTN_GREY)
   btn.label.set_fontsize(9)
   btn.set_active(False)
   btn_state = {"ready": False, "msg": "", "msg_until": 0.0}

   def on_write(_event):
      with data.lock:
         fit_now = data.fit
      ok, _reason = fit_reliable(fit_now)
      if not ok:
         return
      k1_i, k2_i = to_device_values(fit_now["k1"], fit_now["k2"])
      try:
         r1, r2 = write_ardf_k1k2(port, k1_i, k2_i)
         if has_temp:
            btn_state["msg"] = tr("written_temp", r1=r1, k2=r2 / K2_SCALE, r2=r2)
         else:
            btn_state["msg"] = tr("written_fixed", r1=r1, v=hw_info["version"])
      except Exception as e:
         btn_state["msg"] = tr("write_error", e=e)
         print(f"Writing K1/K2 failed: {e!r}")
      btn_state["msg_until"] = time.time() + 6.0

   btn.on_clicked(on_write)

   btn_sig = [None]

   def set_button_label(raw):
      """Set the button text, wrapped and scaled (largest font that fits) for the narrow button."""
      try:
         renderer = fig.canvas.get_renderer()
      except Exception:
         btn.label.set_text(raw)
         return

      box = ax_btn.get_window_extent(renderer)
      sig = (raw, round(box.width), round(box.height))
      if sig == btn_sig[0] or box.width < 20 or box.height < 20:
         return
      btn_sig[0] = sig

      # keep values together while wrapping: non-breaking spaces in "K2 = -0.22", "< 2.0 K", "10 min"
      glued = re.sub(r"\b(\d+(?:\.\d+)?) ([A-Za-z°]+)\b", "\\1\u00a0\\2", raw)
      for op in ("=", "<", ">"):
         glued = glued.replace(f" {op} ", f"\u00a0{op}\u00a0")

      px_per_pt = fig.dpi / 72.0
      avail_w, avail_h = 0.92 * box.width, 0.90 * box.height
      for size in (11, 10, 9, 8, 7, 6.5, 6, 5.5, 5):
         cols = max(8, int(avail_w / (0.62 * size * px_per_pt)))   # ~0.62 em average character width
         wrapped = "\n".join(
            textwrap.fill(line, width=cols, break_long_words=(size == 5)) for line in glued.split("\n")
         )
         btn.label.set_fontsize(size)
         btn.label.set_text(wrapped)
         e = btn.label.get_window_extent(renderer)
         if e.width <= avail_w and e.height <= avail_h:
            break

   def update_button(fit_now):
      ready, reason = fit_reliable(fit_now)

      if time.time() < btn_state["msg_until"]:
         label = btn_state["msg"]
      elif ready:
         k1_i, k2_i = to_device_values(fit_now["k1"], fit_now["k2"])
         label = tr("btn_ready", what=btn_what, vals=fmt_device_values(k1_i, k2_i))
      else:
         label = tr("btn_notready", what=btn_what, reason=reason)

      set_button_label(label)

      if ready != btn_state["ready"]:
         btn_state["ready"] = ready
         btn.set_active(ready)
         btn.color = BTN_GREEN if ready else BTN_GREY
         btn.hovercolor = BTN_GREEN_HOVER if ready else BTN_GREY
         ax_btn.set_facecolor(btn.color)
         for sp in ax_info.spines.values():
            sp.set_edgecolor(INFO_EDGE_READY if ready else INFO_EDGE_IDLE)

   # the time axes of plots 1..3 are coupled: only plot 3 (bottom of the group) shows x tick labels and the x label
   for ax in (ax_drift, ax_dtime_comp):
      ax.tick_params(labelbottom=False)
      ax.set_xlabel("")

   #fig.tight_layout()

   form_cache = {"key": None, "dt": None}
   rate_cache = {"n": -1, "x": np.array([]), "y": np.array([]), "t": np.array([])}
   fit_legend_key = [None]

   def update(_frame):

      # copy the data under the lock, then draw outside of the lock
      with data.lock:
         t = np.array(data.elapsed, dtype=float) / 100.0    # -> seconds

         d = np.array(data.drift, dtype=float) / 100.0      # -> seconds
         raw_drift = np.array(data.drift, dtype=float)      # 10 ms ticks

         d_corr = np.array(data.drift_corr, dtype=float) / 100.0      # -> seconds
         dt_comp_corr = np.array(data.dtime_comp_corr, dtype=float)

         b = np.array(data.bat, dtype=float)
         temp = np.array(data.temp, dtype=float)
         tavg = np.array(data.tavg, dtype=float)
         fit = data.fit

         error = data.error

      if error is not None:
         ax_drift.set_title(tr("error", e=error), color="tab:red", fontsize=12, fontweight="bold", pad=14)

      update_button(fit)
      fit_info()

      if t.size == 0:
         return drift_line, dtime_form_line, text_fast, text_slow, drift_line_corr, dtime_comp_line_corr, fit_points, fit_last, fit_line, dev_line, bat_line, temp_line

      # drift with the current correction formula: whenever K1/K2 (or the data) change,
      # the complete line is recalculated and redrawn
      if fit is not None and fit["valid"] and t.size >= 2:
         key = (fit["k1"], fit["k2"], t.size)
         if form_cache["key"] != key:
            form_cache["key"] = key
            form_cache["dt"] = drift_with_formula(t, raw_drift, tavg, fit["k1"], fit["k2"])
         dt_form = form_cache["dt"]
      else:
         dt_form = np.full(t.size, np.nan)

      drift_line.set_data(t, d)
      dtime_form_line.set_data(t, np.round(dt_form, decimals=1))
      bat_line.set_data(t, b)
      temp_line.set_data(t, temp)
      tavg_line.set_data(t, tavg)

      fit_valid = fit is not None and fit["valid"]
      lines = []
      u_tpm = tr("unit_tpm")
      u_tpmk = tr("unit_tpmk")

      if fit_valid and not has_temp:
         # device without temperature sensor: fixed offset K1 only
         info_vals.set_text(
            f"K1 = {fit['k1']:+.3f}"
            + (f" ± {fit['k1_err']:.3f}" if not np.isnan(fit['k1_err']) else "")
            + f" {u_tpm}"
         )
         info_now.set_text(tr("now_fixed", k1=int(np.round(fit["k1"])), u=u_tpm))
         lines.append(tr("basis_fixed", n=fit["n"], m=fit["span_s"] / 60.0))
      elif fit_valid:
         info_vals.set_text(
            f"K1 = {fit['k1']:+.4f} {u_tpm}      "
            f"K2 = {fit['k2']:+.4f}"
            + (f" ± {fit['k2_err']:.4f}" if not np.isnan(fit['k2_err']) else "")
            + f" {u_tpmk}"
         )
         info_now.set_text(
            tr("now_temp", tavg=fit["tavg_now"], c=fit["corr_now"], u=u_tpm, r=int(np.round(fit["corr_now"])))
         )
         lines.append(
            tr("basis_temp", tmin=fit["tmin"], tmax=fit["tmax"], span=fit["tmax"] - fit["tmin"],
               n=fit["n"], m=fit["span_s"] / 60.0, avg=TEMP_AVG_SECONDS)
         )
      else:
         info_vals.set_text("")
         info_now.set_text("")
         lines.append(tr("waiting_detail", p=MIN_FIT_POINTS, s=MIN_FIT_SECONDS))

      if device_params["k1"] is not None and not has_temp:
         lines.append(tr("dev_fixed", k1=device_params["k1"], u=u_tpm, v=hw_info["version"]))
      elif device_params["k1"] is not None and device_params["k2_raw"] is not None:
         lines.append(
            tr("dev_temp", k1=device_params["k1"], u=u_tpm, k2=device_params["k2_raw"] / K2_SCALE,
               uk=u_tpmk, raw=device_params["k2_raw"])
         )

      if fit_valid and has_temp:
         lines.append(tr("extrapolation"))
         if not fit["with_temp"]:
            lines.append(tr("warn_span", r=MIN_TEMP_RANGE))

      info_text.set_text("\n".join(lines))
      fit_info()

      drift_line_corr.set_data(t, d_corr)
      dtime_comp_line_corr.set_data(t, np.round(dt_comp_corr, decimals=1))
      # 3rd plot: drift rate per time block over temperature + correction line
      if rate_cache["n"] != t.size:
         rate_cache["n"] = t.size
         rate_cache["x"], rate_cache["y"], rate_cache["t"] = rate_vs_temperature(t, raw_drift, tavg, RATE_WINDOW_SECONDS)

      # x axis: averaged temperature (HW with sensor) or time (HW without sensor)
      rx = rate_cache["x"] if has_temp else rate_cache["t"]
      ry = rate_cache["y"]
      fit_points.set_data(rx, ry)
      fit_last.set_data(rx[-1:], ry[-1:])

      # x range of the lines: seen temperature range of the fit, otherwise range of the dots
      tt = None
      if not has_temp:
         tt = np.array([float(t[0]), float(t[-1])])      # offset K1 is a horizontal line over the whole measuring time
      elif fit is not None and fit["valid"]:
         tt = np.array([fit["tmin"], fit["tmax"]])
      elif rx.size > 0:
         tt = np.array([rx.min(), rx.max()])
      if tt is not None and tt[1] - tt[0] < 1e-6:
         tt = tt + np.array([-0.5, 0.5])

      # values stored in the device (K2 is stored in 1/100)
      dev_k1 = device_params["k1"]
      if not has_temp:
         dev_k2 = 0.0                    # HW 1/2: no K2
      else:
         dev_k2 = None if device_params["k2_raw"] is None else device_params["k2_raw"] / K2_SCALE

      fit_ok = fit is not None and fit["valid"]
      dev_ok = tt is not None and dev_k1 is not None and dev_k2 is not None

      # computed line (from the measured data)
      if fit_ok:
         fit_line.set_data(tt, fit["k1"] + fit["k2"] * tt)
      else:
         fit_line.set_data([], [])

      # line of the values stored in the device
      if dev_ok:
         dev_line.set_data(tt, dev_k1 + dev_k2 * tt)
      else:
         dev_line.set_data([], [])

      # legend texts: formula evaluated at the current Tavg; the legend is only rebuilt when a text changes
      tavg_now = float(tavg[-1])
      fit_label = None
      dev_label = None
      if fit_ok and not has_temp:
         fit_label = tr("fit_label_fixed", k1=fit["k1"])
      elif fit_ok:
         op = "-" if fit["k2"] < 0 else "+"
         fit_label = (
            f"{fit['k1']:+.3f} {op} {abs(fit['k2']):.3f} * Tavg = {fit['k1'] + fit['k2'] * tavg_now:+.2f}"
            + tr("fit_range", a=fit["tmin"], b=fit["tmax"])
         )
      if dev_ok and not has_temp:
         dev_label = tr("dev_label_fixed", k1=dev_k1)
      elif dev_ok:
         op = "-" if dev_k2 < 0 else "+"
         dev_label = tr("dev_label_temp", k1=dev_k1, op=op, k2=abs(dev_k2), val=dev_k1 + dev_k2 * tavg_now)

      if fit_legend_key[0] != (fit_label, dev_label):
         fit_legend_key[0] = (fit_label, dev_label)
         if fit_label is not None:
            fit_line.set_label(fit_label)
         if dev_label is not None:
            dev_line.set_label(dev_label)
         ax_fit.legend(loc="upper left", fontsize=8)

      # limit the axes to the range of the drawn data (without data the start limits stay)
      xs_all = [rx]
      ys_all = [ry]
      if fit_ok:
         xs_all.append(tt)
         ys_all.append(fit["k1"] + fit["k2"] * tt)
      if dev_ok:
         xs_all.append(tt)
         ys_all.append(dev_k1 + dev_k2 * tt)
      xs_all = np.concatenate(xs_all)
      ys_all = np.concatenate(ys_all)
      if xs_all.size > 0:
         for lo_hi, setter, min_margin in (
            ((xs_all.min(), xs_all.max()), ax_fit.set_xlim, 0.5),
            ((ys_all.min(), ys_all.max()), ax_fit.set_ylim, 0.25),
         ):
            lo, hi = lo_hi
            margin = max(0.08 * (hi - lo), min_margin)
            setter(lo - margin, hi + margin)

      meddt_comp = np.nanmedian(dt_form) if np.any(~np.isnan(dt_form)) else np.nan
      meddt_comp_corr = np.nanmedian(dt_comp_corr) if np.any(~np.isnan(dt_comp_corr)) else np.nan
      
      if not np.isnan(meddt_comp) and 2 <= np.count_nonzero(~np.isnan(dt_form)):

         if meddt_comp > meddt_comp_corr:
            top = meddt_comp + np.nanstd(dt_form) * 2
            bottom = meddt_comp_corr - np.nanstd(dt_comp_corr) * 2
         else:
            top = meddt_comp_corr + np.nanstd(dt_comp_corr) * 2
            bottom = meddt_comp - np.nanstd(dt_form) * 2

         if top < 8:
            top = 8
         if bottom > -8:
            bottom = -8
         
         if np.isfinite(top) and np.isfinite(bottom) and top > bottom:
            ax_dtime_comp.set_ylim(bottom, top)
         
         ymin, ymax = ax_dtime_comp.get_ylim()
         if ymin <= -8 <= ymax:
            text_slow.set_visible(True)
         else:
            text_slow.set_visible(False)
         
         if ymin <= 8 <= ymax:
            text_fast.set_visible(True)
         else:
            text_fast.set_visible(False)


      for ax in (ax_drift, ax_dtime_comp, ax_bat, ax_temp):
         ax.relim()
         ax.autoscale_view()

      return drift_line, dtime_form_line, text_fast, text_slow, drift_line_corr, dtime_comp_line_corr, fit_points, fit_last, fit_line, dev_line, bat_line, temp_line

   # keep a reference, otherwise the animation is garbage-collected!
   anim = FuncAnimation(
      fig,
      update,
      interval=200,             # ms
      cache_frame_data=False,
      blit=False,               # required so that the axes rescale
   )

   thread.start()

   try:
      plt.show()                # blocks until the window is closed
   finally:
      stop_event.set()
      thread.join(timeout=3.0)

   if data.error is not None:
      raise data.error

   return anim



def natural_key(text):
   """Sort key that orders COM2 before COM10 and ttyUSB2 before ttyUSB10."""
   return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", text)]


def list_serial_ports():
   """
   Available serial ports on Linux and Windows (via pyserial).
   Returns a list of dicts (device, description, usb, label); USB ports come first.
   """
   from serial.tools import list_ports

   ports = []
   for info in list_ports.comports():
      usb = info.vid is not None
      text = info.description if info.description and info.description != "n/a" else ""
      if usb:
         text = f"{text} [USB {info.vid:04x}:{info.pid:04x}]".strip()
      ports.append({
         "device": info.device,
         "description": text,
         "usb": usb,
         "label": f"{info.device} - {text}" if text else info.device,
      })

   ports.sort(key=lambda p: (not p["usb"], natural_key(p["device"])))
   return ports


def default_port_choice(ports):
   """Preselected port for the chooser: /dev/ttyACM0 if present, else the first USB port, else the first port."""
   devices = [p["device"] for p in ports]
   if "/dev/ttyACM0" in devices:
      return "/dev/ttyACM0"
   usb = [p for p in ports if p["usb"]]
   if usb:
      return usb[0]["device"]
   return devices[0] if devices else None


def resolve_port_text(text, ports):
   """Combobox text -> device name: a listed label maps to its device, anything else is taken as typed."""
   text = text.strip()
   for p in ports:
      if text == p["label"]:
         return p["device"]
   return text


def ask_port_dialog(initial=None):
   """Small window with a drop-down of the available ports (editable, with Refresh). Returns the device or None."""
   import tkinter as tk
   from tkinter import ttk

   root = tk.Tk()
   root.title(tr("port_title"))
   root.resizable(False, False)

   state = {"ports": [], "result": None}
   text = tk.StringVar()
   status = tk.StringVar()

   def refresh(keep=None):
      state["ports"] = list_serial_ports()
      combo["values"] = [p["label"] for p in state["ports"]]
      wanted = keep or default_port_choice(state["ports"])
      for p in state["ports"]:
         if p["device"] == wanted:
            text.set(p["label"])
            break
      else:
         text.set(wanted or "")
      status.set(tr("port_found", n=len(state["ports"])) if state["ports"] else tr("port_none"))

   def connect(_event=None):
      value = resolve_port_text(text.get(), state["ports"])
      if value:
         state["result"] = value
         root.destroy()

   frame = ttk.Frame(root, padding=12)
   frame.grid(sticky="nsew")
   ttk.Label(frame, text=tr("port_hint")).grid(row=0, column=0, columnspan=2, sticky="w")
   ttk.Label(frame, text=tr("port_label")).grid(row=1, column=0, sticky="w", pady=(8, 0))
   combo = ttk.Combobox(frame, textvariable=text, width=60)
   combo.grid(row=1, column=1, sticky="ew", pady=(8, 0), padx=(6, 0))
   ttk.Label(frame, textvariable=status, foreground="#555555").grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))

   buttons = ttk.Frame(frame)
   buttons.grid(row=3, column=0, columnspan=2, sticky="e", pady=(10, 0))
   ttk.Button(buttons, text=tr("port_refresh"), command=lambda: refresh(resolve_port_text(text.get(), state["ports"]))).grid(row=0, column=0, padx=4)
   ttk.Button(buttons, text=tr("port_connect"), command=connect).grid(row=0, column=1, padx=4)
   ttk.Button(buttons, text=tr("port_cancel"), command=root.destroy).grid(row=0, column=2, padx=4)

   root.bind("<Return>", connect)
   root.bind("<Escape>", lambda _e: root.destroy())

   refresh(initial)
   combo.focus_set()
   root.mainloop()

   return state["result"]


def ask_port_console(ports):
   """Console fallback (no tkinter or no display): numbered list. Returns the device or None."""
   print("Available serial ports:")
   for i, p in enumerate(ports, 1):
      print(f"  {i}) {p['label']}")
   default = default_port_choice(ports)
   try:
      answer = input(f"Select port number or type a name [{default}]: ").strip()
   except EOFError:
      return None
   if not answer:
      return default
   if answer.isdigit() and 1 <= int(answer) <= len(ports):
      return ports[int(answer) - 1]["device"]
   return answer


def choose_port(force_dialog=False):
   """
   Automatic port detection: exactly one USB serial port -> use it; otherwise ask the user
   (dialog, or console fallback). Returns the device name or None if nothing was chosen.
   """
   ports = list_serial_ports()
   usb = [p for p in ports if p["usb"]]

   if len(usb) == 1 and not force_dialog:
      print(f"Using serial port {usb[0]['label']}")
      return usb[0]["device"]

   try:
      return ask_port_dialog(default_port_choice(ports))
   except Exception as e:   # tkinter missing, no display, ...
      print(f"Port dialog not available ({e!r}), using the console instead.")

   if not ports:
      print("No serial ports found. Connect the device and try again, or pass the port with -p.")
      return None

   return ask_port_console(ports)


def print_ports():
   """--list-ports: print the available serial ports."""
   ports = list_serial_ports()
   if not ports:
      print("No serial ports found.")
   for p in ports:
      print(f"{p['device']}\t{'USB' if p['usb'] else '   '}\t{p['description']}")


def open_radio(device):
   port = serial.Serial(
      port=device,
      baudrate=38400,
      bytesize=serial.EIGHTBITS,
      parity=serial.PARITY_NONE,
      stopbits=serial.STOPBITS_ONE,
      timeout=1.0,
      write_timeout=1.0,
   )

   port.reset_input_buffer()
   port.reset_output_buffer()

   return port


def main():
   global TEMP_AVG_SECONDS, MIN_TEMP_RANGE, RATE_WINDOW_SECONDS, RELIABLE_MAX_K2_ERR, RELIABLE_MAX_K1_ERR, LANG

   parser = argparse.ArgumentParser(
      description="Read/write UV-K5"
   )

   parser.add_argument(
      "-p",
      "--port",
      default=None,
      help="serial port, e.g. /dev/ttyACM0 or COM3 (default: detect automatically, ask if ambiguous)",
   )

   parser.add_argument(
      "--select-port",
      action="store_true",
      help="always show the port selection even if exactly one USB serial port was found",
   )

   parser.add_argument(
      "--list-ports",
      action="store_true",
      help="list the available serial ports and exit",
   )

   parser.add_argument(
      "--tavg",
      type=float,
      default=TEMP_AVG_SECONDS,
      help="averaging window of the temperature in seconds (default: %(default)s)",
   )

   parser.add_argument(
      "--min-trange",
      type=float,
      default=MIN_TEMP_RANGE,
      help="minimum temperature span in K from which K2 is fitted (default: %(default)s)",
   )

   parser.add_argument(
      "--rate-window",
      type=float,
      default=RATE_WINDOW_SECONDS,
      help="time block in seconds for one dot of the drift-rate plot (default: %(default)s)",
   )

   parser.add_argument(
      "--max-k2-err",
      type=float,
      default=RELIABLE_MAX_K2_ERR,
      help="max. uncertainty of K2 [ticks/min/degC] for the write button to turn green (default: %(default)s)",
   )

   parser.add_argument(
      "--max-k1-err",
      type=float,
      default=RELIABLE_MAX_K1_ERR,
      help="devices without temperature sensor: max. uncertainty of K1 [ticks/min] for the write button to turn green (default: %(default)s)",
   )

   parser.add_argument(
      "--lang",
      choices=("de", "en"),
      default=LANG,
      help="language of the GUI texts (default: %(default)s)",
   )

   args = parser.parse_args()

   RATE_WINDOW_SECONDS = args.rate_window
   RELIABLE_MAX_K2_ERR = args.max_k2_err
   RELIABLE_MAX_K1_ERR = args.max_k1_err
   LANG = args.lang
   TEMP_AVG_SECONDS = args.tavg
   MIN_TEMP_RANGE = args.min_trange

   if args.list_ports:
      print_ports()
      return

   device = args.port or choose_port(force_dialog=args.select_port)
   if not device:
      sys.exit(1)

   try:
      port = open_radio(device)
   except (serial.SerialException, OSError) as e:
      print(f"Cannot open serial port {device}: {e}")
      if getattr(e, "errno", None) == 13:       # permission denied / access denied
         if sys.platform.startswith("win"):
            print("Hint: the port is probably in use by another program - close it and try again.")
         else:
            print("Hint: the user must be allowed to use the port, e.g. 'sudo usermod -aG dialout $USER' (then log in again).")
      elif getattr(e, "errno", None) == 2:      # no such file / port
         print("Hint: this port does not exist - check the cable or run with --list-ports.")
      sys.exit(1)

   try:
      try:
         hello(port)
         read_ardf(port)
      except (TimeoutError, RuntimeError, serial.SerialException) as e:
         print(f"No valid answer from the device on {device}: {e}")
         print("Hint: wrong port, or the device is not a UV-Kx with the ARDF firmware, or it is switched off.")
         sys.exit(1)

      run_live_plot(port)

   finally:
      port.close()



if __name__ == "__main__":
   main()
   logfile.close()
