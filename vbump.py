from pathlib import Path
import sys

version = sys.argv[1]
major, minor, patch = version.split(".")

installer_cfg = Path("installer.cfg")
if installer_cfg.exists():
    text = installer_cfg.read_text().splitlines()
    text[3] = f"version={version}"
    installer_cfg.write_text("\n".join(text))

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
