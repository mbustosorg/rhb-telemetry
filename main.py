from machine import Pin, PWM, I2C
from time import sleep, time
import network

try:
    import socket
except ImportError:
    import usocket as socket

try:
    import logging
except ImportError:
    import uosc.fakelogging as logging

from uosc.server import handle_osc
from uosc.server import split_oscstr, parse_message

from ht16k33segment import HT16K33Segment

led = Pin("LED", Pin.OUT)
led.off()

log = logging.getLogger("uosc.minimal_server")
SSID = xxx
PASSWORD = xxx
MAX_DGRAM_SIZE = 1472

i2c = I2C(0, scl=Pin(17), sda=Pin(16))
devices = i2c.scan()
if devices:
    for d in devices:
        print(hex(d))

display = HT16K33Segment(i2c)
display.set_brightness(15)

wlan = network.WLAN(network.STA_IF)
wlan.active(True)


def toggle_startup_display(count):
    if count % 6 == 0:
        sync_text = b"\x01\x01\x01\x01"
    elif count % 6 == 1:
        sync_text = b"\x02\x02\x02\x02"
    elif count % 6 == 2:
        sync_text = b"\x04\x04\x04\x04"
    elif count % 6 == 3:
        sync_text = b"\x08\x08\x08\x08"
    elif count % 6 == 4:
        sync_text = b"\x10\x10\x10\x10"
    elif count % 6 == 5:
        sync_text = b"\x20\x20\x20\x20"
    for i in range(len(sync_text)):
        display.set_glyph(sync_text[i], i)
    display.draw()


def handle_osc(data, src, dispatch=None, strict=False):
    try:
        head, _ = split_oscstr(data, 0)
        if head.startswith('/'):
            messages = [(-1, parse_message(data, strict))]
        elif head == '#bundle':
            messages = parse_bundle(data, strict)
    except Exception as exc:
        if __debug__:
            log.debug("Exception Data: %r", data)
        return

    try:
        for timetag, (oscaddr, tags, args) in messages:
            bcd = int(str(int(args[0])), 16)

            if "pressure" in oscaddr:
                display.set_number((bcd & 0xF0) >> 4, 0)
                display.set_number((bcd & 0x0F), 1)
            elif "temperature" in oscaddr and "cpu" not in oscaddr:
                if int(args[0]) > 100:
                    display.set_blink_rate(1)
                else:
                    display.set_blink_rate(0)
                display.set_number((bcd & 0xF0) >> 4, 2)
                display.set_number((bcd & 0x0F), 3)
            display.draw()
            if __debug__:
                log.debug(f"{time()} OSC message : {oscaddr} {tags} {args}")

            if dispatch:
                dispatch(timetag, (oscaddr, tags, args, src))
    except Exception as exc:
        log.error("Exception in OSC handler: %s", exc)
        

def run_server(saddr, port, handler=handle_osc):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    ai = socket.getaddrinfo(saddr, port)[0]
    sock.bind(ai[-1])
    log.info("Listening for OSC messages on %s:%i", saddr, port)

    try:
        while True:
            data, caddr = sock.recvfrom(MAX_DGRAM_SIZE)
            if __debug__: log.debug("RECV %i bytes", len(data))
            handler(data, caddr)
    finally:
        sock.close()
        log.info("Bye!")


def connect_to_wifi():
    while True:
        wait = 2
        wlan.connect(SSID, PASSWORD)
        while wait < 12:
            status = wlan.status()
            if status >= 3:
                led.on()
                break
            toggle_startup_display(wait)
            wait += 1
            sleep(1)
        if wlan.status() != 3:
            print(f'network connection failed, retrying {wlan.status()}')
        else:
            print('connected')
            status = wlan.ifconfig()
            print('ip = ' + status[0] )
            break


while True:
    toggle_startup_display(1)
    connect_to_wifi()
    sync_text = b"\x40\x40\x40\x40"
    for i in range(len(sync_text)):
        display.set_glyph(sync_text[i], i)
    display.draw()
    #run_server("192.168.86.29", 8888)
    run_server("192.168.1.8", 8888) # RHB
