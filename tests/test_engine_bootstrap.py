"""Ejecuta el bootstrap real del lanzador con una API sintética, sin abrir puertos."""
import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


class EngineBootstrapTests(unittest.TestCase):
    def test_initialization_is_isolated_and_paths_are_arguments(self):
        source = (Path(__file__).resolve().parents[1] / "native/Sources/NEXUS/EngineProcess.swift").read_text()
        code = textwrap.dedent(re.search(r'static let bootstrapCode = """\n(.*?)\n    """', source, re.S)[1])
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "proyecto con espacios; literal"
            packages = Path(folder) / "paquetes con espacios"
            root.mkdir(); packages.mkdir()
            (packages / "uvicorn.py").write_text(textwrap.dedent('''
                def run(module, **kwargs):
                    import json, os, sys
                    print(json.dumps({"cwd": os.getcwd(), "isolated": sys.flags.isolated,
                                      "site_path": sys.path[1], "module": module, **kwargs}))
            '''))
            result = subprocess.run([sys.executable, "-I", "-B", "-u", "-c", code, str(root), str(packages)],
                                    cwd="/", env={**os.environ, "PYTHONPATH": "/not/a/project/path"},
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(Path(payload["cwd"]).resolve(), root.resolve())
            self.assertEqual(payload["isolated"], 1)
            self.assertEqual(payload["site_path"], str(packages))
            self.assertEqual(payload["host"], "127.0.0.1")
            self.assertFalse(payload["reload"])
            self.assertEqual(payload["module"], "web_dashboard:app")
            self.assertLess(result.stderr.index("Python inicializado"), result.stderr.index("Accediendo al proyecto"))
            self.assertLess(code.index("import uvicorn"), code.index("sys.path.insert(0, root)"))

    def test_project_access_failure_is_reported_after_initialization(self):
        source = (Path(__file__).resolve().parents[1] / "native/Sources/NEXUS/EngineProcess.swift").read_text()
        code = textwrap.dedent(re.search(r'static let bootstrapCode = """\n(.*?)\n    """', source, re.S)[1])
        with tempfile.TemporaryDirectory() as folder:
            missing = Path(folder) / "missing"
            result = subprocess.run([sys.executable, "-I", "-B", "-c", code, str(missing), ""],
                                    cwd="/", capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Python inicializado", result.stderr)
        self.assertIn("FileNotFoundError", result.stderr)
