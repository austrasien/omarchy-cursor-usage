"""Run the real QML service against a harmless collector, without a desktop/login."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(shutil.which("quickshell"), "requires Quickshell")
class ServiceTest(unittest.TestCase):
  def test_collection_without_internal_manifest_paths(self):
    for manifest in (None, {"id": "io.github.mrlarsendk.cursor-usage"},
                     {"id": "io.github.mrlarsendk.cursor-usage", "__sourceDir": "/wrong/path"}):
      with self.subTest(manifest=manifest), tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        plugin = base / "plugin space % # é"
        plugin.mkdir()
        shutil.copyfile(Path(__file__).with_name("Service.qml"), plugin / "Service.qml")
        (plugin / "collect.py").write_text('''import json, os, sys
from pathlib import Path
path = Path(os.environ["XDG_STATE_HOME"]) / "calls.json"
calls = json.loads(path.read_text())
calls.append(sys.argv[1:])
staged = path.with_suffix(".tmp")
staged.write_text(json.dumps(calls))
staged.replace(path)
''')
        calls = base / "calls.json"
        calls.write_text("[]")
        harness = base / "shell.qml"
        harness.write_text('''import QtQuick
import Quickshell
import Quickshell.Io
ShellRoot {
  id: root
  property var service: null
  property int stage: 0
  Component.onCompleted: {
    var component = Qt.createComponent(SERVICE_URL)
    if (component.status !== Component.Ready) {
      console.error(component.errorString())
      Qt.quit()
      return
    }
    service = component.createObject(null, { manifest: MANIFEST })
  }
  FileView { id: calls; path: CALLS_PATH; blockLoading: true; printErrors: false }
  Timer {
    interval: 50; running: true; repeat: true
    onTriggered: {
      calls.reload()
      var records = JSON.parse(calls.text())
      if (records.length > root.stage) {
        root.stage = records.length
        if (root.stage === 1) root.service.collect(true)
        else Qt.quit()
      }
    }
  }
}
'''.replace("SERVICE_URL", json.dumps((plugin / "Service.qml").as_uri()))
           .replace("MANIFEST", json.dumps(manifest))
           .replace("CALLS_PATH", json.dumps(str(calls))))
        runtime = base / "runtime"
        runtime.mkdir(mode=0o700)
        env = dict(os.environ, HOME=tmp, XDG_STATE_HOME=tmp, XDG_CONFIG_HOME=tmp,
                   XDG_CACHE_HOME=tmp, XDG_RUNTIME_DIR=str(runtime), QT_QPA_PLATFORM="offscreen",
                   QT_QPA_PLATFORMTHEME="", QT_STYLE_OVERRIDE="Basic")
        result = subprocess.run(["quickshell", "--no-color", "-p", str(harness)],
                                env=env, text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(calls.read_text())[:2],
                         [["--write"], ["--write", "--force"]],
                         result.stdout + result.stderr)


if __name__ == "__main__":
  unittest.main()
