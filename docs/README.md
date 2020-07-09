![BCML Logo](https://i.imgur.com/OiqKPx0.png)

# BCML: BOTW Cross-Platform Mod Loader

A mod merging and managing tool for _The Legend of Zelda: Breath of the Wild_

## Prerequisites

-   Windows 10 (7-8 _might_ work but are not supported) or basically any modern
    Linux distribution
-   A legal, unpacked game dump of _The Legend of Zelda: Breath of the Wild_ for
    Switch (version 1.6.0) or Wii U (version 1.5.0)
-   [The latest x64 Visual C++ redistributable](https://support.microsoft.com/en-us/help/2977003/the-latest-supported-visual-c-downloads#section-2)
-   Cemu (optional)

## Setup

There are three ways to install BCML.

### PyPI

Install Python 3.7+ (**64 bit version**), making sure to add it to your PATH, and then run
`pip install bcml`.

### Windows Installer

Download the setup executable from the
[latest GitHub release](https://github.com/NiceneNerd/BCML/releases/latest) or from
[GameBanana](https://gamebanana.com/tools/6624). Double click to run and install
BCML. Note: It is *highly* recommended that you do not use "Install for all
users."

### Building from Source

Building from source requires, in addition to the general prerequisites:

-   Python 3.7+ 64 bit
-   Node.js v14
-   The following Python packages:
    -   aamp>=1.4.1
    -   byml>=2.3.1
    -   oead>=1.1.1
    -   mkdocs>=1.1.2
    -   mkdocs-material>=5.4.0
    -   pyYaml~=5.3.1
    -   requests~=2.23.0
    -   rstb>=1.2.0
    -   setuptools~=46.4.0
    -   xxhash~=1.4.3
    -   wheel~=0.34.2

Steps to build from source:

1. Prepare the webpack bundle
   1. Open terminal to `bcml/assets`
   2. Run `npm install`
   3. Run `npm build` (or `npm test` to watch while editing)
2. Build the docs
   1. Open terminal to repo root folder
   2. Run `mkdocs build -d bcml/assets/help`
3. Install BCML with `python setup.py install` or run without installing with
   `python -m bcml`

## Usage and Troubleshooting

For information on how to use BCML, see the Help dialog in-app or read the
documentation
[on the repo](https://github.com/NiceneNerd/BCML/tree/master/bcml/docs).
For issues and troubleshooting, please check the official
[Troubleshooting](https://github.com/NiceneNerd/BCML/wiki/Troubleshooting) page.

## Contributing

-   Issues: https://github.com/NiceneNerd/BCML/issues
-   Source: https://github.com/NiceneNerd/BCML

BOTW is an immensely complex game, and there are a number of new mergers that
could be written. If you find an aspect of the game that can be complicated by
mod conflicts, but BCML doesn't yet handle it, feel free to try writing a merger
for it and submitting a PR.

## License

This software is licensed under the terms of the GNU General Public License,
version 3 or later. The source is publicly available on GitHub.

This software includes the 7-Zip console application `7z.exe` and the library
`7z.dll`, which are licensed under the GNU Lesser General Public License. The
source code for this application is available for free at
[https://www.7-zip.org/download.html](https://www.7-zip.org/download.html).

This software includes a lightly modified copy of the console application
`msyt.exe` by Kyle Clemens, copyrighted 2018 under the MIT License. The source
code for this application is available for free at
[https://gitlab.com/jkcclemens/msyt](https://gitlab.com/jkcclemens/msyt). The
only change is a replacement of `serde_yaml` with `serde_json`.

This software includes part of a modified copy of the `pywebview` Python package,
copyrighted 2020 Roman Sirokov under the BSD-3-Clause License. The source code
for the original library is available for free at
[https://github.com/r0x0r/pywebview](https://github.com/r0x0r/pywebview).
