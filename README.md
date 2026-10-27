# rhb-telemetry

> **Deprecated (October 2026).** This project is no longer used on the Red Hot
> Beverly and the repository is archived. Its static address, 192.168.1.8
> (`rhbtelemetry`), is marked retired in rhb-sensor-monitor's `config/network.txt`.
> The rig's vehicle telemetry is rhb-vehicle-telemetry, a separate project.

A Raspberry Pi Pico W with an HT16K33 seven segment display, on the rig WiFi:

- Listens for OSC on port 8888 and only receives, never sends.
- `/pressure` sets the left two digits and `/temperature` the right two;
  the display blinks while the bath is over 100, and faster while
  `/water_heater` is on.
- Reads its WiFi and address from `config_rhb.json` (or `config_home.json`),
  which are gitignored.

Runs MicroPython with `uosc` and `ht16k33segment`; `main.py` and
`rhb_pico_utils.py` go on the board.
