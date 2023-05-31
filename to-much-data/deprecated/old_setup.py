#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
"""
Deployment script for staticDHCPd.
"""
# from distutils.core import setup
import os
import platform
import re
import sys
from setuptools import setup

# import staticdhcpdlib

setup(
    name="staticDHCPd",
    version="3.0.0-beta1",
    description="Highly customisable, static-lease-focused DHCP server",
    long_description=(
        "staticDHCPd is an extensively customisable, high-performance,"
        " RFC-spec-compliant DHCP server, well-suited to labs, LAN parties, home and"
        " small-office networks, and specialised networks of vast size."
        "\n\n"
        "It supports all major DHCP extension RFCs and features a rich, plugin-oriented"
        " web-interface, has a variety of modules, ranging from statistics-management"
        " to notification services to dynamic address-provisioning and"
        " network-auto-discovery."
        "\n\n"
        "Multiple backend databases are supported, from INI files to RDBMS SQL servers,"
        " with examples of how to write and integrate your own, such as a REST-JSON"
        " endpoint, simple enough to complete in minutes."
    ),
    author="Neil Tallim",
    author_email="neil.tallim@linux.com",
    license="GPLv3",
    url="https://github.com/flan/staticdhcpd",
    packages=[
        "staticdhcpdlib",
        "staticdhcpdlib.databases",
        "staticdhcpdlib.web",
    ],
    data_files=[
        (
            "/etc/staticDHCPd",
            [
                "conf/conf.py.sample",
            ],
        ),
        (
            "/etc/staticDHCPd/staticDHCPd_extensions",
            [
                "conf/extensions/HOWTO",
            ],
        ),
    ],
    scripts=[
        "staticDHCPd",
    ],
)
