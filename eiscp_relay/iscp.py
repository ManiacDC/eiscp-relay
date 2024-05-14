"""sends iscp message to the receiver"""

import select
import socket
import time
from configparser import SectionProxy
from logging import DEBUG, WARNING, Logger
from typing import List

import serial

from .eiscp import build_eiscp_packet


class IscpListener:
    """listens for ISCP messages from receiver"""

    logger: Logger
    config: SectionProxy
    connected: bool
    client_sockets: List[socket.socket]

    def __new__(cls, logger: Logger, config: SectionProxy, *args, **kwargs):

        if cls == IscpListener:
            if config['mode'] == 'Serial':
                return IscpSerialListener(logger, config, *args, **kwargs)
            if config['mode'] == 'TCP':
                return IscpTcpListener(logger, config, *args, **kwargs)
            raise ValueError(f'invalid value for config mode: {config['mode']}')

        return object.__new__(cls)


    def __init__(self, logger: Logger, config: SectionProxy, client_sockets: List[socket.socket]):
        self.logger = logger
        self.config = config
        self.client_sockets = client_sockets
        self.connected = False

    def __exit__(self, _type, value, traceback):
        raise NotImplementedError('implement in subclass')

    def __enter__(self):
        raise NotImplementedError('implement in subclass')

    def _connect_to_receiver(self):
        raise NotImplementedError("implement in subclass")

    def _disconnect(self):
        raise NotImplementedError("implement in subclass")

    def listen_forever(self):
        """listens for ISCP messages from receiver"""

        while True:
            if not self.connected:
                try:
                    self._connect_to_receiver()
                except Exception:  # pylint: disable = broad-exception-caught
                    time.sleep(1)
                    continue
            try:
                ready = self.check_for_message()
                if ready:
                    message = self.get_message()
                    if message:
                        self.send_message_to_clients(message)
            except ConnectionResetError:
                self._disconnect()

    def send_message_to_clients(self, message):
        """sends message to all clients"""
        failed = 0
        try:
            self.logger.debug("sending message to %s clients: %s", len(self.client_sockets), message)
            if len(self.client_sockets) > 0:
                eiscp_message = build_eiscp_packet(message)
                for sock in self.client_sockets:
                    try:
                        sock.sendall(eiscp_message)
                    except Exception:  # pylint: disable = broad-exception-caught
                        failed += 1
        except Exception:  # pylint: disable = broad-exception-caught
            self.logger.exception("Unexpected failure sending messages to clients!")

        if failed > 0:
            self.logger.warning('Failed to send messages to %s clients', failed)

    def check_for_message(self):
        """checks for messages"""
        raise NotImplementedError("implement in subclass")

    def get_message(self):
        """receives data on a TCP socket and ensures it's terminated"""
        received_data = b""
        terminated = False
        found_message = False
        while self.check_for_message():
            data = self._get_one_byte()
            if not data:
                raise ConnectionResetError("connection closed")
            if data in (b"\r", b"\n", b"\x1A"):
                if found_message:
                    terminated = True
                    break
                continue
            if data == b"!":
                found_message = True
            received_data += data


        self.logger.log(DEBUG if terminated else WARNING, "total received %s, terminated %s", received_data, terminated)

        if terminated:
            return received_data

        return None

    def _get_one_byte(self):
        raise NotImplementedError("implement in subclass")

    def send_message_to_receiver(self, message: bytes):
        """sends a message to the receiver"""
        if not self.connected:
            self._connect_to_receiver()
        message = message + b"\r"
        try:
            self._send_message_to_receiver(message)
        except ConnectionResetError:
            self.logger.debug("not connected to receiver, trying again")
            time.sleep(1)
            self._disconnect()
            self._connect_to_receiver()
            self._send_message_to_receiver(message)

    def _send_message_to_receiver(self, message: bytes):
        raise NotImplementedError("implement in subclass")


class IscpTcpListener(IscpListener):
    """listens for TCP ISCP messages from receiver"""

    sock: socket.socket

    def __enter__(self):
        return self

    def __exit__(self, _type, value, traceback):
        self._disconnect()

    def _disconnect(self):
        """disconnects from the receiver"""
        if self.connected:
            self.sock.shutdown(socket.SHUT_RDWR)
            self.sock.close()
            self.sock = None
            self.connected = False
            self.logger.info('disconnected from receiver')

    def __init__(self, logger: Logger, config: SectionProxy, client_sockets: List[socket.socket]):
        self.sock = None
        super().__init__(logger, config, client_sockets)

    def _connect_to_receiver(self):
        try:
            if not self.sock:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.config["serial_server"], int(self.config["serial_server_port"])))
            self.logger.info(
                "Connected to receiver at: %s:%s", self.config["serial_server"], int(self.config["serial_server_port"])
            )
        except Exception as err:
            self.logger.exception(
                "unable to connect to serial server: %s:%s",
                self.config["serial_server"],
                int(self.config["serial_server_port"]),
            )
            raise err

        self.connected = True

    def check_for_message(self):
        """returns true if a message is ready"""
        return select.select([self.sock], [], [], 0.1)[0]

    def _get_one_byte(self):
        return self.sock.recv(1)

    def _send_message_to_receiver(self, message: bytes):
        self.sock.sendall(message)


class IscpSerialListener(IscpListener):
    """listens for Serial ISCP messages from receiver"""

    ser: serial.Serial

    def __enter__(self):
        return self

    def __exit__(self, _type, value, traceback):
        self._disconnect()

    def _disconnect(self):
        """disconnects from the receiver"""
        if self.connected and self.ser.is_open:
            self.ser.close()
            self.logger.info('disconnected from receiver')

    def __init__(self, logger: Logger, config: SectionProxy, client_sockets: List[socket.socket]):
        self.ser = None
        super().__init__(logger, config, client_sockets)

    def _connect_to_receiver(self):
        try:
            if not self.ser:
                self.ser = serial.Serial(self.config["serial_port"], 9600, timeout=0.1, write_timeout=0.5)
            if not self.ser.is_open:
                self.ser.open()
            self.logger.info("Connected to receiver at: %s", self.config["serial_port"])
        except Exception as err:
            self.logger.exception(
                "unable to connect to serial port: %s",
                self.config["serial_port"],
            )
            raise err

        self.connected = True

    def check_for_message(self):
        """returns true if a message is ready"""
        in_waiting = self.ser.in_waiting
        if in_waiting > 0:
            return True
        else:
            # implement timeout since in_waiting doesn't have one
            time.sleep(0.1)
            in_waiting = self.ser.in_waiting
            if in_waiting > 0:
                return True
        return False

    def _get_one_byte(self):
        return self.ser.read(1)

    def _send_message_to_receiver(self, message: bytes):
        self.ser.write(message)
