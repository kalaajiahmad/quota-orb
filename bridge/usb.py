import json
import time
import zlib

import serial
from serial.tools import list_ports


def discover_port():
    ports = [p.device for p in list_ports.comports() if p.vid == 0x10C4 and p.pid == 0xEA60]
    if len(ports) == 1:
        return ports[0]
    if not ports:
        raise OSError("No CP210x USB adapter found; reconnect the Heltec USB data cable")
    raise OSError("Several CP210x adapters found; select the Heltec with --port COMx")


def packet(frame, sequence):
    if len(frame) != 1024:
        raise ValueError("An OLED frame must contain 1024 bytes")
    crc = zlib.crc32(frame)
    return f"F {sequence} {crc:08x} {frame.hex()}\n".encode("ascii"), crc


class Display:
    def __init__(self, port=None):
        self.requested_port = port
        self.serial = None
        self.sequence = 0
        self.button_presses = 0
        self.last_ack = None
        self.port = None

    def read(self):
        raw = self.serial.readline(512)
        try:
            message = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            return {}
        if not isinstance(message, dict):
            return {}
        if message.get("type") == "button":
            self.button_presses += 1
        return message

    def connect(self):
        self.port = self.requested_port or discover_port()
        connection = serial.Serial()
        connection.port = self.port
        connection.baudrate = 115200
        connection.timeout = 0.15
        connection.write_timeout = 1
        # CP210x RTS/DTR control ESP32 reset/boot. Do not toggle on every reconnect.
        connection.dtr = False
        connection.rts = False
        connection.open()
        self.serial = connection
        try:
            deadline, next_ping = time.monotonic() + 5, 0
            while time.monotonic() < deadline:
                if time.monotonic() >= next_ping:
                    connection.write(b"\nPING\n")
                    next_ping = time.monotonic() + 0.5
                message = self.read()
                if message.get("type") == "hello":
                    if (message.get("protocol"), message.get("width"), message.get("height"), message.get("oled")) != (1, 128, 64, True):
                        raise OSError("Incompatible firmware or OLED did not acknowledge on I2C")
                    return message
            raise OSError("No Quota Orb firmware handshake; flash firmware first")
        except BaseException:
            self.close()
            raise

    def send(self, frame):
        self.sequence = self.sequence % 0xFFFFFFFF + 1
        data, crc = packet(frame, self.sequence)
        self.serial.write(data)
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            message = self.read()
            if message.get("type") == "nack" and message.get("seq") == self.sequence:
                raise OSError("OLED rejected framebuffer CRC")
            if message.get("type") == "ack" and message.get("seq") == self.sequence:
                if message.get("crc") != crc:
                    raise OSError("OLED acknowledged the wrong framebuffer CRC")
                self.last_ack = message
                return message
        raise OSError("OLED framebuffer acknowledgement timed out")

    def close(self):
        if self.serial:
            self.serial.close()
            self.serial = None
