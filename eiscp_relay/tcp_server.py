"""TCP Server for EISCP requests"""

import select
import socket
import socketserver
import threading
from logging import Logger
from typing import List

from .eiscp import extract_eiscp_header
from .iscp import IscpListener

# pylint: disable = protected-access


class ConnectionClosedException(Exception):
    """raised when connection is closed"""


class PerClientThreadingMixin:
    """Mix-in class to handle each request in a new thread."""

    logger: Logger

    # Decides how threads will act upon termination of the
    # main process
    daemon_threads = False
    # If true, server_close() waits until all non-daemonic threads terminate.
    block_on_close = True
    # Threads object
    # used by server_close() to wait for all threads completion.
    _threads = socketserver._NoThreads()

    sockets: List[socket.socket] = []

    def process_request_thread(self, request: socket.socket, client_address):
        """Same as in BaseServer but as a thread.

        In addition, exception handling is done here.

        """
        self.sockets.append(request)
        self.logger.info("client connected: %s", client_address)
        while True:
            ready = select.select([request], [], [], 0.2)[0]
            if ready:
                try:
                    self.finish_request(request, client_address)
                except (ConnectionClosedException, ConnectionResetError):
                    self.logger.debug("connection closed")
                    break
                except Exception:  # pylint: disable = broad-exception-caught
                    self.logger.debug("exception caught")
                    self.handle_error(request, client_address)
                    break
        self.logger.debug("shutting down request")
        self.sockets.remove(request)
        self.shutdown_request(request)
        self.logger.info("client disconnected: %s", client_address)

    def process_request(self, request, client_address):
        """Start a new thread to process the request."""
        if self.block_on_close:
            vars(self).setdefault("_threads", socketserver._Threads())
        self.logger.debug("STARTING NEW TCP SERVER THREAD")
        t = threading.Thread(target=self.process_request_thread, args=(request, client_address))
        t.daemon = self.daemon_threads
        self._threads.append(t)
        t.start()

    def server_close(self):
        """closes the server"""
        super().server_close()
        self._threads.join()


class ThreadingPerClientTcpServer(PerClientThreadingMixin, socketserver.TCPServer):
    """class that creates a thread per client rather than per request"""

    logger: Logger
    iscp_listener: IscpListener

    def __init__(self, logger: Logger, *args, **kwargs):
        self.logger = logger
        super().__init__(*args, **kwargs)


class EiscpRequestHandler(socketserver.BaseRequestHandler):
    """Request Handler for EISCP requests"""

    request: socket.socket

    server: ThreadingPerClientTcpServer

    def handle(self):
        sock = self.request

        header: bytes = b""

        while True:
            data = tcp_grab_bytes(sock, 1)
            if data == b"I":
                header += data
                break
            if not data:
                self.server.logger.debug("request did not begin with 'I'")
                return

        header += tcp_grab_bytes(sock, 15)

        header_data = extract_eiscp_header(header, self.server.logger)

        if not header_data:
            self.server.logger.debug("request did not have a valid header")
            return

        if header_data[0] > 16:
            # grab remaining header data
            tcp_grab_bytes(sock, header_data[0] - 16)

        message = tcp_grab_bytes(sock, header_data[1])

        if not message:
            self.server.logger.debug("request did not contain data segment")
            return

        while message.endswith(b"\r") or message.endswith(b"\n"):
            message = message[:-1]

        self.server.logger.debug("request message was %s", message)

        if not message.startswith(b"!1"):
            self.server.logger.debug("request message did not begin with !1")
            return

        if message:
            try:
                self.server.iscp_listener.send_message_to_receiver(message)
            except Exception:  # pylint: disable=broad-exception-caught
                self.server.logger.exception("Unable to send message to receiver")


def tcp_grab_bytes(sock: socket.socket, num_bytes: int):
    """grabs num_bytes bytes from tcp buffer"""
    data = b""
    for _ in range(num_bytes):
        ready = select.select([sock], [], [], 1)[0]
        if ready:
            data += sock.recv(1)
        else:
            # timeout hit, did not receive expected bytes
            return None
    return data
