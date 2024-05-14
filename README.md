# Introduction

This script relays eISCP commands to serial-based (ISCP) Onkyo receivers. It will relay responses from the receiver back to the client.

This idea was heavily inspired by cl0rm's eiscp bridge https://github.com/cl0rm/eiscp_bridge, but I wanted a solution that did not require custom hardware.

# Supported Connection Methods

The script supports connecting to the receiver via a serial port or a TCP-based serial server. I use a [NB114](https://www.cdebyte.com/products/NB114) serial server, it cost about $15-20 on Aliexpress (note, if using this device, you must use a null modem cable to connect to the receiver).

# Configuration

A config.ini in the root of the repository can be modified to configure the script.

## Model

The model defines the name of your receiver sent to the client. You can set this to your actual receiver name; but certain programs, such as MyAV, have a hardcoded whitelist of receivers. It's likely better to use an old networked receiver.

## Mode

This can be TCP (for a serial server such as the NB114) or Serial (computer to receiver) depending on your preferred connection method.

## Serial Port

If in Serial mode, the system name of the serial port. On Windows, this will be something like "COM3". On Linux, it will be like "/dev/ttyUSB0".

## Serial Server & Serial Server Port

If in TCP mode, this should be the IP address and port of the Serial server.

# Installing dependencies

To install dependencies needed to run the script:
`pip install -r requirements.txt`

If you also want to install tools for development:
`pip install -r requirements.txt -r requirements-dev.txt`

# Running the script

This is designed to be run as a module, so from the root of the repository, you should run:
`python -m eiscp_relay`

# Running as a service

## Linux

I used this guide to set up the server on Linux (skip to section `Running a Linux daemon`):
https://oxylabs.io/blog/python-script-service-guide

Basically:

 * Create a file named `eiscp_relay.service` in `/etc/systemd/system`
 * Update the file as below
 * Run `systemctl daemon-reload`
 * Run `systemctl start eiscp_relay`
 * Check that it's running: `systemctl status eiscp_relay`


I used miniconda to install python, and created a python 3.12 environment. My `eiscp_relay.service` file looks something like this:

```
[Unit]
Description=Runs eiscp-relay server
After=syslog.target network.target

[Service]
WorkingDirectory=/home/user/eiscp-relay
ExecStart=/home/user/miniconda3/envs/eiscp_env/bin/python -m eiscp_relay

Restart=always
RestartSec=120

[Install]
WantedBy=multi-user.target
```

## Windows

I would recommend setting up the service using [nssm](https://nssm.cc). I would recommend setting up a miniconda environment with python 3.12 and using that to run the script.
