"""Minimal stdlib shim exposing the subset of the pytest API these suites use.

THIS IS NOT UPSTREAM PYTEST. It exists only because the review container has
no PyPI reachability, so `pip install pytest` fails. Results produced through
this shim must always be labelled as custom-harness results.

Supported: pytest.raises, pytest.mark.parametrize, pytest.fixture, and the
tmp_path fixture. Anything else raises rather than silently passing.
"""


class _Raises(object):
    def __init__(self, expected, match=None):
        self.expected = expected
        self.match = match
        self.value = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            raise AssertionError(
                "DID NOT RAISE {0}".format(self.expected)
            )
        if not issubclass(exc_type, self.expected):
            return False  # propagate: wrong exception type is a real failure
        if self.match is not None:
            import re

            if not re.search(self.match, str(exc)):
                raise AssertionError(
                    "pattern {0!r} not found in {1!r}".format(self.match, str(exc))
                )
        self.value = exc
        return True


def raises(expected, match=None):
    return _Raises(expected, match=match)


class _Mark(object):
    @staticmethod
    def parametrize(argnames, argvalues, ids=None):
        if isinstance(argnames, str):
            names = [n.strip() for n in argnames.split(",") if n.strip()]
        else:
            names = list(argnames)

        def decorator(func):
            existing = getattr(func, "_dbx_params", [])
            func._dbx_params = existing + [(names, list(argvalues), ids)]
            return func

        return decorator

    def __getattr__(self, item):
        raise NotImplementedError("pytest.mark.{0} is not shimmed".format(item))


mark = _Mark()


def fixture(*args, **kwargs):
    def decorator(func):
        func._dbx_fixture = True
        return func

    if args and callable(args[0]):
        return decorator(args[0])
    return decorator


def skip(reason=""):
    raise _Skipped(reason)


class _Skipped(Exception):
    pass
