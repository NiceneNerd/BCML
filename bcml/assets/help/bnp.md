# The BNP Format

BCML supports mods in its own format called BNP, "BOTW Nano Patch."

## Creating BNPs

To create a BNP in BCML, go to the Dev Tools tab. The main feature of that tab is the BNP creator.
There you can fill out metadata for your mod, such as name, version number, and description, and
define some useful settings such as dependencies and optional components.

You will also need to select the folder containing your mod files. Mods should have the following folder layout:

**Wii U**
```
.
├── content
├── aoc (optional: for DLC files)
└── options (optional: for optional mod components)
    ├── option1 (any name allowed)
    │   ├── content
    │   └── aoc
    ├── option2
    │   └── content
    └── ...
```

**Switch**
