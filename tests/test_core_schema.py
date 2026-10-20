"""The typed contract stays in step with the code: generated files, every method, the parameters and result shapes."""

import json
from pathlib import Path

from core import __version__
from core.api import CoreApi
from core.schema import METHODS, check_params, json_schema, typescript
from tests.test_core_api_methods import calls

ROOT = Path(__file__).resolve().parents[1]


def test_generated_files_are_up_to_date():
    assert json.loads((ROOT / "core" / "api.schema.json").read_text(encoding="utf-8")) == json_schema(__version__), \
        "run python tools/build_core_schema.py"
    assert (ROOT / "core" / "api.d.ts").read_text(encoding="utf-8") == typescript(__version__)


def test_every_api_method_has_a_schema():
    assert set(METHODS) == set(CoreApi().methods)


def _valid(value, schema, defs, path="$") -> list[str]:
    """A small JSON Schema check: type, required, properties, items, anyOf, $ref."""
    if "$ref" in schema:
        return _valid(value, defs[schema["$ref"].rsplit("/", 1)[1]], defs, path)
    if "anyOf" in schema:
        options = [_valid(value, option, defs, path) for option in schema["anyOf"]]
        return [] if any(not o for o in options) else options[0]
    kind = schema.get("type")
    checks = {"string": str, "boolean": bool, "object": dict, "array": list, "null": type(None)}
    if kind == "integer" and not (isinstance(value, int) and not isinstance(value, bool)):
        return [f"{path}: {value!r} is not an integer"]
    if kind == "number" and not (isinstance(value, (int, float)) and not isinstance(value, bool)):
        return [f"{path}: {value!r} is not a number"]
    if kind in checks and not isinstance(value, checks[kind]):
        return [f"{path}: {type(value).__name__} is not {kind}"]
    problems = []
    if kind == "object":
        problems += [f"{path}.{key}: missing" for key in schema.get("required", []) if key not in value]
        for key, sub in schema.get("properties", {}).items():
            if key in value:
                problems += _valid(value[key], sub, defs, f"{path}.{key}")
    if kind == "array":
        for i, item in enumerate(value):
            problems += _valid(item, schema.get("items", {}), defs, f"{path}[{i}]")
    return problems


def test_requests_and_answers_follow_the_schema(tmp_path, monkeypatch):
    import core.api

    monkeypatch.setattr(core.api, "site_fingerprint", lambda fetch: "site-picture-v2")
    api = CoreApi()
    api.call("data.open", {"data_dir": str(ROOT / "data")})
    schema = json_schema(__version__)
    for method, params, _check in calls(tmp_path, api):
        assert check_params(method, params) == [], method
        result = json.loads(json.dumps(api.call(method, params), ensure_ascii=False))
        problems = _valid(result, schema["methods"][method]["result"], schema["$defs"])
        assert not problems, (method, problems[:5])
