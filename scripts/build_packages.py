import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT / "dist"

LAMBDA_MODULES = [
    {
        "name": "image_processor",
        "source": ROOT / "src" / "image_processor",
    },
    {
        "name": "metadata_updater",
        "source": ROOT / "src" / "metadata_updater",
    },
]


def run(cmd, cwd=None):
    print("Running:", " ".join(cmd))
    subprocess.check_call(cmd, cwd=cwd)


def build_lambda_package(name: str, source_dir: Path) -> None:
    build_dir = DIST_DIR / f"{name}_build"
    zip_path = DIST_DIR / f"{name}.zip"

    if build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(source_dir / "app.py", build_dir / "app.py")

    requirements = source_dir / "requirements.txt"
    if requirements.exists():
        run([
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-input",
            "--disable-pip-version-check",
            "-r",
            str(requirements),
            "-t",
            str(build_dir),
        ])

    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in build_dir.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(build_dir))

    print(f"Created {zip_path}")


def main() -> None:
    DIST_DIR.mkdir(exist_ok=True)

    for module in LAMBDA_MODULES:
        build_lambda_package(module["name"], module["source"])

    print("All Lambda packages are ready in ./dist")


if __name__ == "__main__":
    os.chdir(ROOT)
    main()
