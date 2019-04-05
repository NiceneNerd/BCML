# Breath of the Wild Cemu Mod Loader
A mod installer and manager for BoTW mods on Cemu

## Dependencies

* Cemu (duh)
* Python 3.7 (64-bit)

The following `pip` packages
* [`sarc`](https://pypi.org/project/sarc/)
* [`rarfile`](https://pypi.org/project/rarfile/)
* [`rstbtool`](https://pypi.org/project/rstb/)
* [`wszst_yaz0`](https://pypi.org/project/wszst-yaz0/)
* [`xxhash`](https://pypi.org/project/xxhash/)

## Setup

Until I figure out how to make a `pip` package, either:

* Clone the repository to your root CEMU folder, e.g. `C:\Cemu\BCML`, or
* Download the release ZIP and unzip to your root CEMU folder, e.g. `C:\Cemu\BCML`

You *can* put BCML elsewhere if you want. You'll just need to specify the `graphicPacks` directory when you run it.

## Supported Mods

- Mods must be packed as ZIP and RAR archives
- *7z is **not** currently supported.* This may change in a future release. If necessary, you can manually extract a 7z mod and then make a new ZIP.
- Only mods with a `rules.txt` file for Cemu graphics pack file replacement are suppported. If you want to convert an older mod, you might find help from [this guide](https://gamebanana.com/tuts/12493).

## Usage

Run all commands from within the BCML folder wherever you extracted it.

### Install a Mod

```
python .\install SuperCoolMod.zip
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
  * `--verbose`: Obviously, this option provides very detailed information about neartly every step of the mod installation process.