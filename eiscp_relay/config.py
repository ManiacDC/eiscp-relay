"""reads configuration files for the relay"""

import configparser
from logging import Logger
from pathlib import Path


class ConfigError(Exception):
    """raised when a config error occurs"""


def get_config(logger: Logger):
    """gets the config"""
    config = configparser.ConfigParser()

    config_file = Path(".", "config.ini")

    if not config_file.exists():
        logger.error("%s not found!", config_file)
        raise ConfigError("config.ini not found!")

    config.read(config_file)
    if "DEFAULT" not in config:
        raise ConfigError("config missing 'DEFAULT' section")

    config_section = config["DEFAULT"]

    for key in ["model", "mode", "regional_id"]:
        if key not in config_section:
            raise ConfigError(f"config missing '{key}' in 'DEFAULT' section")

    if config_section["mode"] not in ("TCP", "Serial"):
        raise ConfigError("config must be TCP or Serial")

    if config_section["mode"] == "TCP":
        if not config_section.get("serial_server") or not config_section.get("serial_server_port"):
            raise ConfigError("serial_server and serial_server_port must be in 'DEFAULT' section when in TCP mode")

    elif not config_section.get("serial_port"):
        raise ConfigError("serial_port must be in 'DEFAULT' section when in Serial mode")

    return config_section
