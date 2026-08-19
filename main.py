import json
from time import time

from machine import Pin, I2C

try:
    import socket
except ImportError:
    import usocket as socket

try:
    import asyncio
except ImportError:
    import uasyncio as asyncio

from uosc.server import split_oscstr, parse_message

from ht16k33segment import HT16K33Segment

from rhb_pico_utils import run_server, wifi_connection
import rhb_pico_utils


async def handle_osc(data, src, dispatch=None, strict=False):
    try:
        head, _ = split_oscstr(data, 0)
        if head.startswith('/'):
            messages = [(-1, parse_message(data, strict))]
        elif head == '#bundle':
            messages = parse_bundle(data, strict)
    except Exception as exc:
        if __debug__:
            print(f"Could not parse from {rhb_pico_utils.format_source(src)}: {exc} Data: {data}")
        return
    try:
        for timetag, (oscaddr, tags, args) in messages:

            # Receive only.  Match the exact addresses -- a substring test also
            # catches /water_pressure and /pressure_fine, which are not what
            # these digits show.
            if oscaddr == "/pressure":
                # Accumulator pressure, owned by rhb-sensor-monitor
                rhb_pico_utils.set_two_digits(args[0], 0, 1)
            elif oscaddr == "/temperature":
                # Water bath temperature, owned by rhb-water-heater
                if args[0] > 100:
                    rhb_pico_utils.display.set_blink_rate(1)
                else:
                    rhb_pico_utils.display.set_blink_rate(0)
                rhb_pico_utils.set_two_digits(args[0], 2, 3)
            elif oscaddr == "/water_heater":
                if round(args[0]):
                    rhb_pico_utils.display.set_blink_rate(2)
                else:
                    rhb_pico_utils.display.set_blink_rate(0)
            rhb_pico_utils.display.draw()
            if __debug__:
                print(f"{time()} OSC message from {rhb_pico_utils.format_source(src)} : {oscaddr} {tags} {args}")
            if dispatch:
                dispatch(timetag, (oscaddr, tags, args, src))
    except Exception as exc:
        print(f"Exception in OSC handler for {rhb_pico_utils.format_source(src)}: {exc}")


async def main_loop():
    """Main async loop"""
    try:
        print("Starting main loop...")
        server_task = asyncio.create_task(run_server(config["IP"], 8888, handle_osc))
        await server_task
    except:
        rhb_pico_utils.reboot()


if __name__ == "__main__":
    rhb_pico_utils.led = Pin("LED", Pin.OUT)
    rhb_pico_utils.led.off()
    with open("config_rhb.json") as f:
        config = json.load(f)

    i2c = I2C(0, scl=Pin(17), sda=Pin(16))
    devices = i2c.scan()
    if devices:
        for d in devices:
            print(f"I2C device found: {hex(d)}")
    rhb_pico_utils.display = HT16K33Segment(i2c)
    rhb_pico_utils.display.set_brightness(8)

    try:
        rhb_pico_utils.toggle_startup_display(1)
        wlan = wifi_connection(config)
        sync_text = b"\x40\x40\x40\x40"  # ----
        for i in range(len(sync_text)):
            rhb_pico_utils.display.set_glyph(sync_text[i], i)
        rhb_pico_utils.display.draw()
        asyncio.run(main_loop())
    except Exception as e:
        print(f"{e}")
        rhb_pico_utils.reboot()
    rhb_pico_utils.reboot()

