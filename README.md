# Breath of the Wild Cemu Mod Loader
A mod installer and manager for BoTW mods on Cemu

## Dependencies

* Cemu (duh)
* Python 3.7 (64-bit, installed to system PATH)

The following `pip` packages
* [`sarc`](https://pypi.org/project/sarc/)
* [`rarfile`](https://pypi.org/project/rarfile/)
* [`rstbtool`](https://pypi.org/project/rstb/)
* [`wszst_yaz0`](https://pypi.org/project/wszst-yaz0/)
* [`xxhash`](https://pypi.org/project/xxhash/)

## Setup

First, make sure you have all the dependencies. If you don't, install them.

Next, until I get around to making a `pip` package, either:

* Clone the repository to your root Cemu folder, e.g. `C:\Cemu\BCML`, or
* Download the release ZIP and unzip to your root Cemu folder, e.g. `C:\Cemu\BCML`

You *can* put BCML elsewhere if you want. You'll just need to specify the `graphicPacks` directory when you run it.

**Notice:** While it is certainly possible to use BCML for some mods and install others manually, no compatibility is guaranteed. It is recommended to uninstall all Cemu mods before using BCML, and then to reinstall them through BCML.

## Supported Mods

- Mods must be packed as ZIP, 7z, or  RAR archives.
- Only mods with a `rules.txt` file for Cemu graphics pack file replacement are suppported. If you want to convert an older mod, you might find help from [this guide](https://gamebanana.com/tuts/12493).

## Usage

Run all commands from within the BCML folder wherever you extracted it.

### Install a Mod

```
python install.py SuperCoolMod.zip
```

That's the gist of it. More detailed usage information:

```
usage: install.py [-h] [-s] [-r] [-p PRIORITY] [-d DIRECTORY] [--nomerge] [-v] mod

A tool to install and manage mods for Breath of the Wild in CEMU

positional arguments:
  mod                   Path to a ZIP or RAR archive containing a BOTW mod in Cemu 1.15+ format

optional arguments:
  -h, --help            show this help message and exit
  -s, --shrink          Update RSTB entries for files which haven't grown
  -l, --leave           Do not remove RSTB entries for file sizes which cannot be calculated
  -p PRIORITY, --priority PRIORITY
                        Mod load priority, default starts at 100 for first mod
  -d DIRECTORY, --directory DIRECTORY
                        Specify path to Cemu graphicPacks folder, default assumes relative path from BCML install directory
  --nomerge             Do not automatically merge pack files
  -v, --verbose         Verbose output covering every file processed
  ```

  More details on each argument:

  * `--shrink`: By default, BCML will ignore files with equal or smaller sizes to what was originally in the RSTB. This option forces it to update anyway. I can't think of any reason to use this except as a last ditch effort to stop blood moon spam on a heavily modded setup.
  * `--leave`: By default, BCML will delete RSTB entries when the RSTB size of a file cannot be calculated. This option leaves them alone. *Be warned: This can cause instability.*
  * `--priority`: This specifies the load priority of the mod. By default, mods start with a priority of 100 and go up by 1 for each installation. Higher priority mods will overwrite conflicting changes from lower priority ones.
  * `--directory`: By default, BCML assumes that its installation folder is inside the Cemu folder, and looks for the `graphicPacks` folder from its parent. This option allows specifying the location of the `graphicPacks` folder.
  * `--nomerge`: By default, BCML will try to merge changes when multiple mods modify the same pack files. Sometimes this will break things when mods have completely incompatible changes. This option disables pack merging on the current mod. Any packs with conflicting changes will either give way to or trump the whole pack depending on load priority.
  * `--verbose`: Obviously, this option provides very detailed information about nearly every step of the mod installation process.

### Uninstall a Mod

```
python uninstall.py
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

Pick one and it will be uninstalled. The RSTB will be regenerated, and any merged packs will be reprocessed. This script has only a couple arguments:

```
usage: uninstall.py [-h] [-d DIRECTORY] [-v]
Uninstaller for BCML-managed mods

optional arguments:
  -h, --help            show this help message and exit
  -d DIRECTORY, --directory DIRECTORY
                        Specify path to Cemu graphicPacks folder, default assumes relative path from BCML install directory
  -v, --verbose         Verbose output covering every file processed
```

### Update Mod Configuration

```
python update.py
```

If you make any manual changes to mods installed with BCML, run this script afterwards to make sure any necessary updates to the RSTB or to merged packs are made. This script has only a couple arguments.

```
usage: update.py [-h] [-d DIRECTORY] [-v]

Refreshes RSTB and merged packs for BCML-managed mods

optional arguments:
  -h, --help            show this help message and exit
  -d DIRECTORY, --directory DIRECTORY
                        Specify path to Cemu graphicPacks folder, default assumes relative path from BCML install directory
  -v, --verbose         Verbose output covering every file processed
```

### Export Mod Configuration

```
python export.py LotsOfCoolMods.zip
```

This script exports all of your installed mods, including the BCML merges, into a single modpack. By default, it exports in graphicPack format, but it also supports SDCafiine and the MLC folder in Cemu (or on the Wii U). Usage info:

```
usage: export.py [-h] [-d DIRECTORY] [-o] [-s | -m] [-t TITLE] output

Exports BCML-managed files as a standalone mod

positional arguments:
  output                Path to the mod ZIP that BCML should create

optional arguments:
  -h, --help            show this help message and exit
  -d DIRECTORY, --directory DIRECTORY
                        Specify path to Cemu graphicPacks folder, default assumes relative path from BCML install directory
  -o, --onlymerges      Only include the merged RSTB and packs, not all installed content
  -s, --sdcafiine       Export in SDCafiine format instead of graphicPack
  -m, --mlc             Export in the MLC content format instead of graphicPack
  -t TITLE, --title TITLE
                        The TitleID to use for SDCafiine or mlc export, default 00050000101C9400 (US version)
```

More details on each argument (except `--directory`, because it's been covered):

* `--onlymerges`: By default, BCML will create a zip with the whole contents of all your active mod files. This option exports *only* the RSTB and any packs which BCML has merged. I'm not entirely sure why you might need this, but it's here in case you do.
* `--sdcafiine`: By default, BCML exports to Cemu's graphicPack format. This option exports to a format which can be easily used with SDCafiine on your Wii U instead.
* `--mlc`: By default, BCML exports to Cemu's graphicPack format. This option exports to a format that can be extracted directly into the MLC directory for Cemu or on your Wii U using FTPiiU.
* `--title`: By default, BCML assumes you are using the US version of BOTW. Use this option with SDCafiine or MLC exports to specify the TitleID for another region.

## Known Bugs

* At present, this probably only works completely with the US version of the game. I don't yet have hashes or complete RSTB info for non-US versions. If you would like to help with that, open an issue.

## License

This software is licensed under the terms of the GNU General Public License, version 3 or later.

This software includes the 7-Zip console application `7za.exe`, which is licensed under the GNU Lesser General Public License. The source code for this application is available for free at [https://www.7-zip.org/download.html](https://www.7-zip.org/download.html).
