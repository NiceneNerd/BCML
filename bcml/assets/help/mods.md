# Managing Mods

Once you have installed one or more mods, you will be able to manage them in the main BCML window.

## Viewing Mod Info

If you select a mod, the "Mod Info" panel will show its name, a brief description, its load
priority, the path where it is installed, the kinds of recognized changes it makes to the game, and
optionally a link to its homepage and a preview image. 

From the mod info screen, there are a few useful buttons. You can enable, disable, update, or
uninstall the selected mod. You can also click "Explore" to view the mod's files in your default
file manager.

## Managing Load Order

When conflicts between mods cannot be fully resolved, one of them must take priority over the other.
By default, BCML gives each new mod installed priority over the previous mods. You can, however,
customize this load order.

By default, mods are sorted from highest to lowest priority. This means mods on the top of the list
will override conflicting changes made by mods beneath them. However, since some people prefer the
reverse convention (used, for example, by Nexus Mod Manager), you can toggle the mod display order
in BCML by clicking the sort toggle.

To change your load order, click the "Show sort handles" icon. This will enable drag-and-drop on
your mod list to chage the order. Once you have finished sorting, you will need to click "Apply
Pending Changes" for BCML to process and merge the new load order.

*Load Order Tips*

* In general, complex mods should take priority over simple ones. For example, as I am writing this,
Crafting Project and Relics of the Past are probably the most complex mods in common use. They
should therefore take very high priority.
* In general, if one mod changes the appearance of an actor and the other changes its behavior or
other parameters, the skin should take priority. (Example: The Linkle mod should be given higher
priority than mods that edit armor stats.)
* Any time a mod doesn't appear to work, try changing its place in your load order to fix it.

## Other Functions

If you make any manual changes to your installed mods, or if you run into other issues and need to
clean up, click "Remerge," and BCML will process all of your mods from scratch. **Always try this
before anything else, and especially before reporting bugs. Most crashes and bugs that appear
immediately after installing big mods or several mods can be solved by remerging.**

BCML also provides a backup and restore feature for your mod configuration. When you make a backup,
every mod you have and the exact state of their merge will be compressed and saved. They can easily
be restored at any time, and as long as you are on the same version of BCML, the restored setup
is guaranteed to be identical to the original. Backups are stored as 7z archives in your BCML user
data (`%LOCALAPPDATA%\bcml\backups` on Windows or `~/.config/bcml/backups` on Linux).