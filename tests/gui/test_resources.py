from __future__ import annotations

import hashlib
import json
from importlib import resources
import os
from pathlib import Path
import subprocess
import sys

from chemsmart.gui.resources import THREEDMOL_SHA256, read_threedmol_javascript
from chemsmart.gui.widgets.structure_viewer import build_3dmol_html


def test_vendored_threedmol_matches_pinned_hash():
    root = resources.files("chemsmart.gui") / "assets" / "3dmol"
    asset = root / "3Dmol-min.js"
    source = json.loads((root / "source.json").read_text(encoding="utf-8"))

    assert hashlib.sha256(asset.read_bytes()).hexdigest() == THREEDMOL_SHA256
    assert source["sha256"] == THREEDMOL_SHA256
    assert hashlib.sha256((root / "LICENSE").read_bytes()).hexdigest() == source[
        "license_sha256"
    ]
    assert hashlib.sha256(
        (root / "3Dmol-min.js.LICENSE.txt").read_bytes()
    ).hexdigest() == source["bundle_notice_sha256"]
    assert len(read_threedmol_javascript()) > 500_000


def test_threedmol_document_is_self_contained_and_data_safe():
    xyz = "1\nbacktick-safe\nH 0 0 0\n"
    html = build_3dmol_html(xyz, "#ffffff")

    assert "<script src=" not in html
    assert "window.__chemsmartAtomCount" in html
    assert "decodeUtf8" in html
    assert xyz not in html
    assert "$3Dmol.createViewer" in html


def test_threedmol_document_blocks_script_breakout_from_structure_data():
    malicious = (
        "1\n</script><script>window.pwned = true</script>\\u2028\\u2029\n"
        "H 0 0 0\n"
    ).encode("utf-8").decode("unicode_escape")

    html = build_3dmol_html(malicious, "#ffffff", "xyz")

    assert malicious not in html
    assert "window.pwned" not in html
    assert html.count("</script>") == 2
    assert "decodeUtf8" in html


def test_threedmol_renders_in_isolated_qtwebengine_process():
    script = r'''
import json
from PySide6.QtCore import QTimer
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication
from chemsmart.gui.widgets.structure_viewer import build_3dmol_html

app = QApplication([])
view = QWebEngineView()
view.resize(320, 240)
view.show()
finished = {"done": False}

def complete(value, returncode=0):
    if finished["done"]:
        return
    finished["done"] = True
    print(json.dumps(value, sort_keys=True), flush=True)
    view.close()
    app.exit(returncode)

def loaded(ok):
    if not ok:
        complete({"load": False}, 2)
        return
    view.page().runJavaScript(
        "JSON.stringify({library: typeof $3Dmol !== 'undefined', "
        "atoms: window.__chemsmartAtomCount || 0, "
        "canvases: document.querySelectorAll('canvas').length})",
        lambda value: complete(json.loads(value) if value else {"value": value}),
    )

view.loadFinished.connect(loaded)
view.setHtml(build_3dmol_html("1\nhydrogen\nH 0 0 0\n", "#ffffff"))
QTimer.singleShot(15_000, lambda: complete({"timeout": True}, 3))
raise SystemExit(app.exec())
'''
    environment = dict(os.environ)
    environment["QT_QPA_PLATFORM"] = "offscreen"
    repo_root = str(Path(__file__).resolve().parents[2])
    existing = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        repo_root if not existing else f"{repo_root}{os.pathsep}{existing}"
    )

    completed = subprocess.run(
        [sys.executable, "-c", script],
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr[-2000:]
    assert json.loads(completed.stdout.splitlines()[-1]) == {
        "atoms": 1,
        "canvases": 1,
        "library": True,
    }
