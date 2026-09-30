import tempfile

import pytest

# Sandbox GivTCP before any of its modules are imported (they read settings and paths at import time)
from harness import env
env.bootstrap(tempfile.mkdtemp(prefix="givtcp_tests_"))

import HA_Discovery  # noqa: E402,F401  (imported so fakes.install() can patch it)
import mqtt  # noqa: E402,F401
import read  # noqa: E402
import REST  # noqa: E402
import write  # noqa: E402,F401
from harness import fakes, golden  # noqa: E402
from harness.plant import Plants  # noqa: E402

fakes.install()
read.WRITE_COMMAND_GAP = 0      # no need to spare a real dongle
REST.RESPONSE_TIMEOUT = 3       # an unhandled command fails in 3s rather than 15s

def pytest_addoption(parser):
    parser.addoption("--update-golden", action="store_true",
                     help="Record the current behaviour as the expected results in tests/golden/")

def pytest_configure(config):
    golden.UPDATE = config.getoption("--update-golden")

def pytest_sessionfinish(session, exitstatus):
    golden.save()

@pytest.fixture(scope="session", autouse=True)
def sandbox():
    env.enter()

@pytest.fixture(scope="session")
def plants():
    return Plants()

@pytest.fixture(scope="session")
def api():
    return REST.giv_api.test_client()     # not in testing mode, so a route that raises gives the 500 a real caller gets
