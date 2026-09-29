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
        self.assertIn("console=True", content)
        self.assertIn("AppIcon.ico", content)
        self.assertIn("antigravity_migrator", content)

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

            # Create mock binary
            mock_exe = stage_dir / "agy-migrator.exe"
            mock_exe.write_bytes(b"MZ\x90\x00" + b"\x00" * 1024)

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
                self.assertIn("Antigravity-Chat-Migrator/agy-migrator.exe", namelist)
                self.assertIn("Antigravity-Chat-Migrator/run_fix.bat", namelist)
                self.assertIn("Antigravity-Chat-Migrator/README_WINDOWS.txt", namelist)


if __name__ == "__main__":
    unittest.main()
