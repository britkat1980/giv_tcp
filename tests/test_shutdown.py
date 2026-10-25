"""On SIGTERM (Home Assistant stopping the app), startup.py stops the processes it started and exits with 0, rather than
being killed by the signal (exit code 143, which the Supervisor reports as not shutting down cleanly)"""
import ast
import os
import signal
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(os.name == "nt", reason="needs POSIX signals")

def functions(*names):
    tree = ast.parse((ROOT / "startup.py").read_text(encoding="utf-8"))
    found = {n.name: ast.get_source_segment((ROOT / "startup.py").read_text(encoding="utf-8"), n)
             for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names}
    assert set(found) == set(names)
    return "\n\n".join(found[n] for n in names)

def test_sigterm_stops_children_and_exits_0(tmp_path):
    pidfile = tmp_path / "child.pid"
    script = tmp_path / "run.py"
    script.write_text(textwrap.dedent("""
        import logging, os, signal, subprocess, sys, time
        from datetime import datetime, timedelta
        selfRun, rqWorker, gunicorn = {}, {}, {}
        mqttBroker = nginx = None
        redis = {}
    """) + functions("childProcesses", "shutdown", "stopGunicorn") + textwrap.dedent(f"""

        signal.signal(signal.SIGTERM, shutdown)
        selfRun[1] = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        open({str(pidfile)!r}, "w").write(str(selfRun[1].pid))
        while True:
            try:
                time.sleep(60)
            except:          # the watchdog loop's bare except mustn't stop the exit
                pass
    """), encoding="utf-8")
    proc = subprocess.Popen([sys.executable, str(script)])
    for _ in range(100):
        if pidfile.exists() and pidfile.read_text():
            break
        time.sleep(0.05)
    child = int(pidfile.read_text())
    proc.send_signal(signal.SIGTERM)
    assert proc.wait(timeout=10) == 0
    time.sleep(0.2)
    with pytest.raises(ProcessLookupError):
        os.kill(child, 0)       # the read loop it started was stopped too
