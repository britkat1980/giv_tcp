"""Rotated logs keep the .log extension, so they can be attached to a GitHub issue as they are (#606)."""
import os

from sharedlog import SharedTimedRotatingFileHandler

def handler(path):
    return SharedTimedRotatingFileHandler(str(path), when="midnight", backupCount=7)

def test_rotated_name_keeps_log_extension(tmp_path):
    h = handler(tmp_path / "log_inv_1.log")
    try:
        assert h.rotation_filename(h.baseFilename + ".2026-10-03") == str(tmp_path / "log_inv_1.2026-10-03.log")
    finally:
        h.close()

def test_old_style_backups_are_renamed(tmp_path):
    (tmp_path / "write_log_inv_1.log.2026-10-01").write_text("old")
    (tmp_path / "log_inv_1.log.2026-10-01").write_text("another log's backup")
    h = handler(tmp_path / "write_log_inv_1.log")
    try:
        names = sorted(os.listdir(tmp_path))
        assert "write_log_inv_1.2026-10-01.log" in names
        assert "write_log_inv_1.log.2026-10-01" not in names
        assert "log_inv_1.log.2026-10-01" in names          # left for that log's own handler
    finally:
        h.close()

def test_only_the_last_7_backups_are_kept(tmp_path):
    for day in range(1, 11):
        (tmp_path / f"log_inv_1.2026-10-{day:02d}.log").write_text("x")
    (tmp_path / "write_log_inv_1.2026-10-01.log").write_text("another log's backup")
    h = handler(tmp_path / "log_inv_1.log")
    try:
        deleted = sorted(os.path.basename(p) for p in h.getFilesToDelete())
        assert deleted == ["log_inv_1.2026-10-01.log", "log_inv_1.2026-10-02.log", "log_inv_1.2026-10-03.log"]
    finally:
        h.close()
