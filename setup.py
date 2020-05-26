import os
from setuptools import setup
from subprocess import run
from sys import argv
from pathlib import Path
from bcml.__version__ import VERSION

installer_cfg = Path("installer.cfg")
if installer_cfg.exists() and "sdist" in argv:
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
    description="A mod manager for The Legend of Zelda: Breath of the Wild on Cemu",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/NiceneNerd/BCML",
    include_package_data=True,
    packages=["bcml"],
    entry_points={
        "gui_scripts": ["bcml = bcml.__main__:main"],
        "console_scripts": ["bcml-debug = bcml.__main__:main_debug"],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3 :: Only",
    ],
    python_requires=">=3.7",
    install_requires=[
        "aamp>=1.4.1",
        "byml>=2.3.1",
        "cefpython3>=66.0 ; platform_system=='Windows'",
        "oead>=1.1.1",
        "pywebview~=3.2",
        "PyYAML~=5.3.1",
        "requests~=2.23.0",
        "rstb>=1.2.0",
        "xxhash~=1.4.3",
    ],
    zip_safe=False,
)
