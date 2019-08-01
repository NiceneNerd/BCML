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

## How to Use

![BCML Preview](https://i.imgur.com/0ebIh5M.png)

### General Notes

- Mods can be installed from ZIP, RAR, or 7Z files, or from an unzipped graphic pack folder.
- Only mods with a `rules.txt` file for Cemu graphics pack file replacement are suppported. If you want to convert an older mod, you might find help from [this guide](https://gamebanana.com/tuts/12493).
- While BCML tries to resolve as many conflicts as possible between mods, some mods simply will not work together. They may need to be merged manually or may be irreconcilable. For more information about resolving mod conflicts, see [the article on ZeldaMods.org](https://zeldamods.org/wiki/Help:Resolving_mod_conflicts).
- **Important note:** While it is possible to use BCML for some mods and install others manually, no compatibility is guaranteed. Using BCML together with other install methods is *not* supported.

### Installing Mods

1. Click "Install" on the main BCML window.
2. Queue mods to install by using "Add Mod File" or "Add Mod from Folder." You may also remove, rearrange, or clear the install queue. Mods will be installed in the order in which they are listed.
3. (Optional) Select any advanced options you may need. Note that these will be applied to all mods in the install queue, so if you need different options for different mods you will need to install them separately.
4. Click "Ok" to install the selected mods.

#### Notes on Advanced Options

Advanced options should not be necessary for most mods. However, there are a few possible uses.

*RSTB Options*
- "Shrink RSTB values where possible" - By default, BCML will not adjust RSTB entries if the new size would be smaller. You can use this option to instead shrink them if you have good reason to believe it will improve the stability of your installation.
- "Don't remove complex RSTB entries" - By default, BCML will delete RSTB entries for complex file types (e.g. AAMP, BFRES), since the proper value cannot be calculated. You can use this option to disable this behavior, but know that it can cause instability.

*Merge Options*

By default, BCML will attempt to merge changes between mods for modified pack files, game texts, actor info, game data, and save data. All of these can be disabled if you know you don't need them for a particular mod or group of mods.

*Deep Merge*

Deep merge is an optional, experimental feature which attempts to merge changes made to individual files of certain kinds (BYML and AAMP). This can be a powerful tool to resolve conflicts but can in some cases cause unexpected bugs.

### Managing Mods

Once you have installed one or more mods, you will be able to manage them in the main BCML window.

*Managing Load Order*



## Known Issues

None yet, let me know!

## License

This software is licensed under the terms of the GNU General Public License, version 3 or later.

This software includes the 7-Zip console application `7z.exe` and the library `7z.dll`, which are licensed under the GNU Lesser General Public License. The source code for this application is available for free at [https://www.7-zip.org/download.html](https://www.7-zip.org/download.html).

This software includes the console application `msyt.exe` by Kyle Clemens, copyrighted 2018 under the MIT License. The source code for this application is available for free at [https://gitlab.com/jkcclemens/msyt](https://gitlab.com/jkcclemens/msyt).
