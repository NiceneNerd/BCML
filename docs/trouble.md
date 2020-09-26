# Troubleshooting

***Any time you have any problem with one or more mods in-game after installing them
through BCML, the first thing you should try is using the Remerge button.***

There are a lot of things that can go wrong trying to merge and manage mods for BOTW.
Check here for some basic help for common problems.

## Problems in BCML

### Setup

#### BCML is installed, how do I open it?

If you installed using the Windows installer, there should be a BCML shortcut in your
Start Menu. If you installed using pip, run `bcml` from the command line.

#### Why won't BCML accept my folders?

Here are the rules for the folders you need to set in BCML:

##### Cemu

(Optional) Must be the folder which directly contains `Cemu.exe` and `settings.xml`. For
some Cemu installations, this may be inside a folder named `BIN`.

##### Base Game

*(Required)* Must be the root folder for the BOTW ROM, excluding the executable or meta.
For Wii U/Cemu, this may be separate from Cemu's MLC storage, or, if it is, it will use
the title ID that ends in `0`. You must pass BCML the `content` folder directly, e.g.
`C:\Game Dumps\The Legend of Zelda Breath of the Wild [ALZE]\content`.

For Switch, this will be the `romfs` folder under the base game title ID, e.g.
`C:\Game Dumps\BOTW\01007EF00011E000\romfs`.

You can tell this folder is set correctly if it contains the file `Pack/Dungeon000.pack`.

##### Update

*(Required: Wii U)* Must be the root content folder for BOTW's update files, version 1.5.0
for Wii U or 1.6.0 for Switch. For Cemu users, this should ordinarily be inside Cemu's MLC
storage. For Cemu/Wii U, the first half of the title ID will end in the letter E. Example:
 `C:\Cemu\mlc01\usr\title\0005000E\101C9400\content`
Switch users should not need an update folder, because dumping will ordinarily merge the
base game and update files.

You can tell this folder is set correctly if it contains approximately 7000 files in the
folder `Actor/Pack`.

##### DLC

*(Optional)* Must be the folder containing the latest paid DLC files for BOTW. For Cemu
users, this should ordinarily be inside Cemu's MLC storage. For Cemu/Wii U, the first half
of the title ID will end in the letter C. Example (*make sure to include the `0010`*):
 `C:\Cemu\mlc01\usr\title\0005000E\101C9400\content\0010`
For Switch, this will be the `romfs` folder under the supported DLC title ID, e.g.
 `C:\Game Dumps\BOTW\01007EF00011F001\romfs`

 You can tell this folder is set correctly if it contains `Pack/AocMainField.pack`.

### Installing Mods

#### FileNotFoundError: File `X` not found in game dump

In most cases, this indicates that, despite BCML's attempts to check your folder settings
to begin with, somehow the game dump, update data, or DLC folder you provided to BCML are
incorrect. See the [previous section](#why-wont-bcml-accept-my-folders) for help with
folders. In rare cases it may relate to a mod that adds new files in a way or place that
BCML does not anticipate.

#### FileNotFoundError: No `rules.txt` or `info.json` was found in mod

This one is as it says. BCML didn't find a recongized meta file in the mod you picked.
BCML only supports graphic pack mods and BNPs (Switch: BNPs only). Other formats will need
to be converted first.

#### ValueError: Invalid version: 1-wiiu (expected 1-3)

The mod you are trying to install contains a [BYML](https://zeldamods.org/wiki/BYML) file
(usually `ActorInfo.product.sbyml` ) that has been corrupted by an outdated BYML tool. The
only solution to this is to *contact the mod creator for help* or to repair the file
manually.

#### There was an error installing MOD. It processed successfully, but could not be added to your BCML mods

If the full text of the error includes anything about XML, you probably either (1) have an
old version of Cemu or (2) have a corrupt Cemu settings file. Make sure you have at least
Cemu 1.15, and if you still have issues, try deleting `settings.xml` from the Cemu folder.

### Creating BNPs

#### No modified files were found. This means the mod is probably not in a supported format.

If you haven't already looked, check the [BNP help page](bnp.md) for help with the correct
folder structure for a BNP mod. If it still doesn't work, make sure to check the casing of
the folder names, as they are in fact case-sensitive (e.g. `content/Actor` works but
`Content/actor` does not).

### Usage Problems

#### BCML takes me back to the setup wizard each time.

Your settings, probably the game folders, are incorrect. They need to be fixed first.

#### The "Launch Game" button doesn't work.

Usually, this happens if Cemu is set to run as administrator but BCML is not. To correct
this, either turn off the administrator setting for Cemu (recommended, as it's actually
useless in *most* cases) or run BCML as administrator.

## Problems In Game

***Any time you have any problem with one or more mods in-game after installing them
through BCML, the first thing you should try is using the Remerge button.***

### I've installed my mods in BCML, but they don't take effect in-game

Make sure that the BCML graphic pack is enabled in Cemu. BCML attempts to do this
automatically, but sometimes it can fail. The graphic pack will appear in the Cemu menu
under `The Legend of Zelda: Breath of the Wild/Mods/BCML`. If the graphic pack is enabled
but you still see no effects from any mods, it could be a bug involving hard links and
file permissions. To avoid this, check the "Disable hard links for master mod" option in
BCML's setttings.

### Cemu crashes immediately after compiling shaders

There are a few possible causes:

1. You have mods installed outside of BCML that conflict with the BCML pack. **Running BCML
   alongside mods installed with other methods is not supported.**
2. Your load order is backwards.
3. Your game language in BCML does not match the region and language you use in BOTW.
4. Your game directory settings in BCML are set incorrectly.
5. There is something wrong with one of your mods itself.
6. Your game dump is corrupt.

### I installed the Linkle mod, and it kind of works, but Linkle looks mixed with Link

This is usually a problem of mod priority. Try setting the Linkle mod to a higher priority
than other mods that affect `TitleBG.pack` or armors. If you have already done so, try
remerging. If it still doesn't work, it could be a more complicated problem with your mod
configuration; consider clearing your mods and starting fresh.
