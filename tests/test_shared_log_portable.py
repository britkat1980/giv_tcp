"""Reopen/rollover behavior without POSIX open-file rename semantics."""
import logging
import os
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import sharedlog


@pytest.mark.parametrize('state', ['unchanged', 'replaced', 'deleted'])
def test_reopen_checks_file_identity(monkeypatch, tmp_path, state):
    handler = sharedlog.SharedTimedRotatingFileHandler(tmp_path / 'shared.log', delay=True)
    previous, replacement = Mock(), Mock()
    handler.stream = previous
    opened = Mock(return_value=replacement)
    monkeypatch.setattr(handler, '_open', opened)
    stat = Mock(return_value=SimpleNamespace(st_dev=1, st_ino=1 if state == 'unchanged' else 2))
    if state == 'deleted':
        stat.side_effect = FileNotFoundError()
    monkeypatch.setattr(sharedlog, 'os', SimpleNamespace(stat=stat,
        fstat=Mock(return_value=SimpleNamespace(st_dev=1, st_ino=1))))
    try:
        handler._reopen_if_moved()
        if state == 'unchanged':
            previous.close.assert_not_called()
            opened.assert_not_called()
            assert handler.stream is previous
        else:
            previous.close.assert_called_once()
            opened.assert_called_once_with()
            assert handler.stream is replacement
    finally:
        handler.close()


def test_delayed_handler_has_no_stream_to_reopen(tmp_path):
    handler = sharedlog.SharedTimedRotatingFileHandler(tmp_path / 'shared.log', delay=True)
    try:
        handler._reopen_if_moved()
        assert handler.stream is None
    finally:
        handler.close()


def test_emit_still_writes_if_identity_check_fails(monkeypatch, tmp_path):
    path = tmp_path / 'shared.log'
    handler = sharedlog.SharedTimedRotatingFileHandler(path)
    monkeypatch.setattr(handler, '_reopen_if_moved', Mock(side_effect=OSError('stat unavailable')))
    try:
        handler.emit(logging.LogRecord('test', logging.INFO, __file__, 0, 'still logged', (), None))
        assert path.read_text().strip() == 'still logged'
    finally:
        handler.close()


def test_rollover_already_done_by_another_process(monkeypatch, tmp_path):
    handler = sharedlog.SharedTimedRotatingFileHandler(tmp_path / 'shared.log', delay=True)
    previous, replacement = Mock(), Mock()
    handler.stream = previous
    monkeypatch.setattr(handler, '_open', Mock(return_value=replacement))
    monkeypatch.setattr(handler, 'computeRollover', Mock(return_value=12345))
    monkeypatch.setattr(sharedlog, 'os', SimpleNamespace(path=SimpleNamespace(
        exists=lambda path: True, splitext=os.path.splitext)))
    try:
        handler.doRollover()
        previous.close.assert_called_once()
        assert handler.stream is replacement
        assert handler.rolloverAt == 12345
    finally:
        handler.close()
