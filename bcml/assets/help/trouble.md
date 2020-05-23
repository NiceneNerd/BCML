# Troubleshooting

There are a lot of things that can go wrong trying to merge and manage mods for BOTW.
Check here for some basic help for common problems.

## Mod Install Problems

### FileNotFoundError: File `x` not found in game dump

In most cases, this indicates that, despite BCML's attempts to check your folder settings
to begin with, somehow the game dump, update data, or DLC folder you provided to BCML are
incorrect. In rare cases it may relate to a mod that adds new files in a way or place that
BCML does not anticipate.

### FileNotFoundError: No rules.txt or info.json was found in MOD

This one is as it says. BCML didn't find a recongized meta file in the mod you picked.
BCML only supports graphic pack mods and BNPs. Other formats will need to be converted
first.

### ValueError: Invalid version: 1-wiiu (expected 1-3)

The mod you are trying to install contains a [BYML](https://zeldamods.org/wiki/BYML) file
(usually `ActorInfo.product.sbyml`) that has been corrupted by an outdated BYML tool. The
only solution to this is to contact the mod creator for help or to rework the file
manually.

### There was an error installing MOD. It processed successfully, but could not be added to your BCML mods

If the full text of the error includes anything about XML, you probably either (1) have an
old version of Cemu or (2) have a corrupt Cemu settings file. Make sure you have at least
Cemu 1.15, and if you still have issues, try deleting `settings.xml` from the Cemu folder.

## In-game Problems

**Any time you have any problem with one or more mods in-game after installing them
through BCML, the first thing you should try is using the Remerge button.**

### I've installed my mods in BCML, but they don't take effect in-game

Make sure that the BCML graphic pack is enabled in Cemu. BCML attempts to do this
automatically, but sometimes it can fail. If the graphic pack is enabled but you still see
no effects from any mods, it could be a bug involving hard links and file permissions. To
avoid this, check the "Disable hard links for master mod" option in BCML's setttings.

### Cemu crashes immediately after compiling shaders

This indicates a problem with a bootup file, generally either `Bootup.pack` itself, a file
within it, or one of the `Bootup_XXxx.pack` message packs containing game texts. (Or the
RSTB value for any of those files) First thing to try is to remerge. If that doesn't solve
it, it could be a problem with any mod that modifies game texts or `Bootup.pack`, so you
can try investigating those.

### I installed the Linkle mod, and it kind of works, but Linkle looks mixed with Link

This is usually a problem of mod priority. Try setting the Linkle mod to a higher priority
than other mods that affect `TitleBG.pack` or armors. If you have already done so, try
remerging. If it still doesn't work, it could be a more complicated problem with your mod
configuration; consider clearing your mods and starting fresh.
