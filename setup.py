# pylint: disable=invalid-name
import os
from sys import argv
from pathlib import Path
from setuptools import setup

with open("docs/README.md", "r") as readme:
    long_description = readme.read()

setup(
    name="bcml",
    version="3.9.0-beta6",
    author="NiceneNerd",
    author_email="macadamiadaze@gmail.com",
    description="A mod manager for The Legend of Zelda: Breath of the Wild",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/NiceneNerd/BCML",
    include_package_data=True,
    packages=["bcml"],
    package_dir={"bcml": "bcml"},
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
    install_requires=Path("requirements.txt").read_text().splitlines(),
    zip_safe=False,
)