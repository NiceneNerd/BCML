import base64
import json
import shutil
from configparser import ConfigParser
from pathlib import Path
from typing import Any, Dict
from bcml import util, install

from bcml.util import RulesParser


def convert_old_mods(source: Path = None):
    mod_dir = util.get_modpack_dir()
    old_path = source or util.get_cemu_dir() / "graphicPacks" / "BCML"
    print("Copying old mods...")
    shutil.rmtree(mod_dir, ignore_errors=True)
    shutil.copytree(old_path, mod_dir)
    print("Converting old mods...")
    for i, mod in enumerate(
        sorted({d for d in mod_dir.glob("*") if d.is_dir() and d.name != "9999_BCML"})
    ):
        print(f"Converting {mod.name[4:]}")
        try:
            convert_old_mod(mod, True)
        except Exception as err:
            shutil.rmtree(mod)
            install.refresh_merges()
            raise RuntimeError(
                f"BCML was unable to convert {mod.name[4:]}. Error: {str(err)}. Your old "
                f"mods have not been modified. {i} mod(s) were successfully imported."
            ) from err
    shutil.rmtree(old_path, ignore_errors=True)


def convert_old_mod(mod: Path, delete_old: bool = False):
    rules_to_info(mod / "rules.txt", delete_old=delete_old)
    if (mod / "logs").exists():
        info = parse_rules(mod / "rules.txt")
        convert_old_logs(mod, info["name"])


def convert_old_settings():
    old_settings = ConfigParser()
    old_settings.read(str(util.get_data_dir() / "settings.ini"))
    cemu_dir = old_settings["Settings"]["cemu_dir"]
    mlc_dir = old_settings["Settings"]["mlc_dir"]
    game_dir = old_settings["Settings"]["game_dir"]
    update_dir = util.guess_update_dir(Path(mlc_dir), Path(game_dir))
    dlc_dir = util.guess_aoc_dir(Path(mlc_dir), Path(game_dir))
    settings = {
        "cemu_dir": cemu_dir,
        "game_dir": game_dir,
        "game_dir_nx": "",
        "load_reverse": old_settings["Settings"]["load_reverse"] == "True",
        "update_dir": str(update_dir or ""),
        "dlc_dir": str(dlc_dir or ""),
        "dlc_dir_nx": "",
        "store_dir": str(util.get_data_dir()),
        "site_meta": old_settings["Settings"]["site_meta"],
        "no_guess": old_settings["Settings"]["guess_merge"] == "False",
        "lang": old_settings["Settings"]["lang"],
        "no_cemu": False,
        "wiiu": True,
    }
    setattr(util.get_settings, "settings", settings)
    (util.get_data_dir() / "settings.ini").unlink()
    util.save_settings()


def parse_rules(rules_path: Path) -> Dict[str, Any]:
    rules = RulesParser()
    rules.read(str(rules_path))
    info = {
        "name": str(rules["Definition"]["name"]).strip("\"' "),
        "desc": str(rules["Definition"].get("description", "")).strip("\"' "),
        "url": str(rules["Definition"].get("url", "")).strip("\"' "),
        "image": str(rules["Definition"].get("image", "")).strip("\"' "),
        "version": "1.0.0",
        "depends": [],
        "options": {},
        "platform": "wiiu",
        "priority": 100,
    }
    id_string = f"{info['name']}=={info['version']}"
    info["id"] = base64.urlsafe_b64encode(id_string.encode("utf8")).decode("utf8")
    try:
        info["priority"] = int(rules["Definition"]["fsPriority"])
    except KeyError:
        info["priority"] = int(getattr(rules["Definition"], "fspriority", 100))
    return info


def rules_to_info(rules_path: Path, delete_old: bool = False):
    print("Converting meta file...")
    info = parse_rules(rules_path)
    (rules_path.parent / "info.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2)
    )
    if delete_old:
        rules_path.unlink()


def convert_old_logs(mod_dir: Path, name: str):
    print("Upgrading old logs...")
    if (mod_dir / "logs" / "packs.log").exists():
        print("Upgrading pack log...")
        throw(name)
    if (mod_dir / "logs" / "rstb.log").exists():
        print("Upgrading RSTB log...")
        throw(name)
    if (mod_dir / "logs").glob("*texts*"):
        print("Upgrading text logs...")
        throw(name)
    for log in {l for l in mod_dir.glob("logs/*.yml") if not "texts" in l.stem}:
        if log.name == "deepmerge.yml":
            print("Upgrading deep merge log...")
            throw(name)
        elif log.name == "gamedata.yml":
            print("Upgrading game data log...")
            throw(name)
        elif log.name == "savedata.yml":
            print("Upgrading save data log...")
            throw(name)
        elif log.name == "map.yml":
            print("Upgrading map log...")
            throw(name)
        else:
            pass

def throw(name):
    raise RuntimeError(f"""Looks like {name} is an old mod that uses the BCML 2.x BNP format.\n
    Unfortunately, BCML no longer supports upgrading old BNPs. If there is a graphic pack \n
    version of the mod, please try downloading and installing that.""")
