"""A user path is resolved where it is used, never when a module is imported.

The host's qualification store was a module constant and the default of the
functions that append to it, fixed at import -- before any test could move
HOME. So no fence reached it: the suite's achieved-goal test appended a
``qualified`` row of its goal ``g`` to the developer's real
``~/.chemsmart/agent/qualification.jsonl`` on every run, and ``chemsmart
agent capabilities`` read those rows as host qualification (655 of the
store's 740 rows by 2026-09-25, R10 Q25). Six modules held the user's
settings directory bound the same way, and the agent read the PySCF
interpreter out of the user's server YAML at import.

The invariant is general, so the witness is a census: every ``chemsmart``
module is imported in a child whose HOME is a directory made for it, and
nothing may hold that directory afterwards (a module global, a class
attribute, the state of a module-level instance, or a default) or have read
or written under it on chemsmart's own account while importing. Third-party
libraries that touch a home at import (matplotlib's font cache, ASE's
config file) are theirs, not the host's, and are not counted.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import chemsmart

_CENSUS = r"""
import dataclasses, functools, importlib, inspect, json, os, pkgutil
import sys, sysconfig, threading, types

HOME = os.path.realpath(os.environ["HOME"])
import chemsmart
PACKAGE = os.path.dirname(os.path.realpath(chemsmart.__file__)) + os.sep
PATHS = sysconfig.get_paths()
STDLIB = tuple(
    os.path.realpath(PATHS[key]) + os.sep for key in ("stdlib", "platstdlib")
)
# site-packages can live inside the standard library's directory; a frame
# there is a third-party library's, not the standard library's.
SITE = tuple(
    os.path.realpath(PATHS[key]) + os.sep for key in ("purelib", "platlib")
)
_busy = threading.local()
touched = []

def _owner(frame):
    # The innermost frame that is neither the standard library nor the
    # import machinery says whose code touched the file.
    while frame is not None:
        name = frame.f_code.co_filename
        path = os.path.realpath(name)
        if not name.startswith("<") and (
            path.startswith(SITE) or not path.startswith(STDLIB)
        ):
            return path
        frame = frame.f_back
    return ""

def _hook(event, args):
    if event not in ("open", "os.mkdir", "os.rename", "os.remove", "os.rmdir",
                     "os.scandir", "os.listdir", "glob.glob", "shutil.copyfile",
                     "sqlite3.connect"):
        return
    if getattr(_busy, "on", False):
        return
    _busy.on = True
    try:
        for value in args[:2]:
            if value is None or isinstance(value, int):
                continue
            try:
                text = os.fspath(value)
            except TypeError:
                continue
            if isinstance(text, bytes):
                text = text.decode("utf-8", "replace")
            if not isinstance(text, str) or HOME not in os.path.realpath(os.path.abspath(text)):
                continue
            owner = _owner(sys._getframe(1))
            if owner.startswith(PACKAGE):
                touched.append(f"{event} {text} by {owner[len(PACKAGE):]}")
    except Exception:
        pass
    finally:
        _busy.on = False

sys.addaudithook(_hook)

unimportable = {}
for info in pkgutil.walk_packages(chemsmart.__path__, "chemsmart."):
    if info.name.endswith("__main__"):
        continue
    try:
        importlib.import_module(info.name)
    except Exception as exc:
        unimportable[info.name] = repr(exc)[:200]

def _holds(value, depth=0, seen=None):
    seen = set() if seen is None else seen
    if isinstance(value, (str, bytes, os.PathLike)):
        try:
            text = os.fspath(value)
        except Exception:
            return False
        if isinstance(text, bytes):
            text = text.decode("utf-8", "replace")
        return isinstance(text, str) and HOME in text
    if depth > 3 or id(value) in seen:
        return False
    seen.add(id(value))
    if isinstance(value, (tuple, list, set, frozenset)):
        return any(_holds(item, depth + 1, seen) for item in list(value)[:500])
    if isinstance(value, (dict, types.MappingProxyType)):
        return any(
            _holds(key, depth + 1, seen) or _holds(item, depth + 1, seen)
            for key, item in list(value.items())[:500]
        )
    if isinstance(value, functools.partial):
        return _holds((value.args, value.keywords), depth + 1, seen)
    return False

def _defaults(function):
    function = inspect.unwrap(function)
    return [
        value
        for value in (getattr(function, "__defaults__", None),
                      getattr(function, "__kwdefaults__", None))
        if value
    ]

bound = []
for name in sorted(n for n in list(sys.modules) if n == "chemsmart" or n.startswith("chemsmart.")):
    module = sys.modules[name]
    for attr, value in list(vars(module).items()):
        where = f"{name}.{attr}"
        if inspect.ismodule(value):
            continue
        if inspect.isfunction(value) or isinstance(value, functools._lru_cache_wrapper):
            if getattr(value, "__module__", None) == name and any(_holds(d) for d in _defaults(value)):
                bound.append(f"{where} (default)")
            continue
        if inspect.isclass(value):
            if value.__module__ != name:
                continue
            for member_name, member in list(vars(value).items()):
                if isinstance(member, (staticmethod, classmethod)):
                    member = member.__func__
                if inspect.isfunction(member):
                    if any(_holds(d) for d in _defaults(member)):
                        bound.append(f"{where}.{member_name} (default)")
                elif member_name == "__dataclass_fields__":
                    for field_name, field in member.items():
                        if field.default is not dataclasses.MISSING and _holds(field.default):
                            bound.append(f"{where}.{field_name} (dataclass default)")
                elif not isinstance(member, (property, functools.cached_property)) and not member_name.startswith("__"):
                    if _holds(member):
                        bound.append(f"{where}.{member_name} (class attribute)")
            continue
        if _holds(value):
            bound.append(f"{where} (module global)")
        elif (type(value).__module__ or "").startswith("chemsmart") and _holds(getattr(value, "__dict__", {})):
            bound.append(f"{where} (module-level instance)")

print(json.dumps({"bound": bound, "touched": touched, "unimportable": unimportable,
                  "package": PACKAGE}))
"""


def test_nothing_chemsmart_imports_holds_or_reads_the_home_it_was_imported_under(
    tmp_path,
):
    home = tmp_path / "home-at-import"
    home.mkdir()
    tree = Path(chemsmart.__file__).resolve().parents[1]
    environment = dict(os.environ)
    environment.pop("CHEMSMART_CONFIG_DIR", None)
    environment.update(
        HOME=str(home),
        USERPROFILE=str(home),
        PYTHONPATH=str(tree),
        # matplotlib keeps its font cache in the home; building it there is
        # its business and slow, so it gets a directory of its own.
        MPLCONFIGDIR=str(tmp_path / "matplotlib"),
    )
    completed = subprocess.run(
        [sys.executable, "-c", _CENSUS],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=900,
    )
    assert completed.returncode == 0, completed.stderr[-3000:]
    report = json.loads(completed.stdout.strip().splitlines()[-1])

    # The child imported this tree, not whatever an editable install maps.
    assert Path(report["package"]).resolve() == tree / "chemsmart"
    assert (report["bound"], report["touched"]) == (
        [],
        [],
    ), "bound to the home at import -- resolve these where they are used, " "or no fence can move them:\n  " + "\n  ".join(
        report["bound"]
    ) + "\nthe home read or written by chemsmart while it was imported:\n  " + "\n  ".join(
        report["touched"]
    )
