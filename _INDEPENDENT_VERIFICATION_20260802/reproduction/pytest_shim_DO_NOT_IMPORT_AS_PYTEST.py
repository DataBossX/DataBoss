"""Minimal stdlib pytest shim used to reproduce the Control Tower suite offline.

WHY THIS EXISTS
    The verification host has no pytest and no PyPI access. The Control Tower
    suite uses only a tiny slice of the pytest API, so this shim reproduces
    that slice exactly: raises, fixture, mark.parametrize, tmp_path, monkeypatch.

HOW TO USE IT
    Do NOT import this file as-is and do NOT place it at a repository root
    under the name pytest.py -- that would shadow real pytest for every tool in
    the tree. To reproduce:

        mkdir /tmp/verify && cd /tmp/verify
        git archive <build-ref> | tar -x
        cp <this file> ./pytest.py
        cp run_suite_with_shim.py ./
        python3 run_suite_with_shim.py

DESIGN NOTE
    The shim is deliberately strict. raises() asserts DID NOT RAISE when no
    exception occurs, and propagates any exception that is not a subclass of
    the expected type. A bug in the shim therefore surfaces as a failure or an
    error, never as a false pass.
"""


class _Raises:
    def __init__(self, expected):
        self.expected = expected
        self.value = None  # populated on exit, so `excinfo.value` works

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            raise AssertionError(f"DID NOT RAISE {self.expected}")
        if issubclass(exc_type, self.expected):
            self.value = exc
            return True  # swallow: this is the expected refusal
        return False  # propagate: wrong exception type -> test errors


def raises(expected):
    return _Raises(expected)


def fixture(*a, **k):
    def deco(fn):
        fn.__is_fixture__ = True
        return fn

    if a and callable(a[0]):
        return deco(a[0])
    return deco


class Skipped(Exception):
    """Raised to signal a skipped test, so a skip is never counted as a pass."""


class _Mark:
    @staticmethod
    def skipif(condition, reason=""):
        def deco(fn):
            if condition:
                fn.__skip__ = reason or "skipif"
            return fn

        return deco

    @staticmethod
    def parametrize(argnames, argvalues, ids=None):
        names = [n.strip() for n in argnames.split(",")] if isinstance(argnames, str) else list(argnames)

        def deco(fn):
            fn.__parametrize__ = (names, list(argvalues))
            return fn

        return deco

    def __getattr__(self, _name):  # tolerate marks the suite does not rely on
        def deco(*a, **k):
            return (lambda fn: fn) if not (a and callable(a[0])) else a[0]

        return deco


mark = _Mark()


class MonkeyPatch:
    def __init__(self):
        self._undo = []

    def setattr(self, target, name, value=None, raising=True):
        if value is None and isinstance(target, str):
            mod, _, attr = target.rpartition(".")
            import importlib

            obj = importlib.import_module(mod)
            name, value = attr, name
        else:
            obj = target
        old = getattr(obj, name)
        self._undo.append((obj, name, old))
        setattr(obj, name, value)

    def setenv(self, k, v):
        import os

        self._undo.append(("env", k, os.environ.get(k)))
        os.environ[k] = v

    def delenv(self, k, raising=True):
        import os

        if k not in os.environ:
            if raising:
                raise KeyError(k)
            return
        self._undo.append(("env", k, os.environ[k]))
        del os.environ[k]

    def undo(self):
        import os

        for obj, name, old in reversed(self._undo):
            if obj == "env":
                if old is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = old
            else:
                setattr(obj, name, old)
        self._undo = []
