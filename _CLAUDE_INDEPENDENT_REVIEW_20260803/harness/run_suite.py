"""Independent runner for the PR #74 Control Tower suites.

NOT upstream pytest. Collects `test_*` functions, resolves the `tmp_path`
fixture and any module-level fixtures, expands parametrize, and reports
pass/fail/error counts with a non-zero exit on any failure.
"""

import importlib
import importlib.util
import inspect
import itertools
import os
import shutil
import sys
import tempfile
import traceback


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def collect_fixtures(module):
    out = {}
    for name, obj in vars(module).items():
        if callable(obj) and getattr(obj, "_dbx_fixture", False):
            out[name] = obj
    return out


class MonkeyPatch(object):
    """Minimal monkeypatch: setattr/delattr/setenv/delenv with undo."""

    def __init__(self):
        self._undo = []

    _MISSING = object()

    def setattr(self, target, name=_MISSING, value=_MISSING, raising=True):
        if isinstance(target, str):
            # Two-arg dotted form: setattr("pkg.mod.attr", value)
            value = name
            modname, _, attr = target.rpartition(".")
            target, name = importlib.import_module(modname), attr
        if value is self._MISSING:
            raise TypeError("setattr requires a value")
        had = hasattr(target, name)
        old = getattr(target, name, None)
        if raising and not had:
            raise AttributeError("{0} has no attribute {1}".format(target, name))
        setattr(target, name, value)
        self._undo.append(lambda: setattr(target, name, old) if had
                          else delattr(target, name))

    def delattr(self, target, name, raising=True):
        had = hasattr(target, name)
        if not had:
            if raising:
                raise AttributeError(name)
            return
        old = getattr(target, name)
        delattr(target, name)
        self._undo.append(lambda: setattr(target, name, old))

    def setenv(self, name, value):
        old = os.environ.get(name)
        os.environ[name] = str(value)
        self._undo.append(
            lambda: os.environ.__setitem__(name, old) if old is not None
            else os.environ.pop(name, None))

    def delenv(self, name, raising=True):
        old = os.environ.get(name)
        if old is None and raising:
            raise KeyError(name)
        os.environ.pop(name, None)
        self._undo.append(
            lambda: os.environ.__setitem__(name, old) if old is not None else None)

    def undo(self):
        while self._undo:
            self._undo.pop()()


def build_arg(name, fixtures, tmpdir, stack):
    if name == "tmp_path":
        import pathlib

        p = pathlib.Path(tempfile.mkdtemp(dir=tmpdir))
        return p
    if name == "monkeypatch":
        mp = MonkeyPatch()
        stack.append(mp)
        return mp
    if name in fixtures:
        fn = fixtures[name]
        kwargs = {}
        for pname in inspect.signature(fn).parameters:
            kwargs[pname] = build_arg(pname, fixtures, tmpdir, stack)
        return fn(**kwargs)
    raise KeyError("unresolved fixture: {0}".format(name))


def expand(func):
    """Yield (suffix, kwargs) for each parametrize combination."""
    params = getattr(func, "_dbx_params", [])
    if not params:
        yield "", {}
        return
    # Stacked parametrize decorators: cartesian product, as pytest does.
    per_decorator = []
    for names, values, _ids in params:
        entries = []
        for v in values:
            if len(names) == 1:
                entries.append(dict(zip(names, [v])))
            else:
                entries.append(dict(zip(names, v)))
        per_decorator.append(entries)
    for idx, combo in enumerate(itertools.product(*per_decorator)):
        merged = {}
        for d in combo:
            merged.update(d)
        yield "[{0}]".format(idx), merged


def run(paths):
    tmproot = tempfile.mkdtemp(prefix="dbx_harness_")
    passed = failed = errored = 0
    failures = []
    try:
        for path in paths:
            modname = os.path.splitext(os.path.basename(path))[0]
            module = load_module(path, modname)
            fixtures = collect_fixtures(module)
            names = [n for n in dir(module) if n.startswith("test_")]
            for name in sorted(names):
                func = getattr(module, name)
                if not callable(func):
                    continue
                for suffix, pkwargs in expand(func):
                    label = "{0}::{1}{2}".format(modname, name, suffix)
                    kwargs = dict(pkwargs)
                    stack = []
                    try:
                        for pname in inspect.signature(func).parameters:
                            if pname in kwargs:
                                continue
                            kwargs[pname] = build_arg(pname, fixtures, tmproot, stack)
                        func(**kwargs)
                        passed += 1
                    except AssertionError as exc:
                        failed += 1
                        failures.append((label, "FAIL", str(exc)))
                    except Exception:
                        errored += 1
                        failures.append((label, "ERROR", traceback.format_exc(limit=4)))
                    finally:
                        for mp in stack:
                            mp.undo()
    finally:
        shutil.rmtree(tmproot, ignore_errors=True)

    print("=" * 68)
    print("CUSTOM STDLIB HARNESS (NOT upstream pytest)")
    print("passed={0} failed={1} errored={2} total={3}".format(
        passed, failed, errored, passed + failed + errored))
    print("=" * 68)
    for label, kind, detail in failures:
        print("\n[{0}] {1}\n{2}".format(kind, label, detail))
    return 0 if (failed == 0 and errored == 0) else 1


if __name__ == "__main__":
    sys.exit(run(sys.argv[1:]))
