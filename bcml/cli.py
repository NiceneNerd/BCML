import json
from pathlib import Path
from shutil import rmtree

from bcml import util, install, dev

def run_args():
    args = util.parse_arguments()
    if args.disable:
        # --disable
        for mod in util.get_installed_mods():
            name = mod.name.replace(" ", "").lower()
            arg = args.disable.replace(" ", "").lower()
            if name == arg:
                install.disable_mod(mod=mod)
                exit(0)

    elif args.disable_all:
        # --disable-all
        for mod in util.get_installed_mods():
            install.disable_mod(mod=mod, wait_merge=True)
        install.refresh_merges()
        install.refresh_master_export()
        exit()

    elif args.enable:
        # --enable
        for mod in util.get_installed_mods(disabled=True):
            name = mod.name.replace(" ", "").lower()
            arg = args.enable.replace(" ", "").lower()
            if name == arg:
                install.enable_mod(mod=mod)
                exit()

    elif args.enable_all:
        # --enable-all
        for mod in util.get_installed_mods(disabled=True):
            if mod.disabled:
                install.enable_mod(mod=mod, wait_merge=True)
        install.refresh_merges()
        install.refresh_master_export()
        exit()

    elif args.bnpify:
        # --bnpify
        info = args.bnpify / "info.json" if (args.bnpify / "info.json").exists() else args.bnpify / "rules.txt"
        if not info.exists():
            (args.bnpify / "info.json").write_text(
                json.dumps(
                    {
                        "name": "Temp",
                        "desc": "Temp pack",
                        "url": "",
                        "id": "VGVtcD0wLjA=",
                        "image": "",
                        "version": "1.0.0",
                        "depends": [],
                        "options": {},
                        "platform": "wiiu"
                        if get_settings("wiiu")
                        else "switch",
                    }
                )
            )
            info = args.bnpify / "info.json"

        if info.suffix == ".json":
            meta = json.loads(info.read_text("utf-8"))
            dev.create_bnp_mod(
                mod=args.bnpify,
                output=args.bnpify / f"{meta['name'].replace(' ', '')}.bnp",
                meta=meta,
            )

        else:
            # https://stackoverflow.com/questions/24264609/parsing-txt-file-into-dictionary-in-python
            meta = {}
            with info.open(encoding="utf-8") as rules:
                for line in rules:
                    if "=" in line:
                        key, val = map(str.strip, line.split("="))
                        meta[key] = val
            dev.create_bnp_mod(
                mod=args.bnpify,
                output=args.bnpify / f"{meta['name'].replace(' ', '')}.bnp",
                meta={
                    "name": meta["name"],
                    "version": meta["version"],
                    "desc": meta["description"],
                    "platform": "wiiu"
                    if get_settings("wiiu")
                    else "switch",
                },
            )
    elif args.export:
        # --export
        install.export(args.export)

    elif args.standalone:
        # --standalone
        bnp = args.standalone
        with TempModContext():
            install.install_mod(
                bnp,
                merge_now=True,
                options={"options": {"texts": {"all_langs": True}}, "disable": []},
            )
            
            out = f"{bnp.stem}.zip"
            if out:
                output = Path(out)
                install.export(output, standalone=True)
    
    elif args.update:
        # --update
        update_file = args.update;
        for i in get_installed_mods(disabled=True):
            name = i.name.replace(" ", "").lower()
            arg = update_file.name.rsplit(".")[0].replace(" ", "").lower()
            if name == arg:
                mod = i;

        if (mod.path / "options.json").exists():
            options = json.loads((mod.path / "options.json").read_text());
        else:
            options = {};

        shutil.rmtree(mod.path)
        with Pool(maxtasksperchild=500) as pool:
            new_mod = install.install_mod(
                Path(update_file),
                insert_priority=mod.priority,
                options=options,
                pool=pool,
                updated=True,
            );

        install.refresh_master_export()

    elif args.remerge:
        # --remerge
        install.refresh_merges()
        install.refresh_master_export()

    elif args.install:
        # --install
        install.install_mod(
            mod=args.install, 
            insert_priority=args.priority if args.priority else 0, 
            merge_now=True
        )
        install.refresh_master_export()

    elif args.uninstall:
        # --uninstall
        for mod in util.get_installed_mods(disabled=True):
            name = mod.name.replace(" ", "").lower()
            arg = args.uninstall.replace(" ", "").lower()
            if name == arg:
                install.uninstall_mod(mod=mod)
    
    elif args.uninstall_all:
        for mod in get_installed_mods(disabled=True):
            install.uninstall(mod=mod, wait_merge=True)
            install.refresh_merges()
            install.refresh_master_export()

    elif args.backup:
        # --backup
        install.create_backup(args.backup)

    elif args.restore:
        # --restore
        backup = list((util.get_storage_dir() / "backups").glob(f"{args.restore}*"))
        if len(backup) <= 0:
            raise ValueError(f"No backup named {args.restore} exists!")

        backup = backup[0]
        install.restore_backup(backup)

    else:
        return

    exit()
    
