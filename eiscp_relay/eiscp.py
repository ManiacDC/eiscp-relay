"""houses eiscp functions"""

import struct
from logging import Logger

HEADER_SIZE = (16).to_bytes(4, "big")


def build_eiscp_packet(command: bytes):
    """builds an eiscp packet for the given command"""
    return struct.pack(
        f">4sIIcxxx{len(command)}sccc", b"ISCP", 16, len(command) + 3, b"1", command, b"\x1A", b"\r", b"\n"
    )


def extract_eiscp_message(data: bytes, logger: Logger):
    """extracts the message from an eiscp packet"""

    header_data = extract_eiscp_header(data, logger)

    if not header_data:
        return None

    header_size = header_data[0]
    data_size = header_data[1]

    return data[header_size : (header_size + data_size - 1)]


def extract_eiscp_header(header: bytes, logger: Logger):
    """extracts header data from an eiscp packet"""

    if not header.startswith(b"ISCP"):
        logger.debug("eISCP wrong beginning data: %s", header[:4])
        return

    header_size = int.from_bytes(header[4:8], "big")
    data_size = int.from_bytes(header[8:12], "big")

    return header_size, data_size
