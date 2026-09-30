"""Readable reports: what changed from the golden results, and what GivTCP currently gets wrong."""
import json
import re
from collections import defaultdict

MAX_VALUE = 120

def _short(value):
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else repr(value)
    return text if len(text) <= MAX_VALUE else text[:MAX_VALUE] + "..."

def diff(expected, actual, path=""):
    """Yield one line per changed value: 'path: expected -> actual'"""
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key in sorted(set(expected) | set(actual), key=str):
            sub = path + "/" + str(key)
            if key not in actual:
                yield "%s: removed (was %s)" % (sub, _short(expected[key]))
            elif key not in expected:
                yield "%s: added %s" % (sub, _short(actual[key]))
            else:
                yield from diff(expected[key], actual[key], sub)
    elif isinstance(expected, list) and isinstance(actual, list) and not _is_row(expected) and not _is_row(actual):
        if len(expected) == len(actual):
            for i, (e, a) in enumerate(zip(expected, actual)):
                yield from diff(e, a, "%s[%d]" % (path, i))
        else:
            gone = [x for x in expected if x not in actual]
            new = [x for x in actual if x not in expected]
            for x in gone:
                yield "%s: removed %s" % (path or "/", _short(x))
            for x in new:
                yield "%s: added %s" % (path or "/", _short(x))
    elif expected != actual:
        yield "%s: %s -> %s" % (path or "/", _short(expected), _short(actual))

def _is_row(value):
    # A register write [device, register, value] or a log line [logger, level, message]: compare whole
    return len(value) in (2, 3) and all(not isinstance(v, (dict, list)) for v in value)

# --- problems recorded in the golden results -------------------------------------------------------------

def _problems_in(step):
    found = []
    if step.get("raised"):
        found.append("Unhandled exception (the read loop drops every queued request): " + step["raised"])
    if step.get("still_sending_after_return"):
        found.append("Command returned with %d write(s) still being sent" % step["still_sending_after_return"])
    if step.get("status") not in (None, 200):
        found.append("HTTP %s" % step["status"])
    result = step.get("result")
    if isinstance(result, str) and "timeout" in result.lower():
        found.append("REST caller timed out: " + result)
    for name, level, message in step.get("logs", []):
        if level in ("ERROR", "CRITICAL") and not name.startswith("givenergy_modbus") and name != "rest_logger":
            found.append(message)
    return found

def _group_key(message):
    # Group messages that differ only in slot numbers or enable/disable
    message = re.sub(r" (enable|disable) ", " <state> ", message)
    return re.sub(r"\b\d+\b", "N", message)

def problems(golden_files):
    """{grouped message: {model: [where]}} for every error recorded in the golden results"""
    grouped = defaultdict(lambda: defaultdict(list))
    for model, data in sorted(golden_files.items()):
        for case, lines in data.get("read", {}).items():
            if case.endswith("logs"):
                for name, level, message in lines:
                    if level in ("ERROR", "CRITICAL") and not name.startswith("givenergy_modbus"):
                        grouped[_group_key(message)][model].append("read " + case.replace(" logs", ""))
        for entry in ("direct", "rest", "mqtt"):
            for case, steps in data.get(entry, {}).items():
                for step in steps:
                    for message in _problems_in(step):
                        grouped[_group_key(message)][model].append(entry + " " + case)
    return grouped

# Failures that are a known limit of the model or of givenergy-modbus, rather than a GivTCP bug
UNSUPPORTED = ("not yet supported", "slot index", "only available on", "not supported by", "is not permitted for",
               "External rate setting not allowed", "isn't known for this inverter", "not available for",
               "is not currently running")

def _control(where):
    # "mqtt setChargeTarget3(85)" -> "mqtt setChargeTarget3"
    return where.split("(")[0].strip()

def format_problems(grouped):
    errors, unsupported = [], []
    for message, models in grouped.items():
        (unsupported if any(u in message for u in UNSUPPORTED) else errors).append((message, models))
    lines = []
    for title, items in (("ERRORS TO FIX", errors), ("NOT SUPPORTED OR NOT APPLICABLE (library or model limits, nothing to cancel)", unsupported)):
        lines += [title + " (%d)" % len(items), ""]
        for message, models in sorted(items, key=lambda kv: (-len(kv[1]), kv[0])):
            lines.append("* " + message)
            # models with the same failing controls share a line
            by_controls = defaultdict(list)
            for model, where in models.items():
                by_controls[tuple(sorted({_control(w) for w in where}))].append(model)
            for controls, model_list in sorted(by_controls.items(), key=lambda kv: kv[1]):
                shown = ", ".join(controls[:8]) + (" and %d more" % (len(controls) - 8) if len(controls) > 8 else "")
                lines.append("    %s: %s" % (", ".join(sorted(model_list)), shown))
            lines.append("")
    return lines
