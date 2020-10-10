# pylint: disable=invalid-name
import os
from sys import argv
from pathlib import Path
from setuptools import setup
from bcml.__version__ import VERSION

installer_cfg = Path("installer.cfg")
if installer_cfg.exists() and "sdist" in argv or "bdist_wheel" in argv:
    text = installer_cfg.read_text().splitlines()
    text[3] = f"version={VERSION}"
    installer_cfg.write_text("\n".join(text))

if "install" in argv and os.name == "posix":
    os.chmod("bcml/helpers/7z", int("755", 8))
    os.chmod("bcml/helpers/msyt", int("755", 8))

with open("docs/README.md", "r") as readme:
    long_description = readme.read()

setup(
    name="bcml",
    version=VERSION,
    author="NiceneNerd",
    author_email="macadamiadaze@gmail.com",
    description="A mod manager for The Legend of Zelda: Breath of the Wild",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/NiceneNerd/BCML",
    include_package_data=True,
    packages=["bcml", "webviewb", "webviewb.js", "webviewb.platforms"],
    package_dir={"webviewb": "webviewb", "bcml": "bcml"},
    package_data={
        "webviewb": [
            "webviewb/lib/Microsoft.WindowsAPICodePack.dll",
            "webviewb/lib/Microsoft.WindowsAPICodePack.Shell.dll",
        ],
    },
    entry_points={
        "gui_scripts": ["bcml = bcml.__main__:main"],
        "console_scripts": [
            "bcml-debug = bcml.__main__:main_debug",
        ],
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3 :: Only",
    ],
    python_requires=">=3.7",
    install_requires=[
        "aamp>=1.4.1",
        "byml>=2.3.1",
        "botw-utils==0.2.3",
        "cefpython3~=66.0",
        "oead>=1.1.4",
        "pythonnet>=2.5.0rc2; platform_system=='Windows'",
        "PyYAML~=5.3.1",
        "requests~=2.23.0",
        "rstb>=1.2.0",
        "xxhash~=1.4.3",
    ],
    zip_safe=False,
)
