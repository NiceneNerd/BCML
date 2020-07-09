# Exporting Mods for Console

For Cemu users, BCML will automatically handle loading your installed mods into the game
via Cemu's graphic pack file replacement system. For Wii U or Switch users, you will need
to use the Export option to combine all of your mods into a single installable pack. The
basic process looks like this:

1. Install all of the mods you would like to use.
2. Click Remerge to make sure they are all properly and freshly merged.
3. Click Export to save a combined mod pack. Name it what you wish.
4. BCML will export a ZIP or 7Z file containing a merged build of all your mods.
    - For Wii U users, it will include a `content` and/or `aoc` folder, and it can be
      placed into an SDCafiine mod folder or sorted for FTP install.
    - For Switch users, the ZIP will contain a folder for each title ID used with a
      `romfs` folder in each. You can copy these into `atmosphere/contents` on your SD
      card.
