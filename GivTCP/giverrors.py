"""Readable descriptions of the exception currently being handled, for log messages."""
import os
import sys
import traceback

_GIVTCP_DIR = os.path.dirname(os.path.abspath(__file__))
_APP_DIR = os.path.dirname(_GIVTCP_DIR)


def _isOwnCode(filename):
    path = os.path.abspath(filename)
    return path.startswith(_GIVTCP_DIR) or os.path.dirname(path) == _APP_DIR


def errDetail():
    """Describe the exception being handled as "Type: message (file:line)".

    The location is where the exception was raised. If that was inside a library, the last line of
    GivTCP's own code on the way is added too, eg. "TimeoutError: ... (client.py:1700, via write.py:160)".
    """
    etype, exc, tb = sys.exc_info()
    if etype is None:
        return "no exception"
    text = etype.__name__
    msg = str(exc)
    if msg:
        text += ": " + msg
    if tb is not None:
        frames = traceback.extract_tb(tb)
        raised = frames[-1]
        where = os.path.basename(raised.filename) + ":" + str(raised.lineno)
        if not _isOwnCode(raised.filename):
            own = [f for f in frames if _isOwnCode(f.filename)]
            if own:
                where += ", via " + os.path.basename(own[-1].filename) + ":" + str(own[-1].lineno)
        text += " (" + where + ")"
    return text
