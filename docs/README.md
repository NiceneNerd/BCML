![BCML Logo](https://raw.githubusercontent.com/NiceneNerd/BCML/master/bcml/data/logo.png)

# Breath of the Wild Cemu Mod Loader
A mod installer and manager for BoTW mods on Cemu

## Dependencies

* Cemu (duh)
* A dumped copy of *The Legend of Zelda: Breath of the Wild* for Wii U
* Python 3.7 (64-bit, added to system PATH)

The following `pip` packages, which will be automatically installed:
* [`aamp`](https://pypi.org/project/aamp/)
* [`byml`](https://pypi.org/project/byml/)
* [`diff-match-patch`](https://pypi.org/project/diff-match-patch/)
* [`PySide2`](https://pypi.org/project/PySide2/)
* [`pyYaml`](https://pypi.org/project/PyYAML/)
* [`rstb`](https://pypi.org/project/rstb/)
* [`sarc`](https://pypi.org/project/sarc/)
* [`wszst_yaz0`](https://pypi.org/project/wszst-yaz0/)
* [`xxhash`](https://pypi.org/project/xxhash/)

## Setup

First, make sure you have Python 3.7 64 bit installed and in your system PATH. For more information about this, you can view this

BCML is available through Python's `pip` installer, so just run: `pip install bcml`

Alternatively, you can clone the repository, and then run `python setup.py install` from the BCML root folder.

On first use, you will have to specify the directory to which Cemu is installed.

**Notice:** While it is certainly possible to use BCML for some mods and install others manually, no compatibility is guaranteed. It is recommended to uninstall all Cemu mods before using BCML, and then to reinstall them through BCML.

## Supported Mods

- Mods must be packed as ZIP, 7z, or  RAR archives.
- Only mods with a `rules.txt` file for Cemu graphics pack file replacement are suppported. If you want to convert an older mod, you might find help from [this guide](https://gamebanana.com/tuts/12493).

## GUI Usage

As of version 0.98, BCML now includes a graphical user interface. Hopefully this is simpler for everyone. You can run the graphical BCML simply by:

```
bcml-gui
```

You can also create a shortcut on your desktop if you wish. The path to the executable is will be in the "Scripts" folder in your Python installation (e.g. `C:\Python37\Scripts\bcml-gui.exe`), and an icon is included in the data folder where the BCML package is installed (e.g. `C:\Python37\Lib\site-packages\bcml\data\bcml.ico`).

The interface is previewed below and seems fairly self-explanatory. If you need more details, check the detailed reference for the CLI version below.

![BCML Preview](https://i.imgur.com/0ebIh5M.png)

## Known Issues

None yet, let me know!

## License

This software is licensed under the terms of the GNU General Public License, version 3 or later.

This software includes the 7-Zip console application `7z.exe` and the library `7z.dll`, which are licensed under the GNU Lesser General Public License. The source code for this application is available for free at [https://www.7-zip.org/download.html](https://www.7-zip.org/download.html).

This software includes the console application `msyt.exe` by Kyle Clemens, copyrighted 2018 under the MIT License. The source code for this application is available for free at [https://gitlab.com/jkcclemens/msyt](https://gitlab.com/jkcclemens/msyt).