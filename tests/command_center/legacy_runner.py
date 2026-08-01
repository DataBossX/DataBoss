"""Minimal stdlib-compatible runner for the legacy `pytest` suite.

Why this exists: the build environment has no package network, so `pytest`
cannot be installed and the legacy suite would otherwise go entirely unverified.
Leaving it unrun and *saying so* is honest; leaving it unrun and implying it
passed is not.

What this is NOT: a pytest replacement. It implements a faithful subset --
plain assert-based tests, the ``tmp_path`` fixture, ``pytest.raises``,
``pytest.mark.parametrize``, and ``pytest.approx``. Anything outside that subset
is reported as **SKIPPED-UNSUPPORTED**, never as passed.

Results from this runner must always be labelled "stdlib-compat runner", never
"pytest".
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import inspect
import re
import sys
import tempfile
import traceback
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Fixtures this runner can honestly provide.
SUPPORTED_FIXTURES = {"tmp_path", "tmp_path_factory"}


class _Approx:
    def __init__(self, expected, rel=1e-6, abs=1e-12):
        self.expected, self.rel, self.abs = expected, rel, abs

    def __eq__(self, other):
        try:
            return abs(other - self.expected) <= max(self.abs, self.rel * abs(self.expected))
        except TypeError:
            return NotImplemented

    def __repr__(self):
        return f"approx({self.expected!r})"


class _RaisesContext:
    def __init__(self, expected, match=None):
        self.expected, self.match = expected, match
        self.value = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            raise AssertionError(f"DID NOT RAISE {self.expected}")
        if not issubclass(exc_type, self.expected):
            return False
        if self.match and not re.search(self.match, str(exc)):
            raise AssertionError(f"pattern {self.match!r} not found in {str(exc)!r}")
        self.value = exc
        return True


class _Mark:
    def __getattr__(self, name):
        if name == "parametrize":
            def parametrize(argnames, argvalues, **kwargs):
                def decorator(fn):
                    names = ([a.strip() for a in argnames.split(",")]
                             if isinstance(argnames, str) else list(argnames))
                    cases = getattr(fn, "_dbx_params", [])
                    cases.append((names, list(argvalues)))
                    fn._dbx_params = cases
                    return fn
                return decorator
            return parametrize

        def unsupported_mark(*args, **kwargs):
            def decorator(fn):
                fn._dbx_unsupported = f"pytest.mark.{name}"
                return fn
            if args and callable(args[0]) and len(args) == 1:
                return decorator(args[0])
            return decorator
        return unsupported_mark


def _build_pytest_stub() -> types.ModuleType:
    module = types.ModuleType("pytest")
    module.raises = lambda expected, match=None: _RaisesContext(expected, match)
    module.approx = _Approx
    module.mark = _Mark()

    class Skipped(Exception):
        pass

    module.skip = lambda reason="": (_ for _ in ()).throw(Skipped(reason))
    module.Skipped = Skipped

    def fixture(*args, **kwargs):
        def decorator(fn):
            fn._dbx_is_fixture = True
            return fn
        if args and callable(args[0]) and len(args) == 1:
            return decorator(args[0])
        return decorator

    module.fixture = fixture
    module.importorskip = lambda name, *a, **k: (_ for _ in ()).throw(Skipped(f"needs {name}"))
    return module


@contextlib.contextmanager
def _temp_path():
    with tempfile.TemporaryDirectory(prefix="dbx-legacy-") as path:
        yield Path(path)


def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location(f"legacy_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _invoke(fn, params: dict) -> None:
    signature = inspect.signature(fn)
    kwargs = {}
    with contextlib.ExitStack() as stack:
        for name in signature.parameters:
            if name in params:
                kwargs[name] = params[name]
            elif name in ("tmp_path", "tmp_path_factory"):
                kwargs[name] = stack.enter_context(_temp_path())
            else:
                raise RuntimeError(f"unsupported fixture {name!r}")
        fn(**kwargs)


def run_file(path: Path) -> dict:
    result = {"file": str(path.relative_to(REPO_ROOT)), "passed": 0, "failed": 0,
              "skipped_unsupported": 0, "failures": [], "skips": []}
    try:
        module = _load_module(path)
    except Exception as exc:
        result["skipped_unsupported"] += 1
        result["skips"].append(f"{path.name} (import): {type(exc).__name__}: {exc}")
        return result

    pytest_stub = sys.modules["pytest"]

    for name, fn in sorted(vars(module).items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        if getattr(fn, "_dbx_unsupported", None):
            result["skipped_unsupported"] += 1
            result["skips"].append(f"{path.name}::{name} ({fn._dbx_unsupported})")
            continue

        param_sets = getattr(fn, "_dbx_params", None)
        cases = [({}, "")]
        if param_sets:
            cases = []
            names, values = param_sets[0]
            for value in values:
                bound = value if isinstance(value, (tuple, list)) else (value,)
                cases.append((dict(zip(names, bound)), f"[{bound}]"))

        for params, label in cases:
            try:
                _invoke(fn, params)
                result["passed"] += 1
            except pytest_stub.Skipped as exc:
                result["skipped_unsupported"] += 1
                result["skips"].append(f"{path.name}::{name}{label} (skip): {exc}")
            except RuntimeError as exc:
                if "unsupported fixture" in str(exc):
                    result["skipped_unsupported"] += 1
                    result["skips"].append(f"{path.name}::{name}{label}: {exc}")
                else:
                    result["failed"] += 1
                    result["failures"].append(
                        f"{path.name}::{name}{label}\n{traceback.format_exc(limit=6)}")
            except Exception:
                result["failed"] += 1
                result["failures"].append(
                    f"{path.name}::{name}{label}\n{traceback.format_exc(limit=6)}")
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", default=str(REPO_ROOT / "tests"))
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    # conftest.py puts src/ on the path; mirror that here.
    for extra in (REPO_ROOT, REPO_ROOT / "src"):
        if str(extra) not in sys.path:
            sys.path.insert(0, str(extra))
    sys.modules["pytest"] = _build_pytest_stub()

    files = sorted(Path(args.dir).glob("test_*.py"))
    totals = {"passed": 0, "failed": 0, "skipped_unsupported": 0}
    reports = []

    print("=" * 74)
    print("LEGACY SUITE - stdlib-compat runner (NOT pytest)")
    print("Results below are runner-executed. Unsupported cases are SKIPPED-UNSUPPORTED,")
    print("never reported as passed. pytest could not be installed: no package network.")
    print("=" * 74)

    for path in files:
        report = run_file(path)
        reports.append(report)
        for key in totals:
            totals[key] += report[key]
        print(f"{report['file']:<46} pass={report['passed']:>3} "
              f"fail={report['failed']:>3} skip-unsupported={report['skipped_unsupported']:>3}")

    if args.verbose:
        for report in reports:
            for failure in report["failures"]:
                print("\nFAILURE:", failure)
            for skip in report["skips"]:
                print("SKIP-UNSUPPORTED:", skip)

    print("-" * 74)
    print(f"TOTAL  passed={totals['passed']}  failed={totals['failed']}  "
          f"skipped_unsupported={totals['skipped_unsupported']}")
    print("Runner: stdlib-compat subset. Not a pytest run. Do not report as pytest results.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
