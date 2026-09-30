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
    parser.addoption("--problems", action="store_true",
                     help="List every error GivTCP gives on each model, from the golden results")

def pytest_collection_modifyitems(session, config, items):
    # GIVTCP_TEST_REVERSE=1 runs the tests in reverse order, to check each result doesn't depend on earlier tests
    import os
    if os.environ.get("GIVTCP_TEST_REVERSE"):
        items.reverse()

def pytest_configure(config):
    golden.UPDATE = config.getoption("--update-golden")

def pytest_sessionfinish(session, exitstatus):
    golden.save()

def pytest_terminal_summary(terminalreporter, exitstatus, config):
    from harness import report
    write = terminalreporter.write_line
    if golden.CHANGES:
        terminalreporter.section("GivTCP behaviour changed from tests/golden (%d results)" % len(golden.CHANGES))
        by_model = {}
        for model, section, case, changes in golden.CHANGES:
            by_model.setdefault(model, []).append((section, case, changes))
        for model, results in sorted(by_model.items()):
            write(model)
            for section, case, changes in results:
                write("    %s / %s: %s%s" % (section, case, changes[0] if changes else "",
                                         " (+%d more)" % (len(changes) - 1) if len(changes) > 1 else ""))
        write("")
        write("If these changes are intended, record them with --update-golden and review the git diff of tests/golden.")
    if config.getoption("--problems"):
        grouped = report.problems(golden.all_files())
        terminalreporter.section("Errors GivTCP gives, from tests/golden (%d kinds)" % len(grouped))
        for line in report.format_problems(grouped):
            write(line)

@pytest.fixture(scope="session", autouse=True)
def sandbox():
    env.enter()

@pytest.fixture(scope="session")
def plants():
    return Plants()

@pytest.fixture(scope="session")
def api():
    return REST.giv_api.test_client()     # not in testing mode, so a route that raises gives the 500 a real caller gets
