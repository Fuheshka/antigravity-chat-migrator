"""Tests for Windows packaging pipeline, spec validation, and distribution staging."""

import ast
import os
import re
import tempfile
import unittest
import zipfile
from pathlib import Path
from PIL import Image

import importlib.util

def _load_generate_ico_fn(script_path: Path):
    spec = importlib.util.spec_from_file_location("generate_ico_mod", str(script_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.generate_ico


class TestPackagingWindows(unittest.TestCase):
    """Verify all artifacts, scripts, and spec configurations for Windows distribution."""

    def setUp(self):
        self.repo_root = Path(__file__).resolve().parent.parent
        self.windows_pkg_dir = self.repo_root / "packaging" / "windows"
        self.assets_dir = self.repo_root / "packaging" / "assets"

    def test_all_required_files_exist(self):
        """Verify all mandated Windows packaging files exist in packaging/windows/."""
        required = [
            "migrator.spec",
            "build_windows.ps1",
            "build_windows.bat",
            "run_fix.bat",
            "README_WINDOWS.txt",
            "entrypoint.py",
            "gui_entrypoint.py",
            "generate_ico.py",
        ]
        for fname in required:
            target = self.windows_pkg_dir / fname
            self.assertTrue(target.is_file(), f"Missing required file: {target}")

    def test_spec_file_validity(self):
        """Verify migrator.spec can be parsed as valid Python AST and contains required config."""
        spec_file = self.windows_pkg_dir / "migrator.spec"
        content = spec_file.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(spec_file))
        self.assertGreater(len(tree.body), 0)

        # Check critical settings
        self.assertIn("agy-migrator", content)
        self.assertIn("Antigravity Chat Migrator", content)
        self.assertIn("gui_entrypoint.py", content)
        self.assertIn("entrypoint.py", content)
        self.assertIn("AppIcon.ico", content)
        self.assertIn("antigravity_migrator", content)
        self.assertIn("antigravity_migrator/gui", content)
        self.assertIn("webview", content)
        self.assertIn("webview.platforms.winforms", content)
        self.assertIn("webview.platforms.edgechromium", content)
        self.assertIn("typer", content)
        self.assertIn("rich", content)

        # AST analysis: verify dual-binary targets share single Analysis and PYZ
        analysis_calls = []
        pyz_calls = []
        exe_calls = {}

        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and isinstance(node.value, ast.Call):
                        func_name = getattr(node.value.func, "id", None)
                        if func_name == "Analysis":
                            analysis_calls.append(target.id)
                        elif func_name == "PYZ":
                            pyz_calls.append(target.id)
                        elif func_name == "EXE":
                            # Extract name and console arguments
                            kwargs = {kw.arg: kw.value for kw in node.value.keywords}
                            name_val = None
                            if "name" in kwargs:
                                if isinstance(kwargs["name"], ast.Constant):
                                    name_val = kwargs["name"].value
                            console_val = None
                            if "console" in kwargs:
                                if isinstance(kwargs["console"], ast.Constant):
                                    console_val = kwargs["console"].value
                            exe_calls[target.id] = {"name": name_val, "console": console_val}

        # Single Analysis and PYZ shared across builds
        self.assertEqual(len(analysis_calls), 1, "Expected exactly 1 shared Analysis target")
        self.assertEqual(len(pyz_calls), 1, "Expected exactly 1 shared PYZ target")

        # Two EXE targets: exe_gui and exe_cli
        self.assertIn("exe_gui", exe_calls, "Missing exe_gui target in migrator.spec")
        self.assertIn("exe_cli", exe_calls, "Missing exe_cli target in migrator.spec")

        self.assertIn("Antigravity Chat Migrator", exe_calls["exe_gui"]["name"])
        self.assertFalse(exe_calls["exe_gui"]["console"], "exe_gui must have console=False")

        self.assertIn("agy-migrator", exe_calls["exe_cli"]["name"])
        self.assertTrue(exe_calls["exe_cli"]["console"], "exe_cli must have console=True")

    def test_entrypoints_contract(self):
        """Verify gui_entrypoint.py calls launch_gui() and entrypoint.py calls app()."""
        gui_ep = self.windows_pkg_dir / "gui_entrypoint.py"
        cli_ep = self.windows_pkg_dir / "entrypoint.py"
        self.assertTrue(gui_ep.is_file(), f"gui_entrypoint.py missing at {gui_ep}")
        self.assertTrue(cli_ep.is_file(), f"entrypoint.py missing at {cli_ep}")

        gui_content = gui_ep.read_text(encoding="utf-8")
        self.assertIn("launch_gui", gui_content)

        cli_content = cli_ep.read_text(encoding="utf-8")
        self.assertIn("app", cli_content)

    def test_generate_ico_functionality(self):
        """Verify generate_ico creates valid multi-resolution ICO file."""
        src_png = self.assets_dir / "AppIcon.png"
        self.assertTrue(src_png.is_file(), f"Source icon not found at {src_png}")

        with tempfile.TemporaryDirectory() as td:
            out_ico = Path(td) / "test_icon.ico"
            gen_fn = _load_generate_ico_fn(self.windows_pkg_dir / "generate_ico.py")
            gen_fn(src_png, out_ico)

            self.assertTrue(out_ico.is_file())
            self.assertGreater(out_ico.stat().st_size, 10000)

            # Verify with PIL
            with Image.open(out_ico) as img:
                self.assertEqual(img.format, "ICO")

    def test_batch_script_syntax_and_labels(self):
        """Verify batch scripts have balanced parentheses and valid goto targets."""
        for bat_name in ["build_windows.bat", "run_fix.bat"]:
            bat_path = self.windows_pkg_dir / bat_name
            text = bat_path.read_text(encoding="utf-8")

            # Check goto labels
            labels = set(re.findall(r"^\s*:([a-zA-Z0-9_-]+)", text, re.MULTILINE))
            gotos = re.findall(r"goto\s+([a-zA-Z0-9_-]+)", text, re.IGNORECASE)
            for g in gotos:
                if g.lower() == "eof":
                    continue
                self.assertIn(g, labels, f"Missing label :{g} in {bat_name}")

            # Check balanced brackets
            counts = {"(": 0}
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith("rem") or stripped.startswith("::"):
                    continue
                for char in line:
                    if char == "(":
                        counts["("] += 1
                    elif char == ")":
                        counts["("] -= 1
            self.assertEqual(counts["("], 0, f"Unbalanced parentheses in {bat_name}")

        # Check run_fix.bat CLI targets
        run_fix_text = (self.windows_pkg_dir / "run_fix.bat").read_text(encoding="utf-8")
        self.assertIn("agy-migrator.exe", run_fix_text)
        self.assertIn("audit", run_fix_text)
        self.assertIn("fix", run_fix_text)

    def test_powershell_script_syntax(self):
        """Verify PowerShell build script has balanced braces, brackets, and quotes."""
        ps1_path = self.windows_pkg_dir / "build_windows.ps1"
        text = ps1_path.read_text(encoding="utf-8")

        counts = {"{": 0, "(": 0, "[": 0}
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            for char in line:
                if char in "{([":
                    counts[char] += 1
                elif char == "}":
                    counts["{"] -= 1
                elif char == ")":
                    counts["("] -= 1
                elif char == "]":
                    counts["["] -= 1
        self.assertEqual(counts["{"], 0, "Unbalanced { in build_windows.ps1")
        self.assertEqual(counts["("], 0, "Unbalanced ( in build_windows.ps1")
        self.assertEqual(counts["["], 0, "Unbalanced [ in build_windows.ps1")

    def test_staging_and_zip_creation_simulation(self):
        """Simulate packaging pipeline creating the portable ZIP distribution."""
        with tempfile.TemporaryDirectory() as td:
            stage_dir = Path(td) / "staging" / "Antigravity-Chat-Migrator"
            stage_dir.mkdir(parents=True)

            # Create mock binaries (GUI and CLI)
            mock_gui_exe = stage_dir / "Antigravity Chat Migrator.exe"
            mock_gui_exe.write_bytes(b"MZ\x90\x00" + b"\x00" * 1024)
            mock_cli_exe = stage_dir / "agy-migrator.exe"
            mock_cli_exe.write_bytes(b"MZ\x90\x00" + b"\x00" * 1024)

            # Copy launcher and docs
            import shutil
            shutil.copy(self.windows_pkg_dir / "run_fix.bat", stage_dir / "run_fix.bat")
            shutil.copy(self.windows_pkg_dir / "README_WINDOWS.txt", stage_dir / "README_WINDOWS.txt")

            # Create zip
            zip_dest = Path(td) / "Antigravity-Chat-Migrator-Windows-x64.zip"
            with zipfile.ZipFile(zip_dest, "w", zipfile.ZIP_DEFLATED) as zf:
                for file_path in stage_dir.rglob("*"):
                    if file_path.is_file():
                        arcname = file_path.relative_to(stage_dir.parent)
                        zf.write(file_path, arcname)

            self.assertTrue(zip_dest.is_file())

            # Verify contents of zip
            with zipfile.ZipFile(zip_dest, "r") as zf:
                namelist = zf.namelist()
                self.assertIn("Antigravity-Chat-Migrator/Antigravity Chat Migrator.exe", namelist)
                self.assertIn("Antigravity-Chat-Migrator/agy-migrator.exe", namelist)
                self.assertIn("Antigravity-Chat-Migrator/run_fix.bat", namelist)
                self.assertIn("Antigravity-Chat-Migrator/README_WINDOWS.txt", namelist)


if __name__ == "__main__":
    unittest.main()
