"""Golden results: the recorded behaviour of each device model, one JSON file per model in tests/golden/.

A test compares what GivTCP does now with the recorded result. When a change is intended, re-record with
``pytest --update-golden`` and review the diff of tests/golden/ like any other code change.
"""
import json
from pathlib import Path

import pytest

GOLDEN_DIR = Path(__file__).resolve().parents[1] / "golden"
UPDATE = False

_files = {}
_dirty = set()

def _load(model):
    if model not in _files:
        path = GOLDEN_DIR / (model + ".json")
        _files[model] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return _files[model]

def plain(value):
    """JSON-safe copy (tuples become lists, anything else unusual a string) as it is stored, with source line
    numbers removed from messages so that editing GivTCP doesn't change every result"""
    from harness.fakes import normalise
    def clean(v):
        if isinstance(v, dict):
            return {k: clean(x) for k, x in v.items()}
        if isinstance(v, list):
            return [clean(x) for x in v]
        return normalise(v) if isinstance(v, str) else v
    return clean(json.loads(json.dumps(value, default=str)))

def mask(value, keys):
    """Copy of value with the given dict keys (at any depth) replaced, for values that change from run to run"""
    if isinstance(value, dict):
        return {k: ("<varies>" if k in keys else mask(v, keys)) for k, v in value.items()}
    if isinstance(value, list):
        return [mask(v, keys) for v in value]
    return value

def check(model, section, case, actual):
    data = _load(model)
    actual = plain(actual)
    if UPDATE:
        data.setdefault(section, {})[case] = actual
        _dirty.add(model)
        return
    recorded = data.get(section, {})
    if case not in recorded:
        pytest.fail("No golden result for %s / %s / %s - run pytest --update-golden to record it" % (model, section, case),
                    pytrace=False)
    if actual != recorded[case]:
        from harness.report import diff
        changes = list(diff(recorded[case], actual))
        CHANGES.append((model, section, case, changes))
        shown = changes[:MAX_SHOWN] + (["... and %d more" % (len(changes) - MAX_SHOWN)] if len(changes) > MAX_SHOWN else [])
        pytest.fail("%s / %s / %s differs from tests/golden/%s.json:" % (model, section, case, model)
                    + "".join("\n  " + line for line in shown), pytrace=False)

MAX_SHOWN = 15
CHANGES = []    # (model, section, case, [changed values]) for the end-of-run summary

def all_files():
    """Every model's golden results"""
    for path in sorted(GOLDEN_DIR.glob("*.json")):
        _load(path.stem)
    return dict(_files)

def save():
    GOLDEN_DIR.mkdir(exist_ok=True)
    for model in _dirty:
        path = GOLDEN_DIR / (model + ".json")
        path.write_text(json.dumps(_files[model], indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    _dirty.clear()
