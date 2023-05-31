#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
"""
staticDHCPd
===========
Highly customisable, static-lease-focused DHCP server.

Legal
-----
This file is part of staticDHCPd.
staticDHCPd is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>.

(C) Neil Tallim, 2021 <neil.tallim@linux.com>
"""
import logging
import logging.handlers
import os
import signal
import sys
import time
import traceback
import click
from pprint import pprint

import staticdhcpd
import staticdhcpd.config
import staticdhcpd.libpydhcpserver

# Options-processing needs to be done before config is loaded
# if __name__ == '__main__' and len(sys.argv) > 1:
#     import argparse
#
#     parser = argparse.ArgumentParser()
#     parser.add_argument("--config", help="specify the location of conf.py")
#     parser.add_argument("--debug", help="output logging information at the DEBUG level", action="store_true",
#                         default=False)
#     parser.add_argument("--verbose", help="disable daemon mode, if set, and enable console output", action="store_true",
#                         default=False)
#     parser.add_argument("--version", help="display version information", action="store_true", default=False)
#     args = parser.parse_args()
#     if args.version:
#         print("staticDHCPd v{} - {} | libpydhcpserver v{} - {}".format(
#             staticdhcpdlib.VERSION, staticdhcpdlib.URL,
#             libpydhcpserver.VERSION, libpydhcpserver.URL,
#         ))
#         sys.exit(0)
#     if args.config:
#         os.environ['STATICDHCPD_CONF_PATH'] = args.config
#     del parser
#     del argparse
# # Pre-config options-processing complete


_logger = logging.getLogger("main")


def gracefulShutdown():
    """
    Attempts to shut down the daemon cleanly on the first call, but ends the
    process if a second is made.
    """
    if staticdhcpd.system.ALIVE:
        _logger.warning("System shutdown beginning...")
        staticdhcpd.system.ALIVE = False
    else:
        _logger.warning("System shutting down immediately")
        sys.exit(1)


def termHandler(*args):
    """
    Cleanly shuts down this daemon upon receipt of a SIGTERM.
    """
    _logger.warning("Received SIGTERM")
    _gracefulShutdown()


def hupHandler(*args):
    """
    Reinitialises the system upon receipt of a SIGHUP.
    """
    _logger.warning("Received SIGHUP")
    staticdhcpd.system.reinitialise()


def daemonise():
    """
    The process of daemonising, the standard UNIX way.
    """
    print(os.fork())
    if os.fork():  # The first fork, to decouple stuff

        print("blub")
        sys.exit(0)
    os.setsid()  # Ensure session semantics are configured
    os.chdir("/")  # Avoid holding references to unstable resources

    print("blub")
    # And, lastly, clean up the base descriptors
    devnull = os.open("/dev/null", os.O_RDWR)
    os.dup2(devnull, sys.stdin.fileno())
    os.dup2(devnull, sys.stdout.fileno())
    os.dup2(devnull, sys.stderr.fileno())

    if os.fork():  # The second fork, to ensure TTY cannot be reacquired
        print("blub")
        sys.exit(0)


def setupLogging():
    """
    Attaches handlers to the root logger, allowing for universal access to
    resources.
    """
    logging.root.setLevel(logging.DEBUG)

    if staticdhcpd.config.DEBUG:
        formatter = logging.Formatter(
            "%(asctime)s : %(levelname)s : %(name)s:%(lineno)d[%(threadName)s] : %(message)s"
        )
    else:
        formatter = logging.Formatter("%(asctime)s : %(levelname)s : %(message)s")

    if (
        not staticdhcpd.config.DAEMON
    ):  # Daemon-style execution disables console-based logging
        if logging.root.handlers:
            _logger.info("Configuring console-based logging...")
        console_logger = logging.StreamHandler()
        console_logger.setLevel(
            getattr(logging, staticdhcpd.config.LOG_CONSOLE_SEVERITY)
        )
        console_logger.setFormatter(formatter)
        logging.root.addHandler(console_logger)
        _logger.info("Console-based logging online")

    if (
        staticdhcpd.config.LOG_FILE
    ):  # Determine whether disk-based logging is desired
        if logging.root.handlers:
            _logger.info(
                "Configuring file-based logging for {}...".format(
                    staticdhcpd.config.LOG_FILE
                )
            )
        if staticdhcpd.config.LOG_FILE_HISTORY:
            # Rollover once per day, keeping the configured number of days' logs as history
            file_logger = logging.handlers.TimedRotatingFileHandler(
                staticdhcpd.config.LOG_FILE,
                "D",
                1,
                staticdhcpd.config.LOG_FILE_HISTORY,
            )
            if logging.root.handlers:
                _logger.info(
                    "Configured rotation-based logging for file, with history={} days".format(
                        staticdhcpd.config.LOG_FILE_HISTORY
                    )
                )
        else:

            # Keep writing to the specified file forever
            file_logger = logging.FileHandler(staticdhcpd.config.LOG_FILE)
            if logging.root.handlers:
                _logger.info("Configured indefinite-growth logging for file")
        file_logger.setLevel(getattr(logging, staticdhcpd.config.LOG_FILE_SEVERITY))
        file_logger.setFormatter(formatter)
        logging.root.addHandler(file_logger)
        _logger.info("File-based logging online")

    if staticdhcpd.config.EMAIL_ENABLED:  # Add an SMTP handler
        smtp_handler = logging.handlers.SMTPHandler(
            (staticdhcpd.config.EMAIL_SERVER, staticdhcpd.config.EMAIL_PORT),
            staticdhcpd.config.EMAIL_SOURCE,
            staticdhcpd.config.EMAIL_DESTINATION,
            staticdhcpd.config.EMAIL_SUBJECT,
            credentials=(
                staticdhcpd.config.EMAIL_USER
                and (
                    staticdhcpd.config.EMAIL_USER,
                    staticdhcpd.config.EMAIL_PASSWORD,
                )
                or None
            ),
        )
        if logging.root.handlers:
            _logger.info(
                "Configured SMTP-based logging for {} via {}:{}".format(
                    staticdhcpd.config.EMAIL_DESTINATION,
                    staticdhcpd.config.EMAIL_SERVER,
                    staticdhcpd.config.EMAIL_PORT,
                )
            )
        smtp_handler.setLevel(logging.CRITICAL)
        smtp_handler.setFormatter(formatter)
        logging.root.addHandler(smtp_handler)
        _logger.info("SMTP-based logging online")


def initialise():
    """
    Loads and configures system components.
    """
    import staticdhcpd.system

    if staticdhcpdlib.config.WEB_ENABLED:
        _logger.info("Webservice module enabled; configuring...")
        import staticdhcpd.web
        import staticdhcpd.web.server

        webservice = staticdhcpd.web.server.WebService()
        webservice.start()

        import staticdhcpd.web.methods
        import staticdhcpd.web.headers

        staticdhcpd.web.registerHeaderCallback(
            staticdhcpd.web.headers.contentType
        )
        staticdhcpd.web.registerMethodCallback(
            "/javascript",
            staticdhcpd.web.methods.javascript,
            cacheable=(not staticdhcpd.config.DEBUG),
        )
        staticdhcpd.web.registerHeaderCallback(staticdhcpd.web.headers.javascript)

        if staticdhcpd.config.WEB_LOG_HISTORY > 0:
            _logger.info("Webservice logging module enabled; configuring...")
            web_logger = staticdhcpd.web.methods.Logger()
            staticdhcpd.web.registerDashboardCallback(
                "core",
                "events",
                web_logger.render,
                staticdhcpd.config.WEB_DASHBOARD_ORDER_LOG,
            )

        if staticdhcpd.config.WEB_REINITIALISE_ENABLED:
            staticdhcpd.web.registerMethodCallback(
                "/ca/uguu/puukusoft/staticDHCPd/reinitialise",
                staticdhcpd.web.methods.reinitialise,
                hidden=staticdhcpd.config.WEB_REINITIALISE_HIDDEN,
                module="core",
                name="reinitialise",
                secure=staticdhcpd.config.WEB_REINITIALISE_SECURE,
                confirm=staticdhcpd.config.WEB_REINITIALISE_CONFIRM,
                display_mode=staticdhcpd.web.WEB_METHOD_DASHBOARD,
            )

        if staticdhcpd.config.WEB_HEADER_TITLE:
            staticdhcpd.web.registerHeaderCallback(staticdhcpd.web.headers.title)

        if staticdhcpd.config.WEB_HEADER_CSS:
            staticdhcpd.web.registerMethodCallback(
                "/css",
                staticdhcpd.web.methods.css,
                cacheable=(not staticdhcpd.config.DEBUG),
            )
            staticdhcpd.web.registerHeaderCallback(staticdhcpd.web.headers.css)

        if staticdhcpd.config.WEB_HEADER_FAVICON:
            staticdhcpd.web.registerMethodCallback(
                "/favicon.ico",
                staticdhcpd.web.methods.favicon,
                cacheable=(not staticdhcpd.config.DEBUG),
            )
            staticdhcpd.web.registerHeaderCallback(
                staticdhcpd.web.headers.favicon
            )


def initialiseDHCP():
    """
    Loads and configures DHCP system components.
    """
    import staticdhcpdlib.system

    # Ready the database.
    import staticdhcpd.databases

    database = staticdhcpdlib.databases.get_database()
    staticdhcpdlib.system.registerReinitialisationCallback(database.reinitialise)

    # Start the DHCP server.
    import staticdhcpd.dhcp

    dhcp = staticdhcpdlib.dhcp.DHCPService(database)
    dhcp.start()
    staticdhcpdlib.system.registerTickCallback(dhcp.tick)


# if __name__ == '__main__':
#     if args and args.debug:
#         staticdhcpdlib.config.DEBUG = True
#         staticdhcpdlib.config.LOG_FILE_SEVERITY = 'DEBUG'
#         staticdhcpdlib.config.LOG_CONSOLE_SEVERITY = 'DEBUG'
#         print("staticDHCPd: Debugging overrides enabled: debugging operation requested")
#
#     if staticdhcpdlib.config.DAEMON:
#         if args and args.verbose:
#             staticdhcpdlib.config.DAEMON = False
#             print("staticDHCPd: Daemonised execution disabled: verbose operation requested")
#         else:
#             _daemonise()
#     del _daemonise
#
# del args  # No longer needed; allow reclamation

# parser = argparse.ArgumentParser()
# parser.add_argument("--config", help="specify the location of conf.py")
# parser.add_argument("--debug", help="output logging information at the DEBUG level", action="store_true",
#                     default=False)
# parser.add_argument("--verbose", help="disable daemon mode, if set, and enable console output", action="store_true",
#                     default=False)
# parser.add_argument("--version", help="display version information", action="store_true", default=False)


@click.command()
@click.option("--config", "-c", help="specify the location of conf.py")
@click.option(
    "--debug",
    "-c",
    is_flag=True,
    default=False,
    help="output logging information at the DEBUG level",
)
@click.option(
    "--verbose",
    is_flag=True,
    default=False,
    help="disable daemon mode, if set, and enable console output",
)
def cli(config, debug, verbose):
    # if args.version:
    #     print("staticDHCPd v{} - {} | libpydhcpserver v{} - {}".format(
    #         staticdhcpdlib.VERSION, staticdhcpdlib.URL,
    #         libpydhcpserver.VERSION, libpydhcpserver.URL,
    #     ))
    #     sys.exit(0)
    if config:
        os.environ["STATICDHCPD_CONF_PATH"] = config

    if debug:
        staticdhcpd.config.DEBUG = True
        staticdhcpd.config.LOG_FILE_SEVERITY = "DEBUG"
        staticdhcpd.config.LOG_CONSOLE_SEVERITY = "DEBUG"
        print("staticDHCPd: Debugging overrides enabled: debugging operation requested")

    if staticdhcpd.config.DAEMON:
        if verbose:
            staticdhcpd.config.DAEMON = False
            print(
                "staticDHCPd: Daemonised execution disabled: verbose operation requested"
            )
        else:
            pass
            daemonise()
    # del daemonise

    pprint(os.environ)

    setupLogging()
    # del _setupLogging
    for i in (
        "----------------------------------------",
        "----------------------------------------",
        "----------------------------------------",
        "System startup in progress; PID={}".format(os.getpid()),
        "staticDHCPd version {} : {}".format(
            staticdhcpd.VERSION, staticdhcpd.URL
        ),
        "libpydhcpserver version {} : {}".format(
            staticdhcpd.libpydhcpserver.VERSION, staticdhcpd.libpydhcpserver.URL
        ),
        "Continuing with subsystem initialisation",
        "----------------------------------------",
    ):
        _logger.warning(i)
    del i

    pidfile_recorded = False
    if staticdhcpd.config.PID_FILE:
        _logger.debug("Writing pidfile...")
        try:
            if os.path.isfile(staticdhcpd.config.PID_FILE):
                pidfile = open(staticdhcpd.config.PID_FILE, "r")
                _logger.warning(
                    "Pidfile already exists, with PID {}".format(pidfile.read().strip())
                )
                pidfile.close()

            pidfile = open(staticdhcpd.config.PID_FILE, "w")
            pidfile.write(str(os.getpid()) + "\n")
            pidfile.close()
            os.chown(
                staticdhcpd.config.PID_FILE,
                staticdhcpd.config.UID,
                staticdhcpd.config.GID,
            )
        except:
            _logger.error(
                "Unable to write pidfile: {}".format(staticdhcpd.config.PID_FILE)
            )
        else:
            pidfile_recorded = True

    try:
        # Set signal-handlers.
        signal.signal(signal.SIGHUP, hupHandler)
        _logger.debug("Installed SIGHUP handler")
        signal.signal(signal.SIGTERM, termHandler)
        _logger.debug("Installed SIGTERM handler")

        # Initialise all system resources
        initialise()

        _logger.info("Initialising custom code...")
        staticdhcpd.config.init()

        # Initialise the DHCP server
        initialiseDHCP()

        _logger.info(
            "Changing runtime permissions to UID={uid}, GID={gid}...".format(
                uid=staticdhcpd.config.UID,
                gid=staticdhcpd.config.GID,
            )
        )
        os.setregid(staticdhcpd.config.GID, staticdhcpd.config.GID)
        os.setreuid(staticdhcpd.config.UID, staticdhcpd.config.UID)

        # By this point, all extensions have had an opportunity to alias things
        # and configure themselves, so try to reclaim memory
        del staticdhcpd.config.conf.extensions

        _logger.warning("----------------------------------------")
        _logger.warning("All subsystems initialised; now serving")
        _logger.warning("----------------------------------------")
        sleep_offset = 0
        while staticdhcpd.system.ALIVE:
            time.sleep(max(0.0, 1.0 - sleep_offset))

            start_time = time.time()
            staticdhcpd.system.tick()
            sleep_offset = time.time() - start_time
    except KeyboardInterrupt:
        _logger.warning("System shutdown requested via keyboard interrupt")
    except Exception:
        _logger.critical(
            "System shutdown triggered by unhandled exception:\n{}".format(
                traceback.format_exc()
            )
        )
    finally:
        gracefulShutdown()
        if pidfile_recorded:
            _logger.debug("Unlinking pidfile...")
            try:
                os.unlink(staticdhcpd.config.PID_FILE)
            except:
                _logger.error(
                    "Unable to unlink pidfile: {}".format(
                        staticdhcpd.config.PID_FILE
                    )
                )
