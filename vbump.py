from pathlib import Path
import sys

version = sys.argv[1]
major, minor, patch = version.split(".")

setup = Path("setup.py")
setup_text = setup.read_text().splitlines()
for i, line in enumerate(setup_text):
    if "version=" in line:
        setup_text[i] = f'    version="{version}",'
setup.write_text("\n".join(setup_text))

version_file = Path("bcml/__version__.py")
version_file_text = version_file.read_text().splitlines()
version_file_text[0:3] = [f"_MAJOR={major}", f"_MINOR={minor}", f'_PATCH="{patch}"']
version_file.write_text("\n".join(version_file_text))

cargo = Path("Cargo.toml")
cargo_text = cargo.read_text().splitlines()
for i, line in enumerate(cargo_text):
    if line.startswith("version"):
        cargo_text[i] = f'version = "{version}"'
cargo.write_text("\n".join(cargo_text))

pyproject = Path("pyproject.toml")
pyproject_text = pyproject.read_text().splitlines()
for i, line in enumerate(pyproject_text):
    if line.startswith("version"):
        pyproject_text[i] = f'version = "{version}"'
pyproject.write_text("\n".join(pyproject_text))

