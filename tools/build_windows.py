"""Reproducible preview build, leaving previous dist and user data untouched."""

from pathlib import Path
import subprocess
import sys
import os
import shutil
from importlib.metadata import distribution, PackageNotFoundError

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.3.0-preview"


def main():
    args = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--distpath",
        str(ROOT / "outputs" / f"windows-{VERSION}"),
        "--workpath",
        str(ROOT / "work" / "pyinstaller-v030"),
        str(ROOT / "packaging" / "colorlab.spec"),
    ]
    environment = os.environ.copy()
    for variable, folder in (
        ("PYINSTALLER_CONFIG_DIR", "pyinstaller-cache"),
        ("TEMP", "build-temp"),
        ("TMP", "build-temp"),
    ):
        local = ROOT / "work" / folder
        local.mkdir(parents=True, exist_ok=True)
        environment[variable] = str(local)
    # Limit this change to the build child; never edit the user's global PATH.
    environment["PATH"] = os.pathsep.join(
        part
        for part in environment.get("PATH", "").split(os.pathsep)
        if "poppler" not in part.lower()
    )
    code = subprocess.call(args, cwd=ROOT, env=environment)
    if code == 0:
        package = ROOT / "outputs" / f"windows-{VERSION}" / "FrameSenseColorLab"
        manifest = [
            "FrameSense 0.3.0-preview\n",
            "Bundled dependency license texts are kept in THIRD_PARTY_LICENSES.\n",
        ]
        for name in (
            "numpy",
            "pillow",
            "colour-science",
            "rawpy",
            "PySide6",
            "PySide6_Addons",
            "PySide6_Essentials",
            "shiboken6",
            "pydantic",
            "pydantic_core",
            "scipy",
        ):
            try:
                dependency = distribution(name)
            except PackageNotFoundError:
                continue
            manifest.append(f"{name} {dependency.version}")
            for item in dependency.files or []:
                parts = item.parts
                if not any(".dist-info" in p for p in parts):
                    continue
                if not (
                    "licenses" in parts
                    or item.name.lower().startswith(("license", "copying", "notice"))
                ):
                    continue
                source = dependency.locate_file(item)
                if source.is_file():
                    target = package / "THIRD_PARTY_LICENSES" / name / Path(*parts[1:])
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
        (package / "THIRD_PARTY_NOTICES.txt").write_text(
            "\n".join(manifest) + "\n", encoding="utf-8"
        )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
