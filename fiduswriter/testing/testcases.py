from builtins import map
from builtins import range
import errno
import os
import socket
import threading
import logging

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromiumService
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.utils import ChromeType

from django.test import Client
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import connections
from django.test.testcases import TransactionTestCase

from tornado.ioloop import IOLoop
from tornado.platform.asyncio import AnyThreadEventLoopPolicy
from asyncio import set_event_loop_policy

from base.servers.tornado_django_hybrid import make_tornado_server


set_event_loop_policy(AnyThreadEventLoopPolicy())


logger = logging.getLogger(__name__)


class LiveTornadoThread(threading.Thread):
    """
    Thread for running a live http server while the tests are running.
    """

    def __init__(
        self, host, possible_ports, static_handler, connections_override=None
    ):
        self.host = host
        self.port = None
        self.possible_ports = possible_ports
        self.is_ready = threading.Event()
        self.error = None
        self.static_handler = static_handler
        self.connections_override = connections_override
        super().__init__()

    def run(self):
        """
        Sets up the live server and databases, and then loops over handling
        http requests.
        """
        if self.connections_override:
            # Override this thread's database connections with the ones
            # provided by the main thread.
            for alias, conn in list(self.connections_override.items()):
                connections[alias] = conn
        try:
            self.httpd = make_tornado_server()

            # Go through the list of possible ports, hoping that we can find
            # one that is free to use for the WSGI server.
            for index, port in enumerate(self.possible_ports):
                try:
                    self.httpd.listen(int(port))
                except socket.error as e:
                    if (
                        index + 1 < len(self.possible_ports)
                        and e.errno == errno.EADDRINUSE
                    ):
                        # This port is already in use, so we go on and try with
                        # the next one in the list.
                        continue
                    else:
                        # Either none of the given ports are free or the error
                        # is something else than "Address already in use". So
                        # we let that error bubble up to the main thread.
                        raise
                else:
                    # A free port was found.
                    self.port = port
                    break

            self.is_ready.set()
            self.ioloop = IOLoop.current()
            self.ioloop.start()
        except Exception as e:
            self.error = e
            self.is_ready.set()
            raise

    def terminate(self):
        if hasattr(self, "httpd"):
            self.httpd.stop()

        if hasattr(self, "ioloop"):
            self.ioloop.stop()


class LiveTornadoTestCase(TransactionTestCase):
    """
    Does basically the same as TransactionTestCase but also launches a live
    http server in a separate thread so that the tests may use another testing
    framework, such as Selenium for example, instead of the built-in dummy
    client.
    Note that it inherits from TransactionTestCase instead of TestCase because
    the threads do not share the same transactions (unless if using in-memory
    sqlite) and each thread needs to commit all their transactions so that the
    other thread can see the changes.
    """

    static_handler = None
    live_server_url = None

    @classmethod
    def setUpClass(cls):
        settings.TESTING = True
        connections_override = {}
        for conn in connections.all():
            # If using in-memory sqlite databases, pass the connections to
            # the server thread.
            if conn.vendor == "sqlite" and conn.is_in_memory_db():
                # Explicitly enable thread-shareability for this connection
                conn.inc_thread_sharing()
                connections_override[conn.alias] = conn

        # Launch the live server's thread
        specified_address = os.environ.get(
            "DJANGO_LIVE_TEST_SERVER_ADDRESS", "localhost:8081-8140"
        )
        # The specified ports may be of the form '8000-8010,8080,9200-9300'
        # i.e. a comma-separated list of ports or ranges of ports, so we break
        # it down into a detailed list of all possible ports.
        possible_ports = []
        try:
            host, port_ranges = specified_address.split(":")
            for port_range in port_ranges.split(","):
                # A port range can be of either form: '8000' or '8000-8010'.
                extremes = list(map(int, port_range.split("-")))
                assert len(extremes) in [1, 2]
                if len(extremes) == 1:
                    # Port range of the form '8000'
                    possible_ports.append(extremes[0])
                else:
                    # Port range of the form '8000-8010'
                    for port in range(extremes[0], extremes[1] + 1):
                        possible_ports.append(port)
        except Exception:
            msg = 'Invalid address ("%s") for live server.' % specified_address
            raise ImproperlyConfigured(msg)

        cls.server_thread = LiveTornadoThread(
            host,
            possible_ports,
            cls.static_handler,
            connections_override=connections_override,
        )
        cls.server_thread.daemon = True
        cls.server_thread.start()

        # Wait for the live server to be ready
        cls.server_thread.is_ready.wait()
        if cls.server_thread.error:
            # Clean up behind ourselves, since tearDownClass won't get called
            # in case of errors.
            cls._tearDownClassInternal()
            raise cls.server_thread.error

        cls.live_server_url = "http://%s:%s" % (
            cls.server_thread.host,
            cls.server_thread.port,
        )

        super().setUpClass()

    @classmethod
    def _tearDownClassInternal(cls):
        # There may not be a 'server_thread' attribute if setUpClass() for some
        # reasons has raised an exception.
        if hasattr(cls, "server_thread"):
            # Terminate the live server's thread
            cls.server_thread.terminate()
        # Restore sqlite connections' non-shareability
        for conn in connections.all():
            if (
                conn.vendor == "sqlite"
                and conn.settings_dict["NAME"] == ":memory:"
            ):
                conn.allow_thread_sharing = False

    @classmethod
    def tearDownClass(cls):
        cls._tearDownClassInternal()
        super().tearDownClass()

    @classmethod
    def get_drivers(cls, number, download_dir=False, user_agent=False):
        # django native clients, to be used for faster login.
        clients = []
        for i in range(number):
            clients.append(Client())
        drivers = []
        wait_time = 0
        options = webdriver.ChromeOptions()
        if download_dir:
            prefs = {
                "download.default_directory": download_dir,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
            }
            options.add_experimental_option("prefs", prefs)
        if user_agent:
            options.add_argument("user-agent={}".format(user_agent))
        if os.getenv("CI"):
            options.binary_location = "/usr/bin/google-chrome-stable"
            options.add_argument("--headless=new")
            options.add_argument("--disable-gpu")
            wait_time = 20
        else:
            wait_time = 6
        for i in range(number):
            driver = webdriver.Chrome(
                service=ChromiumService(
                    ChromeDriverManager(
                        chrome_type=ChromeType.GOOGLE
                    ).install()
                ),
                options=options,
            )
            drivers.append(driver)
        for driver in drivers:
            # Set sizes of browsers so that all buttons are visible.
            driver.set_window_position(0, 0)
            driver.set_window_size(1920, 1080)
        cls.drivers = drivers
        return {"clients": clients, "drivers": drivers, "wait_time": wait_time}

    def tearDown(self):
        # Source: https://stackoverflow.com/a/39606065
        if hasattr(self._outcome, "errors"):
            # Python 3.4 - 3.10  (These two methods have no side effects)
            result = self.defaultTestResult()
            self._feedErrorsToResult(result, self._outcome.errors)
        else:
            # Python 3.11+
            result = self._outcome.result
        ok = all(
            test != self for test, text in result.errors + result.failures
        )
        if not ok:
            if not os.path.exists("screenshots"):
                os.makedirs("screenshots")
            for id, driver in enumerate(self.drivers, start=1):
                screenshotfile = (
                    f"screenshots/driver{id}-{self._testMethodName}.png"
                )
                logger.info(f"Saving {screenshotfile}")
                driver.save_screenshot(screenshotfile)
                self.leave_site(driver)
        return super().tearDown()

    def leave_site(self, driver):
        driver.get("data:,")
