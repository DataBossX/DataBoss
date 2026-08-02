"""Independent runner for the Control Tower suite under the stdlib pytest shim.

Expands parametrize decorators the way pytest does, gives each test a fresh
tmp_path, and reports passed / failed / errors separately so a shim problem is
distinguishable from a genuine test failure.

See pytest_shim_DO_NOT_IMPORT_AS_PYTEST.py for setup instructions.
"""
import pathlib
import sys
import tempfile
import traceback

sys.path.insert(0, ".")
import pytest as _shim  # noqa: E402  (the shim, copied to ./pytest.py)

import tests.test_control_tower as T  # noqa: E402

FIXTURES = {n: getattr(T, n) for n in dir(T) if getattr(getattr(T, n, None), "__is_fixture__", False)}


def make(name, tmp):
    if name == "tmp_path":
        return tmp
    if name == "monkeypatch":
        return _shim.MonkeyPatch()
    if name in FIXTURES:
        fn = FIXTURES[name]
        args = [make(p, tmp) for p in fn.__code__.co_varnames[: fn.__code__.co_argcount]]
        return fn(*args)
    raise KeyError(f"unknown fixture {name}")


passed = failed = errored = 0
fails = []

for name in sorted(n for n in dir(T) if n.startswith("test_")):
    fn = getattr(T, name)
    params = getattr(fn, "__parametrize__", None)
    if params:
        pnames, pvals = params
        cases = [dict(zip(pnames, v)) if len(pnames) > 1 else {pnames[0]: v} for v in pvals]
    else:
        cases = [{}]

    for case in cases:
        label = f"{name}{list(case.values()) if case else ''}"
        mp = None
        try:
            with tempfile.TemporaryDirectory() as td:
                tmp = pathlib.Path(td)
                kwargs = {}
                for a in fn.__code__.co_varnames[: fn.__code__.co_argcount]:
                    if a in case:
                        kwargs[a] = case[a]
                    else:
                        kwargs[a] = make(a, tmp)
                        if a == "monkeypatch":
                            mp = kwargs[a]
                fn(**kwargs)
            passed += 1
        except AssertionError as e:
            failed += 1
            fails.append((label, f"FAIL: {e}"))
        except Exception:
            errored += 1
            fails.append((label, "ERROR:\n" + traceback.format_exc()))
        finally:
            if mp:
                mp.undo()

print(f"\n{'=' * 60}")
print(f"passed={passed} failed={failed} errors={errored}  (total={passed + failed + errored})")
for label, msg in fails[:15]:
    print(f"\n--- {label}\n{msg}")
sys.exit(0 if not fails else 1)
