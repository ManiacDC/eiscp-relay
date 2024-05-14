"""UDP Server for EISCP discovery"""

import socket
import socketserver
from configparser import SectionProxy
from logging import Logger

from getmac import get_mac_address

from .constants import PORT
from .eiscp import build_eiscp_packet, extract_eiscp_message


class ThreadingUdpServerWithLogging(socketserver.ThreadingUDPServer):
    """Threading UDP Server with Logging"""

    logger: Logger
    config: SectionProxy

    def __init__(self, logger: Logger, config: SectionProxy, *args, **kwargs):
        self.logger = logger
        self.config = config
        super().__init__(*args, **kwargs)


class EiscpUDPRequestHandler(socketserver.BaseRequestHandler):
    """Request Handler for EISCP requests"""

    server: ThreadingUdpServerWithLogging

    mac = get_mac_address().replace(":", "")

    def handle(self):
        data: bytes = self.request[0]
        udp_socket: socket.socket = self.request[1]
        self.server.logger.debug("received data: %s", data)

        message = extract_eiscp_message(data, self.server.logger)

        if not message:
            self.server.logger.debug("message was not a ISCP message")
            return

        if message.startswith(b"!xECNQSTN"):
            response_command = f"!1ECN{self.server.config["model"]}/{PORT}/{self.server.config["regional_id"]}/{self.mac}".encode("ascii")
        else:
            self.server.logger.debug("not a valid message")
            return

        packet = build_eiscp_packet(response_command)

        result = udp_socket.sendto(packet, self.client_address)
        self.server.logger.debug("UDP sent result to %s: %s; %s", self.client_address, result, packet)
