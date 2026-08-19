from time import sleep, ticks_ms

import machine
import network

try:
    import socket
except ImportError:
    import usocket as socket

try:
    import select
except ImportError:
    import uselect as select

try:
    import asyncio
except ImportError:
    import uasyncio as asyncio

display: HT16K33Segment = None
led: machine.Pin = None

MAX_DGRAM_SIZE = 6000
MINUS_GLYPH = 0x40


def reboot():
    """Reset the machine"""
    sleep(5)
    machine.reset()


def toggle_startup_display(count):
    """Indicate progress on the display"""
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


def set_two_digits(value, tens_digit, ones_digit):
    """Show `value' rounded to a whole number across two digits

    Senders broadcast floats, some of them unrounded, so round here rather
    than truncate. Only 0-99 fits in two digits: peg anything higher at 99
    (temperature blinks above 100 anyway) and show a leading minus below 0.
    """
    value = round(value)
    if value < -9:
        display.set_glyph(MINUS_GLYPH, tens_digit)
        display.set_glyph(MINUS_GLYPH, ones_digit)
        return
    if value < 0:
        display.set_glyph(MINUS_GLYPH, tens_digit)
        display.set_number(-value, ones_digit)
        return
    if value > 99:
        value = 99
    display.set_number(value // 10, tens_digit)
    display.set_number(value % 10, ones_digit)


def wifi_connection(config):
    """Connect to the wifi.

    The rig is statically addressed, so the address comes from the config
    rather than DHCP.  It has to match, because the OSC socket is bound to
    config["IP"] -- a lease handing out anything else leaves the socket
    listening on an address this device does not hold, and nothing arrives.
    """
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    # Power save lets the radio doze between beacons, which delays the ARP
    # reply the water heater's W5500 is waiting on and drops inbound UDP that
    # arrives while it is asleep.  This board is mains powered; keep it awake.
    try:
        wlan.config(pm=getattr(network.WLAN, "PM_NONE", 0xA11140))
    except Exception as e:
        print("Could not disable wifi power save:", e)
    if config.get("IP"):
        octets = config["IP"].split(".")
        gateway = config.get("GATEWAY") or ".".join(octets[:3] + ["1"])
        wlan.ifconfig(
            (
                config["IP"],
                config.get("NETMASK", "255.255.255.0"),
                gateway,
                config.get("DNS", gateway),
            )
        )
    while True:
        wait = 0
        wlan.connect(config["WIFI_SSID"], config["WIFI_PASSWORD"])
        while wait < 12:
            status = wlan.status()
            if status >= 3:
                break
            toggle_startup_display(wait)
            wait += 1
            sleep(1)
        if wlan.status() != 3:
            print(f'network connection failed, retrying {wlan.status()}')
        else:
            print('connected')
            status = wlan.ifconfig()
            print('ip = ' + status[0])
            break
    return wlan


def format_source(src):
    """Human readable `host:port' from a recvfrom() address

    lwip hands back an (ip, port) tuple, but fall back to the raw value so a
    packed sockaddr still logs something useful.
    """
    if isinstance(src, tuple):
        return f"{src[0]}:{src[1]}"
    return str(src)


async def run_server(saddr, port, handler):
    """Run the OSC Server asynchronously"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Bind every interface.  Binding the configured address instead means
        # that if this device ever comes up on a different one, the socket is
        # listening where no packet can reach it and the failure is silent.
        ai = socket.getaddrinfo("0.0.0.0", port)[0]
        sock.setblocking(False)
        sock.bind(ai[-1])
        p = select.poll()
        p.register(sock, select.POLLIN)
        poll = getattr(p, "ipoll", p.poll)

        print(f"Listening for OSC messages on 0.0.0.0:{port} (configured {saddr})")
        while True:
            try:
                for res in poll(1):
                    if res[1] & (select.POLLERR | select.POLLHUP):
                        print("UDPServer.serve: unexpected socket error.")
                        break
                    elif res[1] & select.POLLIN:
                        buf, addr = sock.recvfrom(MAX_DGRAM_SIZE)
                        asyncio.create_task(handler(buf, addr))
                led.toggle()
                await asyncio.sleep(0.0)
            except Exception as e:
                print(f"Exception in run_server: {e}")
                break
        sock.close()
    except Exception as e:
        print(f"Exception in run_server top: {e}")
