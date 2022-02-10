# The BNP Format

BCML supports mods in its own format called BNP, "BOTW Nano Patch."

## Creating BNPs

To create a BNP in BCML, go to the Dev Tools tab. The main feature of that tab is the BNP creator.
There you can fill out metadata for your mod, such as name, version number, and description, and
define some useful settings such as dependencies and optional components.


### Folder Structure

You will also need to select the folder containing your mod files. Mods should have the following
folder layout:

**Wii U**

```
.
├── content
├── aoc (optional: for DLC files)
├── patches (optional: for Cemu code patches)
└── options (optional: for optional mod components)
    ├── option1 (any name allowed)
    │   ├── content
    │   └── aoc
    ├── option2
    │   └── content
    └── ...
```

**Switch**

```
.
├── 01007EF00011E000
│   └── romfs
├── 01007EF00011F001 (optional: for DLC files)
│   └── romfs
└── options (optional: for optional mod components)
    ├── option1 (any name allowed)
    │   ├── 01007EF00011E000
    │   │   └── romfs
    │   └── 01007EF00011F001
    │       └── romfs
    ├── option2
    │   └── 01007EF00011E000
    │       └── romfs
    └── ...
```

### Dependencies and Options

You can specify any number of other mods as dependencies for your BNP. If the user attempts to
install without the necessary mod(s), BCML will throw an error. By default, the dependency modal
will only offer to specify mods you currently have installed as dependencies. However, you can also
specify any other mod by manually providing it's BCML ID, which can be found inside the mod's
`info.json` meta file.

You can also specify optional components for your mod. To add mod options, first create an "options"
folder in the mod root. Then make subfolders for each option you want to add. In each subfolder, you
will need to replicate a normal mod structure, but containing only files different from the main
mod.

Options can be either single or multiple choice. You can add an unlimited number of multiple choice
options which the user can freely check or uncheck on install. You can also create option groups,
where you specify a few mutually exclusive options in a certain category (e.g. choose a hair color
for a player skin).

## Workings of a BNP

For developers, it might be helpful to understand exactly how a BNP works. A BNP mod starts with
normal game content folders, using the structure documented above. When creating a BNP, BCML scans
the mod content for edited files. Then, for any file supported by one of BCML's mergers, BCML will
analyze the file and compare it to the version from the vanilla game. Each merger will create a log
file (e.g. `rstb.json`) of changes detected and store it in a `logs` folder at the root of the BNP.
If the changes made to a file can be completely reproduced from the log alone, that file will be
deleted from the BNP. This includes files inside of SARC archives. Files which are not in the
vanilla game, or modified files for which there is no merger in BCML, will be left alone.

The end result is a 7z archive containing (1) one or more content folders with only edited files not
handled by BCML remaining and (2) a set of merger logs. Most of the logs are stored as YAML files,
though JSON is also used. This means a BNP can be opened and extracted with 7-Zip, and many
of the logs will be readable to anyone familiar with YAML-based BOTW modding tools.

When the BNP is installed, BCML will extract its contents into an internal mods directory and
process the logs inside to apply the changes to vanilla or existing merged files. Options which
have not been selected are removed from the installed mod.
