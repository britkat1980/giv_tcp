"""Log file handler for a log written by several GivTCP processes. Kept free of other GivTCP imports so any
process can use it, including the EVC loops (GivLUT connects to the inverter and Redis when imported)"""
import os
import time
from logging.handlers import TimedRotatingFileHandler

class SharedTimedRotatingFileHandler(TimedRotatingFileHandler):
    """TimedRotatingFileHandler for a log file written by several processes (read loop, REST workers,
    MQTT client, RQ worker). Only the first process to reach midnight rotates; the others reopen the new
    file instead of rotating again, and every process follows the file if another one has moved it.
    Rotated files keep the .log extension (log_inv_1.2026-10-03.log, not log_inv_1.log.2026-10-03), so they
    can be attached to a GitHub issue as they are (#606)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.namer=self._dated_name     # the library deletes old backups by this name too, so backupCount still applies
        self._rename_old_backups()

    def _dated_name(self, default):
        root,ext=os.path.splitext(self.baseFilename)
        if not ext:
            return default
        return root+"."+default[len(self.baseFilename)+1:]+ext

    def _rename_old_backups(self):
        # Backups rotated before #606 end in the date, so give them the new name, or they'd never be deleted
        folder,base=os.path.split(self.baseFilename)
        try:
            names=os.listdir(folder)
        except OSError:
            return
        for name in names:
            if name.startswith(base+".") and self.extMatch.fullmatch(name[len(base)+1:]):
                old=os.path.join(folder,name)
                try:
                    os.rename(old,self.namer(old))
                except OSError:
                    pass        # another process renamed it first

    def _reopen_if_moved(self):
        if self.stream is None:
            return
        try:
            sres=os.stat(self.baseFilename)
        except FileNotFoundError:
            sres=None
        fres=os.fstat(self.stream.fileno())
        if sres is None or (sres.st_dev,sres.st_ino)!=(fres.st_dev,fres.st_ino):
            self.stream.close()
            self.stream=self._open()

    def emit(self, record):
        try:
            self._reopen_if_moved()
        except Exception:
            pass
        super().emit(record)

    def doRollover(self):
        timeTuple=time.localtime(self.rolloverAt-self.interval)
        dfn=self.rotation_filename(self.baseFilename+"."+time.strftime(self.suffix, timeTuple))
        if os.path.exists(dfn):
            # Another process has already rotated this period: just move on to the new file
            if self.stream:
                self.stream.close()
            self.stream=self._open()
            self.rolloverAt=self.computeRollover(int(time.time()))
            return
        super().doRollover()
