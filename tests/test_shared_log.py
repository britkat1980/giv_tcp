"""Several GivTCP processes write to the same log file. When one rotates it at midnight, the others must follow
the new file rather than keep writing to the renamed (and, 7 days later, deleted) one (#566).
Linux only: Windows can't rename or delete a file another handler has open (GivTCP runs on Linux)"""
import logging
import os

import pytest

from sharedlog import SharedTimedRotatingFileHandler

pytestmark = pytest.mark.skipif(os.name == "nt", reason="needs Linux file semantics")

def record(text):
    return logging.LogRecord("t", logging.INFO, __file__, 0, text, None, None)

def lines(path):
    return path.read_text().splitlines() if path.exists() else []

def handler(path):
    h = SharedTimedRotatingFileHandler(str(path), when="midnight", backupCount=7)
    h.setFormatter(logging.Formatter("%(message)s"))
    return h

def test_follows_file_rotated_by_another_process(tmp_path):
    log = tmp_path / "write_log_inv_1.log"
    first, second = handler(log), handler(log)      # eg. the read loop and the RQ worker
    first.emit(record("before"))
    second.emit(record("before too"))
    first.doRollover()                       # the first process to log after midnight rotates
    second.emit(record("after"))             # must land in the new file, not the rotated one
    first.emit(record("after too"))
    rotated = [p for p in tmp_path.iterdir() if p.name != log.name]
    assert lines(log) == ["after", "after too"]
    assert len(rotated) == 1 and lines(rotated[0]) == ["before", "before too"]

def test_second_rollover_in_same_period_does_not_rotate_again(tmp_path):
    log = tmp_path / "log_evc.log"
    first, second = handler(log), handler(log)
    first.emit(record("one"))
    first.doRollover()
    second.doRollover()                      # the other process reaches midnight too: it must not rotate again
    second.emit(record("two"))
    assert len([p for p in tmp_path.iterdir() if p.name != log.name]) == 1
    assert lines(log) == ["two"]

def test_reopens_deleted_file(tmp_path):
    log = tmp_path / "log_inv_1.log"
    h = handler(log)
    h.emit(record("one"))
    log.unlink()                             # eg. removed as an old backup while this process still had it open
    h.emit(record("two"))
    assert lines(log) == ["two"]
