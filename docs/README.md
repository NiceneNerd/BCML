![BCML Logo](https://i.imgur.com/OiqKPx0.png)

# Breath of the Wild Cemu Mod Loader
A mod installer and manager for BoTW mods on Cemu

## Dependencies

* Cemu (duh)
* A dumped copy of *The Legend of Zelda: Breath of the Wild* for Wii U
* Python 3.7 (64-bit, added to system PATH)

The following `pip` packages, which will be *automatically installed*:
* [`aamp`](https://pypi.org/project/aamp/)
* [`byml`](https://pypi.org/project/byml/)
* [`cython`](https://pypi.org/project/cython/)
* [`libyaz0`](https://pypi.org/project/libyaz0/)
* [`PySide2`](https://pypi.org/project/PySide2/)
* [`pyYaml`](https://pypi.org/project/PyYAML/)
* [`rstb`](https://pypi.org/project/rstb/)
* [`sarc`](https://pypi.org/project/sarc/)
* [`xxhash`](https://pypi.org/project/xxhash/)

## Setup

There are three primary options for installing BCML.

**Option 1: Easy Installer**
1. Download the latest Windows setup executable release.
2. Double click and install it like a normal program. (Note: I recommend choosing "Install just for me" to prevent permissions issues.)

**Option 2: PIP** 
1. Download and install Python. You **must** use the 64 bit version of Python 3.7 or later. The most recent download as of July 2019 is [here](https://www.python.org/ftp/python/3.7.4/python-3.7.4-amd64.exe). You also **must** choose the "Add to System PATH" option during installation.
2. Open a command line and run: `pip install bcml`
3. Run BCML using the command `bcml`
4. (Optional) Create a shortcut to the BCML executable in Python's `Scripts` folder.

**Option 3: Install from Source**
1. Download and install Python. You **must** use the 64 bit version of Python 3.7 or later. The most recent download as of July 2019 is [here](https://www.python.org/ftp/python/3.7.4/python-3.7.4-amd64.exe). You also **must** choose the "Add to System PATH" option during installation.
2. Download and extract the source code for the latest BCML release or clone the repo.
3. In the directory where you extracted the BCML source, run `python setup.py install`.
4. Run BCML using the command `bcml`
5. (Optional) Create a shortcut to the BCML executable in Python's `Scripts` folder.

On first use, you will have to specify the directory where Cemu is installed and the `content` directory of your BotW game dump. BCML also needs to know the location of Cemu's mlc folder for BotW, but by default it will detect this from your Cemu folder and BotW title ID. If this detection fails or you have another mlc folder you want to use, you will need to specify it manually.

## Updating BCML

**Option 1: For Windows Installer Users**

Download the new installer, and install it to the same location as your previous install.

**Option 2: For PIP Installs**

Run `pip install -U bcml`

**Option 3: For Source Installs**

1. Download the new source
2. In the main folder, run `python setup.py install`

## How to Use

![BCML Preview](https://i.imgur.com/x3ILZvN.png)

### General Notes

- Mods can be installed from BNP, ZIP, RAR, or 7Z files, or from an unzipped graphic pack folder.
- Only mods with a Cemu `rules.txt` file are supported. If you want to convert an older mod, you might find help from [this guide](https://gamebanana.com/tuts/12493).
- While BCML tries to resolve as many conflicts as possible between mods, some mods simply will not work together. They may need to be merged manually or may be irreconcilable. For more information about resolving mod conflicts, see [the article on ZeldaMods.org](https://zeldamods.org/wiki/Help:Resolving_mod_conflicts).
- **Important note:** While it is possible to use BCML for some mods and install some in other ways, no compatibility is guaranteed. Using BCML together with other install methods is *not* supported.

### Installing Mods

1. Click "Install" on the main BCML window.
2. Queue mods to install by using "Add Mod File" or "Add Mod from Folder." You may also remove, rearrange, or clear the install queue. Mods will be installed in the order in which they are listed.
3. (Optional) Select any advanced options you may need. Note that these will be applied to all mods in the install queue, so if you need different options for different mods you will need to install them separately.
4. Click "Ok" to install the selected mods.

#### Notes on Advanced Options

Advanced options should not be necessary for most mods. However, there are a few possible uses.

*Insert at Priority*

By default, BCML will install any new mods after those that have already been installed, giving them the highest priority. By changing this option however, you can specify the priority at which the mods currently selected to be installed will be inserted at. This can be useful if you have changes made by a mod already installed that you want to take priority, or if you know that a mod you're installing needs to have a lower priority than one you have already installed in order for them to be compatible.

*RSTB Options*
- "Shrink RSTB values where possible" - By default, BCML will not adjust RSTB entries if the new size would be smaller. You can use this option to instead shrink them if you have good reason to believe it will improve the stability of your installation.
- "Estimate complex RSTB values" - Though proper RSTB calculations for AAMP and BFRES files is not possible, BCML can optionally apply statistically-generated estimates for most of them. This can potentially add more stability that deleting such entries, but if the estimates are ever too low it can cause crashes.
- "Don't remove complex RSTB entries" - By default, BCML will delete RSTB entries for complex file types like AAMP and BFRES, since the proper value cannot be calculated. You can use this option to disable this behavior, but know that it can cause instability. If RSTB estimation is enabled for these files, this option will only affect values which the estimation function cannot calculate.

*Merge Options*

By default, BCML will attempt to merge changes between mods for modified pack files, game texts, actor info, game data, and data, and main field maps. All of these can be disabled if you know you don't need them for a particular mod or group of mods.

*Deep Merge*

Deep merge attempts to merge changes made to individual AAMP files. This can be a powerful tool to resolve conflicts but might in *some* cases cause unexpected bugs.

### Managing Mods

Once you have installed one or more mods, you will be able to manage them in the main BCML window.

**Viewing Mod Info**

If you select a mod, the "Mod Info" panel will show its name, a brief description, its load priority, the path where it is installed, an optionally a link to its homepage and a preview image.

**Managing Load Order**

When conflicts between mods cannot be fully resolved, one of them must take priority over the other. By default, BCML gives each new mod installed priority over the previous mods. You can, however, customize this load order.

The load order can be changed simply by dragging and dropping mods in the mod list. By default, mods are sorted from *highest* to *lowest* priority, i.e. mods on the top of the list override mods beneath them. However, since some people prefer the reverse convention (used, for example, by Nexus Mod Manager), you can toggle the mod display order in BCML by clicking the arrow above the mod list.

If you change the load order, you will need to click the "Apply Sort" button for BCML to process and merge any relevant changes.

*Load Order Tips*
* In general, complex mods should take priority over simple ones. For example, as I am writing this, Crafting Project is probably the most complex mod in use. It should therefore take very high priority.
* In general, if one mod changes the appearance of an actor and the other changes its behavior or other parameters, the skin should take priority.
* Any time a mod doesn't appear to work, you can try changing its place in your load order to fix it.

**Uninstalling Mods**

You can uninstall mods by selecting one or more and clicking "Uninstall" in the "Mod Info" panel. 

**Other Functions**

To view the contents of an installed mod, you can select it and click "Explore," which will open the folder in your default file browser.

If you make any manual changes to your installed mods, or if you run into other issues and need to clean up, click "Remerge," and BCML will process all of your mods from scratch.

## Notes to Mod Makers

One of the original goals of BCML was to maintain complete backwards compatibility with normal graphic pack mods. Anything that can be installed by the plain Cemu graphic pack menu could be installed via BCML and vice versa. However, as BCML has increased in capability, I found it necessary to expand to support a new, second format for mods. You can continue to use BCML with normal graphic packs, but you can also create and install BCML Nano Patch mods, which have additional benefits.

Two of BCML's extended mod distribution features can be used with normal graphic packs as well Nano Patch mods. These can be added to any graphic pack mod without causing problems for non-BCML users.

### Bonus Features for Graphic Pack Mods

#### Extended `rules.txt`

BCML supports two extensions to mod metadata in `rules.txt`. You can add two optional fields, `url` and `image`. The `url` field can provide a link to your mod's homepage, GitHub, or GameBanana listing, and `image` can provide a preview image of the mod either as a relative path to an image included in the mod (ideally, just the filename of an image in the same directory as `rules.txt`) or as a URL to an image online. Example:

```ini
[Definition]
titleids = 00050000101C9300,00050000101C9400,00050000101C9500
name = Eventide Extreme
path = The Legend of Zelda: Breath of the Wild/Mods/Eventide Extreme
description = Boosts the difficulty level of Eventide Island by adding enemies and making a few other cool changes.
version = 3
fspriority = 100
image = https://files.gamebanana.com/img/ss/maps/530-90_5b5a11842b944.jpg
url = https://gamebanana.com/maps/200936
```

#### Quick Install

When BCML installs a mod, it analyzes all of its contents to log changes which can be merged. This process can sometimes be time-consuming, so BCML also has a Quick Install feature. This allows a mod creator to run the analysis process once, and then the user can install much more quickly.

To add Quick Install support to a mod:
1. Create your mod as a standard graphic pack
2. Install your mod using BCML
3. Copy the `logs` folder from your installed mod into the mod archive you publish, beside (not inside) the `content` folder.

By adding support for Quick Install, you can cut the time it takes to install your mod through BCML by about half, depending on its contents.

### BCML Nano Patch Mods

One of the key new features of BCML 2.0 is the BNP—BCML Nano Patch—mod format. This format allows for smaller, quicker, and more compatible mod distribution than standard graphic packs.

Instructions to create a BCML Nano Patch mod:
1. Create your mod the same way you would for a normal graphic pack mod (instructions [here](https://zeldamods.org/wiki/Help:Using_mods#Installing_mods_with_the_graphic_pack_menu) if you need help).
2. Click the "Create BCML Nano Patch Mod" icon at the bottom of the main BCML window.
3. Fill out your mod metadata, optionally including a preview image and a URL to a webpage for your mod. If your mod is on GameBanana, it is encouraged to use the GB link.
4. Select your mod's main folder, the one which contains `content`, `aoc`, and/or `rules.txt`.
5. (Optional) Select any advanced options you may need. See above in the mod installation instructions for more information about them.
6. Save your BNP mod where you wish.

#### Why Use Nano Patch?

BCML Nano Patch mods work by combining the power of deep merge, quick install, and partial packs, and as such they offer three primary advantages over traditional graphic pack mods.

1. **File size:** Nano Patches strip mods to only the changes they make to the original game files, and use LZMA compression, which together can massively reduce file sizes in most cases. For example, the current complete download of [Hyrule Rebalance v5](https://gamebanana.com/gamefiles/8525) totals almost 122MB. Converted to Nano Patch format, it weighs it at only ~2MB. [Crafting Project](https://gamebanana.com/craftings/103) went from 37MB to <1MB. Even the Linkle mod shrunk by over 80MB.
2. **Installation speed:** As mentioned in the above section on Quick Install, Nano Patch mods save the time of manual processing during installation, which can be a huge boost for more complex mods.
3. **Compatibility:** By trimming off mod content to only their changes, Nano Patch installation minimizes the potential for conflicts and accidental incompatibilites between mods. It also makes it easier to identify exactly where conflicts take place when they must be manually solved.

## Known Issues

* Deep merge may not work properly for mods that use loose files: files which have been moved out of the packs which contain them in the base game.

## License

This software is licensed under the terms of the GNU General Public License, version 3 or later.

This software includes the 7-Zip console application `7z.exe` and the library `7z.dll`, which are licensed under the GNU Lesser General Public License. The source code for this application is available for free at [https://www.7-zip.org/download.html](https://www.7-zip.org/download.html).

This software includes the console application `msyt.exe` by Kyle Clemens, copyrighted 2018 under the MIT License. The source code for this application is available for free at [https://gitlab.com/jkcclemens/msyt](https://gitlab.com/jkcclemens/msyt).
