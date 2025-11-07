
import datetime as _dt
import json

class Logger:
    def _emit(self, level, event, message, ctx):
        ts = _dt.datetime.utcnow().isoformat() + "Z"
        line = {"ts": ts, "level": level, "event": event, "msg": message, "ctx": ctx or {}}
        print(json.dumps(line))

    def info(self, event, message, ctx=None):
        self._emit("INFO", event, message, ctx)

    def debug(self, event, message, ctx=None):
        self._emit("DEBUG", event, message, ctx)

    def warn(self, event, message, ctx=None):
        self._emit("WARN", event, message, ctx)

    def error(self, event, message, ctx=None):
        self._emit("ERROR", event, message, ctx)
