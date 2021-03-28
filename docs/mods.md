# Managing Mods

Once you have installed one or more mods, you will be able to manage them in the main
BCML window.

## Viewing Mod Info

If you select a mod, the "Mod Info" panel will show its name, a brief description, its
load priority, the path where it is installed, the kinds of recognized changes it makes
to the game, and optionally a link to its homepage and a preview image.

From the mod info screen, there are a few useful buttons. You can enable, disable,
update, or uninstall the selected mod. You can also click "Explore" to view the mod's
files in your default file manager. If you installed a graphic pack mod, there will also
be a "Reprocess" button that will discard the BCML logs generated and refresh it in case
of any manual changes to the files.

## Managing Load Order

When conflicts between mods cannot be fully resolved, one of them must take priority
over the other. By default, BCML gives each new mod installed priority over the previous
mods. You can, however, customize this load order.

**By default, mods are sorted from highest to lowest priority.** (Priority starts at 100
and goes up.) This means mods on the top of the list (highest number) will override
conflicting changes made by mods beneath them. However, since some people prefer the
reverse convention (used, for example, by Nexus Mod Manager), you can toggle the mod
display order in BCML by clicking the sort toggle.

**To change your load order**, click the "Show sort handles" icon. This will enable
drag-and-drop on your mod list to chage the order. Once you have finished sorting, you
will need to click "Apply Pending Changes" for BCML to process and merge the new load
order.

_Load Order Tips_

-   In general, skins should be higher than edits to behaviour or stats, at least for
    the same actors. For example: the Linkle mod should be higher than a mod which edits
    armour stats, otherwise you might have texture bugs.
-   Optional components, addons, compatibility patches, or any mods that are based on
    other mods should always be given higher priority than the mods they're based on.
-   Large overhaul-type mods (e.g. Second Wind or Hyrule Rebalance) are complicated.
    When possible, they should take lower priority than other mods, kind of like an
    alternate base game. They may, however, sometimes need to take priority over some or
    most other mods if certain complex features (like some of those in Survival of the
    Wild) are not working properly.
-   Any time you experience crashing or odd glitches, it can be worth it to try
    rearranging your load order.

Sample good load order (highest to lowest):

```
SOTW & Linkle Compatibility Patch (106)
Linkle Cucco Glider
Linkle Mod
Survival of the Wild
Relics of the Past
Hyrule Rebalance
Second Wind (100)
```

Sample bad load order (highest to lowest):

```
Second Wind (106)
Hyrule Rebalance
Linkle Mod
Linkle Cucco Glider
Relics of the Past
Survival of the Wild
SOTW & Linkle Compatibility Patch (100)
```

## Other Functions

If you make any manual changes to your installed mods, or if you run into other issues
and need to clean up, click "Remerge," and BCML will process all of your mods from
scratch. **Always try remerging before anything else, and especially before reporting
bugs. Most crashes and bugs that appear immediately after installing big mods or several
mods can be solved by remerging.**

BCML also provides a backup and restore feature for your mod configuration. When you
make a backup, every mod you have and the exact state of their merge will be compressed
and saved. They can easily be restored at any time, and as long as you are on the same
version of BCML, the restored setup is guaranteed to be identical to the original.
Backups are stored as 7z archives in your BCML user data.
