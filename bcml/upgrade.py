import base64
import csv
import json
import shutil
from configparser import ConfigParser
from multiprocessing import Pool
from pathlib import Path

import oead
import yaml
from aamp import yaml_util as ayu
from aamp import ParameterIO, ParameterObject, ParameterList, Writer
from byml import yaml_util as byu
from bcml import util, install
from bcml.mergers.texts import read_msbt
from bcml.mergers.rstable import RstbMerger
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
        convert_old_logs(mod)


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


def parse_rules(rules_path: Path) -> {}:
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


def convert_old_logs(mod_dir: Path):
    print("Upgrading old logs...")
    if (mod_dir / "logs" / "packs.log").exists():
        print("Upgrading pack log...")
        _convert_pack_log(mod_dir)
    if (mod_dir / "logs" / "rstb.log").exists():
        print("Upgrading RSTB log...")
        _convert_rstb_log(mod_dir)
    if (mod_dir / "logs").glob("*texts*"):
        print("Upgrading text logs...")
        _convert_text_logs(mod_dir / "logs")
    for log in {l for l in mod_dir.glob("logs/*.yml") if not "texts" in l.stem}:
        if log.name == "deepmerge.yml":
            print("Upgrading deep merge log...")
            _convert_aamp_log(log)
        elif log.name == "gamedata.yml":
            print("Upgrading game data log...")
            _convert_gamedata_log(log)
        elif log.name == "savedata.yml":
            print("Upgrading save data log...")
            _convert_savedata_log(log)
        elif log.name == "map.yml":
            print("Upgrading map log...")
            _convert_map_log(log)
        else:
            pass


def _convert_rstb_log(mod: Path):
    (mod / "logs" / "rstb.log").unlink()
    with Pool() as pool:
        files = install.find_modded_files(mod, pool=pool)
        merger = RstbMerger()
        merger.set_pool(pool)
        merger.log_diff(mod, files)


def _convert_pack_log(mod: Path):
    packs = {}
    with (mod / "logs" / "packs.log").open("r") as rlog:
        csv_loop = csv.reader(rlog)
        for row in csv_loop:
            if "logs" in str(row[1]) or str(row[0]) == "name":
                continue
            packs[str(row[0])] = Path(str(row[1])).as_posix().replace("\\", "/")
    (mod / "logs" / "packs.log").unlink()
    (mod / "logs" / "packs.json").write_text(
        json.dumps(packs, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _convert_aamp_log(log: Path):
    loader = yaml.CLoader
    ayu.register_constructors(loader)
    doc = yaml.load(log.read_text("utf-8"), Loader=loader)
    pio = ParameterIO("log", 0)
    root = ParameterList()
    for file, plist in doc.items():
        if not plist.lists:
            continue
        root.set_list(file, plist.list("param_root"))
    file_table = ParameterObject()
    for i, file in enumerate(doc):
        if not doc[file].lists:
            continue
        file_table.set_param(f"File{i}", file)
    root.set_object("FileTable", file_table)
    pio.set_list("param_root", root)
    log.unlink()
    log.with_suffix(".aamp").write_bytes(Writer(pio).get_bytes())


def _convert_text_log(log: Path) -> dict:
    lang = log.stem[6:]
    data = yaml.safe_load(log.read_text("utf-8"))
    log.unlink()
    return {lang: {file: data[file]["entries"] for file in data}}


def _convert_text_logs(logs_path: Path):
    diffs = {}
    with Pool() as pool:
        for diff in pool.imap_unordered(_convert_text_log, logs_path.glob("texts_*.yml")):
            diffs.update(diff)
    fails = set()
    for text_pack in logs_path.glob("newtexts_*.sarc"):
        lang = text_pack.stem[9:]
        sarc = oead.Sarc(text_pack.read_bytes())
        for file in sarc.get_files():
            if lang not in diffs:
                diffs[lang] = {}
            try:
                diffs[lang].update({file.name: read_msbt(bytes(file.data))["entries"]})
            except RuntimeError:
                print(f"Warning: {file.name} could not be processed and will not be used")
                fails.add(file.name)
                continue
        util.vprint(f"{len(fails)} text files failed to process:\n{fails}")
        text_pack.unlink()
    (logs_path / "texts.json").write_text(
        json.dumps(diffs, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _convert_gamedata_log(log: Path):
    diff = oead.byml.from_text(log.read_text("utf-8"))
    log.write_text(
        oead.byml.to_text(
            oead.byml.Hash(
                {
                    data_type: {"add": data, "del": oead.byml.Array()}
                    for data_type, data in diff.items()
                }
            )
        ),
        encoding="utf-8",
    )


def _convert_savedata_log(log: Path):
    diff = oead.byml.from_text(log.read_text("utf-8"))
    log.write_text(
        oead.byml.to_text(oead.byml.Hash({"add": diff, "del": oead.byml.Array()})),
        encoding="utf-8",
    )


def _convert_map_log(log: Path):
    loader = yaml.CLoader
    byu.add_constructors(loader)
    diff = yaml.load(log.read_text("utf-8"), Loader=loader)
    new_diff = {}
    for unit, changes in diff.items():
        new_changes = {
            "add": changes["add"],
            "del": changes["del"],
            "mod": {str(hashid): actor for hashid, actor in changes["mod"].items()},
        }
        new_diff[unit] = new_changes
    dumper = yaml.CDumper
    byu.add_representers(dumper)
    log.write_text(
        yaml.dump(new_diff, Dumper=dumper, allow_unicode=True), encoding="utf-8"
    )
