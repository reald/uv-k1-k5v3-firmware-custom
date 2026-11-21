# UV-Kx ARDF Clock Drift Tool – User Guide

The clock of UV-Kx radios is not very precise. This leads to a heavy difference in time, 
shown fox cycle starts drifting away from the real fox cycle very soon. To compensate this correction factors
can be calculated. Hardware version 1 and 2 simply introduce a fixed number of tasks to be
added or removed every minute.
Hardware version 3 needs a temperature dependend factor, too. Both methods will archive good results.

This python tool calculates the needed correction factors and stores them into the radio.

> [!Note]
> If no timing is used (e.g. in ARDF="DF Simple" mode) clock correction is not necessary.


## Contents
1. [Preconditions](#preconditions)
1. [Installation](#installation)
1. [Quick start](#quick-start) 
1. [Calibration procedure](#calibration-procedure) 
1. [The display](#the-display)
1. [Command line options](#command-line-options)
1. [Troubleshooting](#troubleshooting)


---

## Preconditions

### Needed firmware versions
- UV-K5/6 Version 1: ARDF-v0.9
- UV-K5/6 Version 2: ARDF-V2-v0.6
- UV-K5/6 Version 3, UV-K1: ARDF-K5v3_K1-v0.6

... or newer ARDF firmware.

The tool automatically detects the connected hardware version and chooses the right compensation stategy (with or without temperature compensation).

 
---

## Installation

### Linux
1. Install python (3.8 or later)
1. Install tkinter

| Distribution | Command |
|---|---|
| Debian / Ubuntu | `sudo apt install python3-tk python3-venv` |
| Fedora | `sudo dnf install python3-tkinter` |
| Arch | `sudo pacman -S tk` |

1. Install libraries
   ```bash
   python -m venv ardfvenv
   ardfvenv/bin/pip install numpy matplotlib pyserial
   ```
1. Your user must be allowed to use serial ports. Add yourself to the `dialout` group (on Arch: `uucp`) and log in again:
  ```bash
  sudo usermod -aG dialout $USER
  ```
1. Run the tool: `ardfvenv/bin/python uvkx_ardf_clk_drift.py`



### Windows
No tool installation needed. Simply run the provided .exe file.

USB serial adapters may need a driver (CH340, CP210x or FTDI chips). The port appears as `COMx` in the Device Manager. Close every other program that uses the port.


---

## Calibration procedure

### UV-K5/6 hardware version 1 and 2

- Connect radio to PC using serial cable
- Run the tool
- Wait for about 1 hour
- Click on the button (should turn green after a while) in the lower right to store the calibration 
facor in the radio

Although the temperature dependency is not very high for these devices it is recommended to run the 
calibration at an ambient temperature roughly about as the temperatur at the intended use.


### UV-K5/6 hardware version 3 and UV-K1

- Place the radio in the fridge, cool it down to ca. 5 °C
- Take it out of the fridge
- Connect radio to PC using USB-C cable
- Run the tool
- Wait until the temperature becomes stable (ca. 60-90 min)
- Click on the button (should turn green after a while) in the lower right to store the calibration 
facors in the radio


---

## The display

The window contains four plots and, at the bottom, an information box with the write button next to it. 

### Plot 1 – Drift

* **Red:** drift of the uncorrected clock: PC time minus radio counter, in seconds. A rising line means the radio is too slow.
* **Green:** drift of the corrected clock (the correction active in the radio).


### Plot 2 – Drift in 1 hour

The drift expressed as seconds per hour, estimated from all data collected so far. The colored background marks the tolerance:

* **Green band:** within ±2.5 s/h
* **Yellow band:** between 2.5 and 5 s/h
* Labels *too slow* / *too fast* mark the outer regions

Two curves are shown:

* **Orange – new calculated formula:** the drift that would remain if the newly calculated formula had been applied to the recorded data.
* **Blue – active compensation in the radio:** the measured drift of the radio's own corrected clock. Because the compensation
is applied only every minute the first minutes are not very meaningful. Wait some minutes and observe the blue line at the right end of the
measured time span.


### Plot 3 – Battery voltage and temperature

* Internal temperature (solid) and the **averaged temperature** `Tavg` (dashed) that is used for the correction formula.
* Battery voltage of the radio.

On hardware without a temperature sensor only the battery voltage is shown.


### Plot 4 – Drift versus temperature

This plot shows how the correction formula is derived:

* **x axis:** averaged temperature `Tavg`.
* **left y axis:** needed correction in ticks per minute.
* **right y axis:** the drift per hour (in seconds) that this correction compensates. The scale is 1 tick/min = 0.6 s/h; the right axis 
runs in the opposite direction, because a positive correction compensates a negative drift.

Elements:

* **Blue dots:** the measured needed correction. Each dot is one time block (300 s by default, `--rate-window`).
* **Red ring:** the latest block.
* **Orange line:** the newly calculated formula `K1 + Tavg * K2`, drawn over the temperature range that has been seen. The legend shows the formula evaluated at the current temperature.
* **Green line (semi-transparent):** the formula stored in the radio

If the dots lie close to the orange line the linear model fits well. Start at a cool temperature (place radio in the fridge for an hour before measuring) and run the tool until the
radio does not heat up anymore (a bunch of blue dots close to each other). This normally takes 60-90 minutes depending on the ambient temperature. The greater the
measured temperature range the better the correction result.

On hardware without temperature sensor this plot shows the needed correction over time, with a horizontal line for the fixed offset `K1`.


### Information box

| Row | Content |
|---|---|
| Top left | The correction formula. |
| Top right | Detected hardware, for example *HW with temperature sensor (V3)* or *HW V2: no temperature sensor*. |
| Large green line | The current values `K1` and `K2` with the uncertainty (± one standard deviation) of `K2`. |
| Bold line | The current averaged temperature and the correction the formula gives for it, also rounded to whole ticks. |
| *Basis* | The data the formula is based on: **seen temperature range**, temperature span, number of data points, measuring time and averaging time. |
| *In device* | `K1` and `K2` currently stored in the radio. |
| Hint / warning | The formula is only valid inside the seen temperature range. A warning appears while the temperature span is too small for `K2`. |

The frame of the box is grey while the data is not reliable and turns **green** when it is. When the radio is still heating up just continue measuring
before writing the correction values to the device to get even better results.


### Button

The large button to the right of the information box is used to store the calibration data into the radio.

| State | Meaning |
|---|---|
| **Grey**, not clickable | The data is not reliable yet. The text names the reason. |
| **Green**, clickable | Reliable. The text shows the values that will be written, for example `K1 = -80, K2 = +1.45`. |

* The corrected clock of the radio is updated in steps (observed: about once a minute). The blue curve in plot 2 therefore needs several minutes to show the effect.
* The tool always writes the values as calculated at the moment of the click. You can keep measuring afterwards and write improved values later.
* The written values are stored permanently in the radio and survive switching off and on.


## Command line options

| Option | Default | Description |
|---|---|---|
| `-p`, `--port PORT` | automatic | Serial port, for example `/dev/ttyACM0` or `COM3`. Without this option the port is detected or selected in a dialog. |
| `--select-port` | off | Always show the port selection, even if exactly one USB serial port was found. |
| `--list-ports` | – | Print the available serial ports and exit. |
| `--lang {de,en}` | `en` | Language of the user interface (plots, information box, button, dialog). Console output is always English. |
| `--tavg SECONDS` | `60` | Averaging window of the temperature. |
| `--min-trange KELVIN` | `2.0` | Minimum seen temperature span before `K2` is fitted. With a smaller span only `K1` is fitted and `K2 = 0`. |
| `--rate-window SECONDS` | `300` | Length of the time block that forms one dot in the drift-versus-temperature plot. |
| `--max-k2-err VALUE` | `0.05` | Largest uncertainty of `K2` (ticks/min/°C, one standard deviation) for which the data counts as reliable. |
| `--max-k1-err VALUE` | `0.25` | Same for `K1` (ticks/min) on hardware without temperature sensor. |
| `-h`, `--help` | – | Show the built-in help. |


---

## Troubleshooting

| Problem | Cause and remedy |
|---|---|
| The tool starts but no window opens, or *tkinter* errors appear | `tkinter` is missing. See [Installation](#installation). |
| *Cannot open serial port … permission denied* (Linux) | Add your user to the `dialout` group, then log in again. |
| *Cannot open serial port* (Windows) | The port is used by another program or the radio is not connected. Close the other program or check the Device Manager. |
| The radio is not offered in the port dialog | Press **Refresh** after connecting. Check the cable and the driver. `--list-ports` shows what the system reports. |
| *No valid answer from the device* | Wrong port, radio switched off or the radio does not run the ARDF firmware. |
| The button stays grey | Read the reason on the button. Typical: too little temperature variation, or the measurement is still shorter than 10 minutes. |
| `K1` and `K2` change strongly although the temperature is constant | With a small temperature span the two values are strongly coupled; only their combination at the current temperature is well determined. Check the current correction in the bold line and wait for a larger temperature span. |
| The dots in plot 4 are far from the orange line | The internal temperature does not follow the oscillator closely (heating or cooling too fast). Repeat the measurement with slower temperature changes. |
| Text in the information box is very small | The window is small. Enlarge it. |

---
