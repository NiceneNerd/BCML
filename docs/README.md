![BCML Logo](https://raw.githubusercontent.com/NiceneNerd/BCML/master/bcml/data/logo.png)

# Breath of the Wild Cemu Mod Loader
A mod installer and manager for BoTW mods on Cemu

## Dependencies

* Cemu (duh)
* A dumped copy of *The Legend of Zelda: Breath of the Wild* for Wii U
* Python 3.7 (64-bit, added to system PATH)

The following `pip` packages, which will be *automatically installed*:
* [`aamp`](https://pypi.org/project/aamp/)
* [`byml`](https://pypi.org/project/byml/)
* [`diff-match-patch`](https://pypi.org/project/diff-match-patch/)
* [`PySide2`](https://pypi.org/project/PySide2/)
* [`pyYaml`](https://pypi.org/project/PyYAML/)
* [`rstb`](https://pypi.org/project/rstb/)
* [`sarc`](https://pypi.org/project/sarc/)
* [`wszst-yaz0`](https://pypi.org/project/wszst-yaz0/)
* [`xxhash`](https://pypi.org/project/xxhash/)

## Setup

There are three primary options for installing BCML.

**Option 1: Easy Installer**
1. Download the latest Windows setup executable release.
2. Double click and install it like a normal program.

**Option 2: PIP** 
1. Download and install Python. You **must** use the 64 bit version of Python 3.7 or later. The most recent download as of July 2019 is [here](https://www.python.org/ftp/python/3.7.4/python-3.7.4-amd64.exe). You also **must** choose the "Add to System PATH" option during installation.
2. Open a command line and run: `pip install bcml`
3. Run BCML using the command `bcml`
4. (Optional) Create a shortcut to the BCML executable in Python's `Scripts` folder.

**Option 3: Install from Source**
1. Download and install Python. You **must** use the 64 bit version of Python 3.7 or later. The most recent download as of July 2019 is [here](https://www.python.org/ftp/python/3.7.4/python-3.7.4-amd64.exe). You also **must** choose the "Add to System PATH" option during installation.
2. Download the source code for the latest BCML release or clone the repo.
3. In the directory where you extracted the BCML source, run `python setup.py install`
4. Run BCML using the command `bcml`
5. (Optional) Create a shortcut to the BCML executable in Python's `Scripts` folder.

On first use, you will have to specify the directory where Cemu is installed and the `content` directory of your BotW game dump.

## Supported Mods

- Mods must be packed as ZIP, 7z, or  RAR archives.
- Only mods with a `rules.txt` file for Cemu graphics pack file replacement are suppported. If you want to convert an older mod, you might find help from [this guide](https://gamebanana.com/tuts/12493).
- **Notice:** While it is certainly possible to use BCML for some mods and install others manually, no compatibility is guaranteed. It is recommended to uninstall all Cemu mods before using BCML, and then to reinstall them through BCML.

## How to Use

![BCML Preview](https://i.imgur.com/0ebIh5M.png)

## Known Issues

None yet, let me know!

## License

This software is licensed under the terms of the GNU General Public License, version 3 or later.

This software includes the 7-Zip console application `7z.exe` and the library `7z.dll`, which are licensed under the GNU Lesser General Public License. The source code for this application is available for free at [https://www.7-zip.org/download.html](https://www.7-zip.org/download.html).

This software includes the console application `msyt.exe` by Kyle Clemens, copyrighted 2018 under the MIT License. The source code for this application is available for free at [https://gitlab.com/jkcclemens/msyt](https://gitlab.com/jkcclemens/msyt).
