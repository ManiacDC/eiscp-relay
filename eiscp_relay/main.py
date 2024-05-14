"""main loop for EISCP TCP Relay"""

import logging
import sys
import threading
import time

from .config import get_config
from .constants import LOG_LEVEL, PORT
from .iscp import IscpListener
from .tcp_server import EiscpRequestHandler, ThreadingPerClientTcpServer
from .udp_server import EiscpUDPRequestHandler, ThreadingUdpServerWithLogging


def init_logging():
    """initializes logging"""

    logger = logging.getLogger()
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "[%(asctime)s,%(msecs)d %(levelname)s/%(module)s] : %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(LOG_LEVEL)

    return logger


def main_loop():
    """main loop for running the servers"""
    host = "0.0.0.0"

    logger = init_logging()

    config = get_config(logger)

    with (
        ThreadingPerClientTcpServer(logger, (host, PORT), EiscpRequestHandler) as tcp_server,
        ThreadingUdpServerWithLogging(logger, config, (host, PORT), EiscpUDPRequestHandler) as udp_server,
        IscpListener(logger, config, tcp_server.sockets) as iscp_listener,
    ):

        try:
            # set up iscp_listener so tcp_server has access
            tcp_server.iscp_listener = iscp_listener
            # Start a thread with the server -- that thread will then start one
            # more thread for each request
            tcp_server_thread = threading.Thread(target=tcp_server.serve_forever)
            # Exit the server thread when the main thread terminates
            tcp_server_thread.daemon = True
            tcp_server_thread.start()

            # Start a thread with the server -- that thread will then start one
            # more thread for each request
            udp_server_thread = threading.Thread(target=udp_server.serve_forever)
            # Exit the server thread when the main thread terminates
            udp_server_thread.daemon = True
            udp_server_thread.start()

            iscp_listener_thread = threading.Thread(target=iscp_listener.listen_forever)
            iscp_listener_thread.daemon = True
            iscp_listener_thread.start()

            while True:
                time.sleep(0.1)

            # client(host, PORT, build_eiscp_packet(b"!1ECNQSTN"))
        finally:
            tcp_server.shutdown()
            udp_server.shutdown()
