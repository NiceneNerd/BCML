![BCML Logo](https://raw.githubusercontent.com/NiceneNerd/BCML/master/bcml/data/logo.png)

# Breath of the Wild Cemu Mod Loader
A mod installer and manager for BoTW mods on Cemu

## Dependencies

* Cemu (duh)
* Python 3.7 (64-bit, installed to system PATH)

The following `pip` packages, which will be automatically installed:
* [`sarc`](https://pypi.org/project/sarc/)
* [`rarfile`](https://pypi.org/project/rarfile/)
* [`rstbtool`](https://pypi.org/project/rstb/)
* [`wszst_yaz0`](https://pypi.org/project/wszst-yaz0/)
* [`xxhash`](https://pypi.org/project/xxhash/)

## Setup

First, make sure you have Python 3.7 64-bit installed and in your system PATH.

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

![BCML](https://i.imgur.com/Qa3w4k7.png)

## CLI Usage

All BCML commands take the following arguments:

```
  -h, --help            show this help message and exit
  -d DIRECTORY, --directory DIRECTORY
                        Specify path to Cemu graphicPacks folder, if different from saved
  -v, --verbose         Verbose output covering every file processed
```

Running `bcml` by itself with no arguments will list installed mods like so:

```
No command given, listing mods currently installed:

Modified Beedle Shop — Priority: 100
"Amiibo Chest Items Mod" — Priority: 101
"Disable_Fast_Travel" — Priority: 102
Unobtainable Chests Fix — Priority: 103
Hyrule Rebalance v4.0 — Priority: 109
Linkle Mod — Priority: 110
```

### Install a Mod

```
bcml install SuperCoolMod.zip
```

That's the gist of it. More detailed usage information:

```
usage: bcml install [-h] [-p PRIORITY] [--nomerge] [-s] [-l] mod

positional arguments:
  mod                   Path to a ZIP or RAR archive containing a BOTW mod in Cemu 1.15+ format

optional arguments:
  -h, --help            show this help message and exit
  -p PRIORITY, --priority PRIORITY
                        Mod load priority, default 100
  --nomerge             Do not automatically merge pack files
  -s, --shrink          Update RSTB entries for files which haven't grown
  -l, --leave           Do not remove RSTB entries for file sizes which cannot be calculated
  ```

  More details on each argument:

  * `--priority`: This specifies the load priority of the mod. By default, mods start with a priority of 100 and go up by 1 for each installation. Higher priority mods will overwrite conflicting changes from lower priority ones.
  * `--nomerge`: By default, BCML will try to merge changes when multiple mods modify the same pack files. Sometimes this will break things when mods have completely incompatible changes. This option disables pack merging on the current mod. Any packs with conflicting changes will either give way to or trump the whole pack depending on load priority.
  * `--shrink`: By default, BCML will ignore files with equal or smaller sizes to what was originally in the RSTB. This option forces it to update anyway. I can't think of any reason to use this except as a last ditch effort to stop blood moon spam on a heavily modded setup.
  * `--leave`: By default, BCML will delete RSTB entries when the RSTB size of a file cannot be calculated. This option leaves them alone. *Be warned: This can cause instability.*

### Uninstall a Mod

```
bcml uninstall
```

Dead simple. Run this script and you will be presented with a list of installed mods like so:

```
1. Modified Beedle Shop — Priority: 100
2. Double Durability — Priority: 101
3. "Disable_Fast_Travel" — Priority: 102
4. Upgraded Hylian Shield — Priority: 103
5. Hyrule Rebalance v4.0 — Priority: 175
6. "Lantern" — Priority: 150
7. First Person Quest Dialogs — Priority: 200

Enter the number of the mod you would like to uninstall:
```

Pick one and it will be uninstalled. The RSTB will be regenerated, and any merged packs will be reprocessed.

### Update Mod Configuration

```
bcml update
```

If you make any manual changes to mods installed with BCML, run this script afterwards to make sure any necessary updates to the RSTB or to merged packs are made.

### Export Mod Configuration

```
bcml export LotsOfCoolMods.zip
```

This script exports all of your installed mods, including the BCML merges, into a single modpack. By default, it exports in graphicPack format, but it also supports SDCafiine and the MLC folder in Cemu (or on the Wii U). Usage info:

```
usage: bcml export [-h] [-o] [-s | -m] [-t TITLE] output

positional arguments:
  output                Path to the mod ZIP that BCML should create

optional arguments:
  -h, --help            show this help message and exit
  -o, --onlymerges      Only include the merged RSTB and packs, not all installed content
  -s, --sdcafiine       Export in SDCafiine format instead of graphicPack
  -m, --mlc             Export in the mlc content format instead of graphicPack
  -t TITLE, --title TITLE
                        The TitleID to use for SDCafiine or mlc export, default 00050000101C9400 (US version)
```

More details on each argument:

* `--onlymerges`: By default, BCML will create a zip with the whole contents of all your active mod files. This option exports *only* the RSTB and any packs which BCML has merged. I'm not entirely sure why you might need this, but it's here in case you do.
* `--sdcafiine`: By default, BCML exports to Cemu's graphicPack format. This option exports to a format which can be easily used with SDCafiine on your Wii U instead.
* `--mlc`: By default, BCML exports to Cemu's graphicPack format. This option exports to a format that can be extracted directly into the MLC directory for Cemu or on your Wii U using FTPiiU.
* `--title`: By default, BCML assumes you are using the US version of BOTW. Use this option with SDCafiine or MLC exports to specify the TitleID for another region.

## Known Bugs

* At present, this probably only works completely with the US version of the game. I don't yet have hashes or complete RSTB info for non-US versions. If you would like to help with that, open an issue.

## License

This software is licensed under the terms of the GNU General Public License, version 3 or later.

This software includes the 7-Zip console application `7z.exe` and the library `7z.dll`, which are licensed under the GNU Lesser General Public License. The source code for this application is available for free at [https://www.7-zip.org/download.html](https://www.7-zip.org/download.html).
