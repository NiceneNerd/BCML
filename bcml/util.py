# pylint: disable=missing-docstring
# Copyright 2020 Nicene Nerd <macadamiadaze@gmail.com>
# Licensed under GPLv3+
import csv
from dataclasses import dataclass
from functools import lru_cache
import json
import os
import re
import shutil
import subprocess
import sys
import traceback
import unicodedata
import urllib.error
import urllib.request
from collections import namedtuple, OrderedDict
from collections.abc import Mapping
from configparser import ConfigParser
from pathlib import Path
from platform import system
from typing import Union, List, Dict, ByteString

import oead
import xxhash
from webview import Window


CREATE_NO_WINDOW = 0x08000000
SARC_EXTS = {
    ".sarc",
    ".pack",
    ".bactorpack",
    ".bmodelsh",
    ".beventpack",
    ".stera",
    ".stats",
    ".ssarc",
    ".sbactorpack",
    ".sbmodelsh",
    ".sbeventpack",
    ".sstera",
    ".sstats",
    ".sblarc",
    ".blarc",
}
AAMP_EXTS = {
    ".bxml",
    ".sbxml",
    ".bas",
    ".sbas",
    ".baglblm",
    ".sbaglblm",
    ".baglccr",
    ".sbaglccr",
    ".baglclwd",
    ".sbaglclwd",
    ".baglcube",
    ".sbaglcube",
    ".bagldof",
    ".sbagldof",
    ".baglenv",
    ".sbaglenv",
    ".baglenvset",
    ".sbaglenvset",
    ".baglfila",
    ".sbaglfila",
    ".bagllmap",
    ".sbagllmap",
    ".bagllref",
    ".sbagllref",
    ".baglmf",
    ".sbaglmf",
    ".baglshpp",
    ".sbaglshpp",
    ".baiprog",
    ".sbaiprog",
    ".baslist",
    ".sbaslist",
    ".bassetting",
    ".sbassetting",
    ".batcl",
    ".sbatcl",
    ".batcllist",
    ".sbatcllist",
    ".bawareness",
    ".sbawareness",
    ".bawntable",
    ".sbawntable",
    ".bbonectrl",
    ".sbbonectrl",
    ".bchemical",
    ".sbchemical",
    ".bchmres",
    ".sbchmres",
    ".bdemo",
    ".sbdemo",
    ".bdgnenv",
    ".sbdgnenv",
    ".bdmgparam",
    ".sbdmgparam",
    ".bdrop",
    ".sbdrop",
    ".bgapkginfo",
    ".sbgapkginfo",
    ".bgapkglist",
    ".sbgapkglist",
    ".bgenv",
    ".sbgenv",
    ".bglght",
    ".sbglght",
    ".bgmsconf",
    ".sbgmsconf",
    ".bgparamlist",
    ".sbgparamlist",
    ".bgsdw",
    ".sbgsdw",
    ".bksky",
    ".sbksky",
    ".blifecondition",
    ".sblifecondition",
    ".blod",
    ".sblod",
    ".bmodellist",
    ".sbmodellist",
    ".bmscdef",
    ".sbmscdef",
    ".bmscinfo",
    ".sbmscinfo",
    ".bnetfp",
    ".sbnetfp",
    ".bphyscharcon",
    ".sbphyscharcon",
    ".bphyscontact",
    ".sbphyscontact",
    ".bphysics",
    ".sbphysics",
    ".bphyslayer",
    ".sbphyslayer",
    ".bphysmaterial",
    ".sbphysmaterial",
    ".bphyssb",
    ".sbphyssb",
    ".bphyssubmat",
    ".sbphyssubmat",
    ".bptclconf",
    ".sbptclconf",
    ".brecipe",
    ".sbrecipe",
    ".brgbw",
    ".sbrgbw",
    ".brgcon",
    ".sbrgcon",
    ".brgconfig",
    ".sbrgconfig",
    ".brgconfiglist",
    ".sbrgconfiglist",
    ".bsfbt",
    ".sbsfbt",
    ".bsft",
    ".sbsft",
    ".bshop",
    ".sbshop",
    ".bumii",
    ".sbumii",
    ".bvege",
    ".sbvege",
    ".bactcapt",
    ".sbactcapt",
}
BYML_EXTS = {
    ".bgdata",
    ".sbgdata",
    ".bquestpack",
    ".sbquestpack",
    ".byml",
    ".sbyml",
    ".mubin",
    ".smubin",
    ".baischedule",
    ".sbaischedule",
    ".baniminfo",
    ".sbaniminfo",
    ".bgsvdata",
    ".sbgsvdata",
}
TITLE_ACTORS = {
    "AncientArrow",
    "Animal_Insect_A",
    "Animal_Insect_B",
    "Animal_Insect_F",
    "Animal_Insect_H",
    "Animal_Insect_M",
    "Animal_Insect_S",
    "Animal_Insect_X",
    "Armor_Default_Extra_00",
    "Armor_Default_Extra_01",
    "BombArrow_A",
    "BrightArrow",
    "BrightArrowTP",
    "CarryBox",
    "DemoXLinkActor",
    "Dm_Npc_Gerudo_HeroSoul_Kago",
    "Dm_Npc_Goron_HeroSoul_Kago",
    "Dm_Npc_RevivalFairy",
    "Dm_Npc_Rito_HeroSoul_Kago",
    "Dm_Npc_Zora_HeroSoul_Kago",
    "ElectricArrow",
    "ElectricWaterBall",
    "EventCameraRumble",
    "EventControllerRumble",
    "EventMessageTransmitter1",
    "EventSystemActor",
    "Explode",
    "Fader",
    "FireArrow",
    "FireRodLv1Fire",
    "FireRodLv2Fire",
    "FireRodLv2FireChild",
    "GameROMPlayer",
    "IceArrow",
    "IceRodLv1Ice",
    "IceRodLv2Ice",
    "Item_Conductor",
    "Item_Magnetglove",
    "Item_Material_01",
    "Item_Material_03",
    "Item_Material_07",
    "Item_Ore_F",
    "NormalArrow",
    "Obj_IceMakerBlock",
    "Obj_SupportApp_Wind",
    "PlayerShockWave",
    "PlayerStole2",
    "RemoteBomb",
    "RemoteBomb2",
    "RemoteBombCube",
    "RemoteBombCube2",
    "SceneSoundCtrlTag",
    "SoundTriggerTag",
    "TerrainCalcCenterTag",
    "ThunderRodLv1Thunder",
    "ThunderRodLv2Thunder",
    "ThunderRodLv2ThunderChild",
    "WakeBoardRope",
}


class BcmlMod:
    priority: int
    path: Path

    def __init__(self, mod_path):
        self.path = mod_path
        self._info = json.loads(
            (self.path / "info.json").read_text("utf-8"), encoding="utf-8"
        )
        self.priority = self._info["priority"]

    def __repr__(self):
        return f"""BcmlMod(name="{
            self.name
        }", path="{
            self.path.as_posix()
        }", priority={self.priority})"""

    def __hash__(self):
        return hash(str(self))

    def __eq__(self, other):
        return hash(self) == hash(other)

    def to_json(self) -> dict:
        return {
            "name": self.name,
            "priority": self.priority,
            "path": str(self.path),
            "disabled": (self.path / ".disabled").exists(),
            "id": self.id,
        }

    @staticmethod
    def from_json(json: dict):
        return BcmlMod(Path(json["path"]))

    @staticmethod
    def from_info(info_path: Path):
        return BcmlMod(info_path.parent)

    @property
    def name(self) -> str:
        return self._info["name"]

    @property
    def id(self) -> str:
        return self._info["id"]

    @property
    def description(self) -> str:
        return self._info["desc"]

    @property
    def platform(self) -> str:
        return self._info["platform"]

    @property
    def image(self) -> str:
        return self._info["image"]

    @property
    def url(self) -> str:
        return self._info["url"]

    @property
    def dependencies(self) -> List[str]:
        return self._info["depedencies"]

    @property
    def info_path(self):
        return self.path / "info.json"

    @property
    def disabled(self):
        return (self.path / ".disabled").exists()

    def _get_folder_id(self):
        return f"{self.priority}_" + re.sub(
            r"(?u)[^-\w.]", "", self.name.strip().replace(" ", "")
        )

    def _save_changes(self):
        self.info_path.write_text(
            json.dumps(self._info, ensure_ascii=False), encoding="utf-8"
        )

    @property
    def mergers(self) -> list:
        from bcml.mergers import get_mergers_for_mod

        return get_mergers_for_mod(self)

    def get_partials(self) -> dict:
        partials = {}
        for m in self.mergers:
            if m.can_partial_remerge():
                partials[m.NAME] = m.get_mod_affected(self)
        return partials

    def change_priority(self, priority):
        self.priority = priority
        self._info["priority"] = priority
        self._save_changes()
        self.path.rename(self.path.parent.resolve() / self._get_folder_id())

    def get_preview(self) -> Path:
        try:
            return self._preview
        except AttributeError:
            if not list(self.path.glob("thumbnail.*")):
                if self.image:
                    if self.url and "gamebanana.com" in self.url:
                        response = urllib.request.urlopen(self.url)
                        rdata = response.read().decode()
                        img_match = re.search(
                            r"<meta property=\"og:image\" ?content=\"(.+?)\" />", rdata
                        )
                        if img_match:
                            image_path = "thumbnail.jfif"
                            urllib.request.urlretrieve(
                                img_match.group(1), str(self.path / image_path)
                            )
                        else:
                            raise IndexError(
                                f"Rule for {self.url} failed to find the remote preview"
                            )
                    else:
                        raise KeyError(f"No preview image available")
                else:
                    image_path = self.image
                    if image_path.startswith("http"):
                        urllib.request.urlretrieve(
                            image_path,
                            str(self.path / ("thumbnail." + image_path.split(".")[-1])),
                        )
                        image_path = "thumbnail." + image_path.split(".")[-1]
                    if not os.path.isfile(str(self.path / image_path)):
                        raise FileNotFoundError(
                            f"Preview {image_path} specified in rules.txt not found"
                        )
            else:
                for thumb in self.path.glob("thumbnail.*"):
                    image_path = thumb
            self._preview = self.path / image_path
            return self._preview

        def uninstall(self, wait_merge: bool = False):
            from bcml.install import uninstall_mod

            uninstall_mod(self, wait_merge)

        def get_modded_info() -> {}:
            pass


decompress = oead.yaz0.decompress
compress = oead.yaz0.compress


def vprint(content):
    from bcml import DEBUG

    if not DEBUG:
        return
    if not isinstance(content, str):
        if isinstance(content, oead.byml.Hash) or isinstance(content, oead.byml.Array):
            print(oead.byml.to_text(content))
        elif isinstance(content, oead.aamp.ParameterIO):
            print(content.to_text())
        else:
            from pprint import pformat

            content = pformat(content, compact=True, indent=4)
    print(f"VERBOSE{content}")


def timed(func):
    def timed_function(*args, **kwargs):
        from time import time_ns

        start = time_ns()
        res = func(*args, **kwargs)
        vprint(f"{func.__qualname__} took {(time_ns() - start) / 1000000000} seconds")
        return res

    return timed_function


@lru_cache(None)
def get_exec_dir() -> Path:
    return Path(os.path.dirname(os.path.realpath(__file__)))


@lru_cache(None)
def get_data_dir() -> Path:
    import platform

    if platform.system() == "Windows":
        data_dir = Path(os.path.expandvars("%LOCALAPPDATA%")) / "bcml"
    else:
        data_dir = Path.home() / ".config" / "bcml"
    if not data_dir.exists():
        data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


@lru_cache(None)
def get_work_dir() -> Path:
    work_dir = get_data_dir() / "work_dir"
    if not work_dir.exists():
        work_dir.mkdir(parents=True, exist_ok=True)
    return work_dir


def clear_temp_dir():
    """Empties BCML's temp directories"""
    for path in get_work_dir().glob("tmp*"):
        try:
            if path.is_dir():
                shutil.rmtree(str(path))
            elif path.is_file():
                path.unlink()
        except OSError:
            pass


def get_settings(name: str = "") -> {}:
    try:
        if not hasattr(get_settings, "settings"):
            settings = {}
            settings_path = get_data_dir() / "settings.json"
            if not settings_path.exists():
                settings = {
                    "cemu_dir": "",
                    "game_dir": "",
                    "game_dir_nx": "",
                    "update_dir": "",
                    "dlc_dir": "",
                    "dlc_dir_nx": "",
                    "load_reverse": False,
                    "site_meta": "",
                    "dark_theme": False,
                    "no_guess": False,
                    "lang": "",
                    "no_cemu": False,
                    "wiiu": True,
                }
                with settings_path.open("w", encoding="utf-8") as s_file:
                    json.dump(settings, s_file)
            else:
                settings: dict = json.loads(settings_path.read_text())
                if "game_dir_nx" not in settings:
                    settings.update({"game_dir_nx": "", "dlc_dir_nx": ""})
            get_settings.settings = settings
        if name:
            return get_settings.settings.get(name, False)
        return get_settings.settings
    except Exception as e:
        e.message = f"""Oops, BCML could not load its settings file. The error: {
            getattr(e, 'message', '')
        }"""
        raise e


def save_settings():
    with (get_data_dir() / "settings.json").open("w", encoding="utf-8") as s_file:
        json.dump(get_settings.settings, s_file)


def get_cemu_dir() -> Path:
    cemu_dir = str(get_settings("cemu_dir"))
    if not cemu_dir or not Path(cemu_dir).is_dir():
        err = FileNotFoundError("The Cemu directory has moved or not been saved yet.")
        err.error_text = "The Cemu directory has moved or not been saved yet."
        raise err
    return Path(cemu_dir)


def set_cemu_dir(path: Path):
    settings = get_settings()
    settings["cemu_dir"] = str(path.resolve())
    save_settings()


def get_game_dir() -> Path:
    game_dir = str(
        get_settings("game_dir")
        if get_settings("wiiu")
        else get_settings("game_dir_nx")
    )
    if not game_dir or not Path(game_dir).is_dir():
        err = FileNotFoundError(
            "The BotW game directory has has moved or not been saved yet."
        )
        err.error_text = "The BotW game directory has has moved or not been saved yet."
        raise err
    else:
        return Path(game_dir)


def set_game_dir(path: Path):
    settings = get_settings()
    settings["game_dir"] = str(path.resolve())
    save_settings()
    try:
        get_mlc_dir()
    except FileNotFoundError:
        try:
            from xml.dom import minidom

            set_path = get_cemu_dir() / "settings.xml"
            if not set_path.exists():
                err = FileNotFoundError("The Cemu settings file could not be found.")
                err.error_text = (
                    "The Cemu settings file could not be found. This usually means your Cemu directory "
                    "is set incorrectly."
                )
                raise err
            set_read = ""
            with set_path.open("r") as setfile:
                for line in setfile:
                    set_read += line.strip()
            settings = minidom.parseString(set_read)
            mlc_path = Path(
                settings.getElementsByTagName("mlc_path")[0].firstChild.nodeValue
            )
        except (FileNotFoundError, IndexError, ValueError, AttributeError):
            mlc_path = get_cemu_dir() / "mlc01"
        if mlc_path.exists():
            set_mlc_dir(mlc_path)
        else:
            raise FileNotFoundError(
                "The MLC directory could not be automatically located."
            )


def get_mlc_dir() -> Path:
    mlc_dir = str(get_settings("mlc_dir"))
    if not mlc_dir or not Path(mlc_dir).is_dir():
        err = FileNotFoundError(
            "The Cemu MLC directory has moved or not been saved yet."
        )
        err.error_text = "The Cemu MLC directory has moved or not been saved yet."
        raise err
    return Path(mlc_dir)


def set_mlc_dir(path: Path):
    settings = get_settings()
    settings["mlc_dir"] = str(path.resolve())
    save_settings()
    if hasattr(get_update_dir, "update_dir"):
        del get_update_dir.update_dir
    if hasattr(get_aoc_dir, "aoc_dir"):
        del get_aoc_dir.aoc_dir


def set_site_meta(site_meta):
    settings = get_settings()
    if not "site_meta" in settings:
        settings["site_meta"] = ""
    else:
        settings["site_meta"] = str(settings["site_meta"] + f"{site_meta};")
    save_settings()


@lru_cache(None)
def get_title_id(game_dir: Path = None) -> (str, str):
    if not hasattr(get_title_id, "title_id"):
        title_id = "00050000101C9400"
        if not game_dir:
            game_dir = get_game_dir()
        with (game_dir.parent / "code" / "app.xml").open("r") as a_file:
            for line in a_file:
                title_match = re.search(
                    r"<title_id type=\"hexBinary\" length=\"8\">([0-9A-F]{16})</title_id>",
                    line,
                )
                if title_match:
                    title_id = title_match.group(1)
                    break
        get_title_id.title_id = (title_id[0:7] + "0", title_id[8:])
    return get_title_id.title_id


def guess_update_dir(cemu_dir: Path = None, game_dir: Path = None) -> Path:
    if not cemu_dir:
        cemu_dir = get_cemu_dir()
    mlc_dir = cemu_dir / "mlc01" / "usr" / "title"
    title_id = get_title_id(game_dir)
    # First try the 1.15.11c mlc layout
    if (mlc_dir / f"{title_id[0][0:7]}E" / title_id[1] / "content").exists():
        return mlc_dir / f"{title_id[0][0:7]}E" / title_id[1] / "content"
    # Then try the legacy layout
    elif (mlc_dir / title_id[0] / title_id[1] / "content").exists():
        return mlc_dir / title_id[0] / title_id[1] / "content"
    return None


@lru_cache(None)
def get_update_dir() -> Path:
    try:
        update_str = get_settings("update_dir")
        if not update_str:
            raise FileNotFoundError()
        update_dir = Path(update_str)
        if not update_dir.exists():
            raise FileNotFoundError()
    except:
        e = FileNotFoundError(
            "The BOTW update directory has moved or has not been saved yet."
        )
        e.error_text = "The BOTW update directory has moved or has not been saved yet."
        raise e
    return update_dir


def guess_aoc_dir(cemu_dir: Path = None, game_dir: Path = None) -> Path:
    if not cemu_dir:
        cemu_dir = get_cemu_dir()
    mlc_dir = cemu_dir / "mlc01" / "usr" / "title"
    title_id = get_title_id(game_dir)
    # First try the 1.15.11c mlc layout
    if (mlc_dir / f"{title_id[0][0:7]}C" / title_id[1] / "content" / "0010").exists():
        return mlc_dir / f"{title_id[0][0:7]}C" / title_id[1] / "content" / "0010"
    # Then try the legacy layout
    elif (mlc_dir / title_id[0] / title_id[1] / "aoc" / "content" / "0010").exists():
        return mlc_dir / title_id[0] / title_id[1] / "aoc" / "content" / "0010"
    return None


def get_aoc_dir() -> Path:
    try:
        dlc_str = (
            get_settings("dlc_dir")
            if get_settings("wiiu")
            else get_settings("dlc_dir_nx")
        )
        if not dlc_str:
            raise FileNotFoundError()
        aoc_dir = Path(dlc_str)
        if not aoc_dir.exists():
            raise FileNotFoundError()
    except:
        e = FileNotFoundError(
            "The BOTW DLC directory has moved or has not been saved yet."
        )
        e.error_text = "The BOTW DLC directory has moved or has not been saved yet."
        raise e
    return aoc_dir


def get_content_path() -> str:
    return (
        "content"
        if get_settings("wiiu")
        else "atmosphere/contents/01007EF00011E000/romfs"
    )


def get_dlc_path() -> str:
    return (
        "aoc" if get_settings("wiiu") else "atmosphere/contents/01007EF00011F001/romfs"
    )


def get_modpack_dir() -> Path:
    return get_data_dir() / ("mods" if get_settings("wiiu") else "mods_nx")


@lru_cache(1024)
def get_game_file(path: Union[Path, str], aoc: bool = False) -> Path:
    if str(path).replace("\\", "/").startswith(f"{get_content_path()}/"):
        path = Path(str(path).replace("\\", "/").replace(f"{get_content_path()}/", ""))
    if isinstance(path, str):
        path = Path(path)
    game_dir = get_game_dir()
    if get_settings("wiiu"):
        update_dir = get_update_dir()
    try:
        aoc_dir = get_aoc_dir()
    except FileNotFoundError:
        aoc_dir = None
    if "aoc" in path.parts or get_dlc_path() in str(path.as_posix()) or aoc:
        if aoc_dir:
            path = Path(
                path.as_posix()
                .replace("aoc/content/0010/", "")
                .replace("aoc/0010/content/", "")
                .replace("aoc/content/", "")
                .replace("aoc/0010/", "")
                .replace(get_dlc_path(), "")
            )
            if (aoc_dir / path).exists():
                return aoc_dir / path
            raise FileNotFoundError(f"{path} not found in DLC files.")
        else:
            raise FileNotFoundError(
                f"{path} is a DLC file, but the DLC directory is missing."
            )
    if get_settings("wiiu"):
        if (update_dir / path).exists():
            return update_dir / path
    if (game_dir / path).exists():
        return game_dir / path
    elif aoc_dir and (aoc_dir / path).exists():
        return aoc_dir / path
    else:
        raise FileNotFoundError(f"File {str(path)} was not found in game dump.")


def get_nested_file_bytes(file: str, unyaz: bool = True) -> bytes:
    nests = file.split("//")
    sarcs = []
    sarcs.append(oead.Sarc(unyaz_if_needed(Path(nests[0]).read_bytes())))
    i = 1
    while i < len(nests) - 1:
        sarc_bytes = unyaz_if_needed(sarcs[i - 1].get_file(nests[i]).data)
        sarcs.append(oead.Sarc(sarc_bytes))
        i += 1
    file_bytes = sarcs[-1].get_file(nests[-1]).data
    if file_bytes[0:4] == b"Yaz0" and unyaz:
        file_bytes = decompress(file_bytes)
    else:
        file_bytes = bytes(file_bytes)
    del sarcs
    return file_bytes


@lru_cache(None)
def get_master_modpack_dir() -> Path:
    master = get_modpack_dir() / "9999_BCML"
    if not (master / "rules.txt").exists():
        create_bcml_graphicpack_if_needed()
    return master


@lru_cache(2)
def get_hash_table(wiiu: bool = True) -> {}:
    return json.loads(
        decompress(
            (
                get_exec_dir()
                / "data"
                / "hashes"
                / f'{"wiiu" if wiiu else "switch"}.sjson'
            ).read_bytes()
        ).decode("utf-8")
    )


@lru_cache(None)
def get_canon_name(file: str, allow_no_source: bool = False) -> str:
    if isinstance(file, str):
        file = Path(file)
    name = (
        file.as_posix()
        .replace("\\", "/")
        .replace("/titles/", "/contents/")
        .replace("atmosphere/contents/01007EF00011E000/romfs", "content")
        .replace("atmosphere/contents/01007EF00011E001/romfs", "aoc/0010")
        .replace("atmosphere/contents/01007EF00011E002/romfs", "aoc/0010")
        .replace("atmosphere/contents/01007EF00011F001/romfs", "aoc/0010")
        .replace("atmosphere/contents/01007EF00011F002/romfs", "aoc/0010")
        .replace(".s", ".")
        .replace("Content", "content")
        .replace("Aoc", "aoc")
    )
    if "aoc/" in name:
        return name.replace("aoc/content", "aoc").replace("aoc", "Aoc")
    elif "content/" in name and "/aoc" not in name:
        return name.replace("content/", "")
    elif allow_no_source:
        return name


@lru_cache(None)
def get_mod_id(mod_name: str, priority: int) -> str:
    return f"{priority:04}_" + re.sub(
        r"(?u)[^-\w.]", "", mod_name.strip().replace(" ", "")
    )


def get_mod_by_priority(priority: int) -> Union[Path, bool]:
    try:
        return list(get_modpack_dir().glob(f"{priority:04}*"))[0]
    except IndexError:
        return False


@lru_cache(None)
def get_file_language(file: Union[Path, str]) -> str:
    if isinstance(file, Path):
        file = str(file)
    lang_match = re.search(r"_([A-Z]{2}[a-z]{2})", file)
    return lang_match.group(1)


def is_file_modded(name: str, file: Union[bytes, Path], count_new: bool = True) -> bool:
    contents = (
        file
        if isinstance(file, bytes)
        else file.read_bytes()
        if isinstance(file, Path)
        else bytes(file)
    )
    table = get_hash_table(get_settings("wiiu"))
    if name not in table:
        return count_new
    fhash = xxhash.xxh64_intdigest(contents)
    return not fhash in table[name]


@lru_cache(None)
def is_file_sarc(path: str) -> bool:
    ext = os.path.splitext(str(path))[1]
    return ext in SARC_EXTS


def unyaz_if_needed(file_bytes: bytes) -> bytes:
    if file_bytes[0:4] == b"Yaz0":
        return bytes(decompress(file_bytes))
    else:
        return file_bytes if isinstance(file_bytes, bytes) else bytes(file_bytes)


def inject_file_into_sarc(file: str, data: bytes, sarc: str, create_sarc: bool = False):
    path = get_master_modpack_dir() / get_content_path() / sarc
    if path.exists() or create_sarc:
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(get_game_file(sarc), path)
        sarc_data = path.read_bytes()
        yaz = sarc_data[0:4] == b"Yaz0"
        if yaz:
            sarc_data = decompress(sarc_data)
        old_sarc = oead.Sarc(sarc_data)
        del sarc_data
        new_sarc = oead.SarcWriter.from_sarc(old_sarc)
        del old_sarc
        new_sarc.files[file] = data if isinstance(data, bytes) else bytes(data)
        new_bytes = new_sarc.write()[1]
        del new_sarc
        path.write_bytes(new_bytes if not yaz else compress(new_bytes))
        del new_bytes
    else:
        raise FileNotFoundError(f"{sarc} is not present in the master BCML mod")


def inject_files_into_actor(actor: str, files: Dict[str, ByteString]):
    actor_sarc: oead.Sarc
    if actor in TITLE_ACTORS:
        title_path = (
            get_master_modpack_dir() / get_content_path() / "Pack" / "TitleBG.pack"
        )
        if not title_path.exists():
            title_path = get_game_file("Pack/TitleBG.pack")
        title_sarc = oead.Sarc(title_path.read_bytes())
        actor_sarc = oead.Sarc(
            decompress(title_sarc.get_file_data(f"Actor/Pack/{actor}.sbactorpack").data)
        )
        del title_sarc
    else:
        actor_path = (
            get_master_modpack_dir()
            / get_content_path()
            / "Actor"
            / "Pack"
            / f"{actor}.sbactorpack"
        )
        if not actor_path.exists():
            actor_path = get_game_file(f"Actor/Pack/{actor}.sbactorpack")
        actor_sarc = oead.Sarc(decompress(actor_path.read_bytes()))
    new_sarc = oead.SarcWriter.from_sarc(actor_sarc)
    del actor_sarc
    for file, data in files.items():
        new_sarc.files[file] = oead.Bytes(data)
    out_bytes = compress(new_sarc.write()[1])

    if actor in TITLE_ACTORS:
        inject_file_into_sarc(
            f"Actor/Pack/{actor}.sbactorpack", out_bytes, "Pack/TitleBG.pack", True
        )
    else:
        output = (
            get_master_modpack_dir()
            / get_content_path()
            / "Actor"
            / "Pack"
            / f"{actor}.sbactorpack"
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(out_bytes)


@lru_cache(None)
def get_mod_preview(mod: BcmlMod, rules: ConfigParser = None) -> Path:
    if not rules:
        rules = RulesParser()
        rules.read(str(mod.path / "rules.txt"))
    if "url" in rules["Definition"]:
        url = str(rules["Definition"]["url"])
    if not list(mod.path.glob("thumbnail.*")):
        if "image" not in rules["Definition"]:
            if "url" in rules["Definition"] and "gamebanana.com" in url:
                response = urllib.request.urlopen(url)
                rdata = response.read().decode()
                img_match = re.search(
                    r"<meta property=\"og:image\" ?content=\"(.+?)\" />", rdata
                )
                if img_match:
                    image_path = "thumbnail.jfif"
                    urllib.request.urlretrieve(
                        img_match.group(1), str(mod.path / image_path)
                    )
                else:
                    raise IndexError(
                        f"Rule for {url} failed to find the remote preview"
                    )
            else:
                raise KeyError(f"No preview image available")
        else:
            image_path = str(rules["Definition"]["image"])
            if image_path.startswith("http"):
                urllib.request.urlretrieve(
                    image_path,
                    str(mod.path / ("thumbnail." + image_path.split(".")[-1])),
                )
                image_path = "thumbnail." + image_path.split(".")[-1]
            if not os.path.isfile(str(mod.path / image_path)):
                raise FileNotFoundError(
                    f"Preview {image_path} specified in rules.txt not found"
                )
    else:
        for thumb in mod.path.glob("thumbnail.*"):
            image_path = thumb
    return mod.path / image_path


def get_mod_link_meta(rules: ConfigParser = None):
    url = str(rules["Definition"]["url"])
    mod_domain = ""
    if "www." in url:
        mod_domain = url.split(".")[1]
    elif "http" in url:
        mod_domain = url.split("//")[1].split(".")[0]
    site_name = mod_domain.capitalize()
    fetch_site_meta = True
    if "site_meta" not in get_settings():
        set_site_meta("")
    if len(get_settings("site_meta").split(";")) > 1:
        for site_meta in get_settings("site_meta").split(";"):
            if site_meta.split(":")[0] == mod_domain:
                fetch_site_meta = False
                site_name = site_meta.split(":")[1]
    if fetch_site_meta:
        try:
            response = urllib.request.urlopen(url)
            rdata = response.read().decode()
            name_match = re.search(
                r"property=\"og\:site_name\"[^\/\>]"
                r"*content\=\"(.+?)\"|content\=\"(.+?)\"[^\/\>]"
                r"*property=\"og\:site_name\"",
                rdata,
            )
            if name_match:
                for group in name_match.groups():
                    if group is not None:
                        set_site_meta(f"{mod_domain}:{group}")
                        site_name = str(group)
            img_match = re.search(
                r"<link.*rel=\"(shortcut icon|icon)\".*href=\"(.+?)\".*>", rdata
            )
            if img_match:
                (get_exec_dir() / "work_dir" / "cache" / "site_meta").mkdir(
                    parents=True, exist_ok=True
                )
                try:
                    urllib.request.urlretrieve(
                        img_match.group(2),
                        str(
                            get_exec_dir()
                            / "work_dir"
                            / "cache"
                            / "site_meta"
                            / f'fav_{site_name}.{img_match.group(2).split(".")[-1]}'
                        ),
                    )
                except (
                    urllib.error.URLError,
                    urllib.error.HTTPError,
                    urllib.error.ContentTooShortError,
                ):
                    pass
        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            urllib.error.ContentTooShortError,
        ):
            pass
    favicon = ""
    for file in (get_exec_dir() / "work_dir" / "cache" / "site_meta").glob(
        f"fav_{site_name}.*"
    ):
        favicon = f'<img src="{file.resolve()}" height="16"/> '
    return f'<b>Link: <a style="text-decoration: none;" href="{url}">{favicon} {site_name}</a></b>'


def get_installed_mods(disabled: bool = False) -> List[BcmlMod]:
    return sorted(
        {
            BcmlMod.from_info(info)
            for info in get_modpack_dir().glob("*/info.json")
            if not (
                info.parent.stem == "9999_BCML"
                and (not disabled and (info.parent / ".disabled").exists())
            )
        },
        key=lambda mod: mod.priority,
    )


def create_bcml_graphicpack_if_needed():
    """Creates the BCML master modpack if it doesn't exist"""
    bcml_mod_dir = get_modpack_dir() / "9999_BCML"
    (bcml_mod_dir / "logs").mkdir(parents=True, exist_ok=True)
    rules = bcml_mod_dir / "rules.txt"
    if not rules.exists():
        with rules.open("w", encoding="utf-8") as r_file:
            r_file.write(
                "[Definition]\n"
                "titleIds = 00050000101C9300,00050000101C9400,00050000101C9500\n"
                "name = BCML\n"
                "path = The Legend of Zelda: Breath of the Wild/Mods/BCML\n"
                "description = Complete pack of mods merged using BCML\n"
                "version = 4\n"
                "fsPriority = 9999"
            )


def dict_merge(
    dct: Union[dict, oead.byml.Hash],
    merge_dct: Union[dict, oead.byml.Hash],
    overwrite_lists: bool = False,
    shallow: bool = False,
):
    for k in merge_dct:
        if shallow:
            dct[k] = merge_dct[k]
        elif (
            k in dct
            and (isinstance(dct[k], dict) or isinstance(dct[k], oead.byml.Hash))
            and (
                isinstance(merge_dct[k], Mapping)
                or isinstance(merge_dct[k], oead.byml.Hash)
            )
        ):
            dict_merge(dct[k], merge_dct[k])
        elif (
            k in dct
            and (isinstance(dct[k], list) or isinstance(dct[k], oead.byml.Array))
            and (
                isinstance(merge_dct[k], list)
                or isinstance(merge_dct[k], oead.byml.Array)
            )
        ):
            if overwrite_lists:
                dct[k] = merge_dct[k]
            else:
                dct[k].extend(merge_dct[k])
        else:
            dct[k] = merge_dct[k]


def create_schema_handler():
    # pylint: disable=import-error,undefined-variable
    import platform

    if platform.system() == "Windows":
        import winreg

        with winreg.CreateKey(
            winreg.HKEY_CURRENT_USER, r"Software\Classes\bcml"
        ) as key:
            try:
                winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Classes\bcml\shell\open\command",
                    0,
                    winreg.KEY_READ,
                )
            except (WindowsError, OSError):
                winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
                with winreg.CreateKey(key, r"shell\open\command") as key2:
                    if (
                        Path(os.__file__).parent.parent / "Scripts" / "bcml.exe"
                    ).exists():
                        exec_path = (
                            Path(os.__file__).parent.parent / "Scripts" / "bcml.exe"
                        )
                    elif (
                        Path(__file__).parent.parent.parent / "bin" / "bcml.exe"
                    ).exists():
                        exec_path = (
                            Path(__file__).parent.parent.parent / "bin" / "bcml.exe"
                        )
                    else:
                        return
                    winreg.SetValueEx(
                        key2, "", 0, winreg.REG_SZ, f'"{exec_path.resolve()}" "%1"'
                    )


class RulesParser(ConfigParser):
    def __init__(self):
        ConfigParser.__init__(self, dict_type=MultiDict)

    def write(self, fileobject):
        from io import StringIO

        buf = StringIO()
        ConfigParser.write(self, buf)
        config_str = re.sub(r"\[Preset[0-9]+\]", "[Preset]", buf.getvalue())
        fileobject.write(config_str)


class MultiDict(OrderedDict):
    _unique = 0

    def __setitem__(self, key, val):
        if isinstance(val, dict) and key == "Preset":
            self._unique += 1
            key += str(self._unique)
        OrderedDict.__setitem__(self, key, val)


class InstallError(Exception):
    error_text: str
    pass


class MergeError(Exception):
    def __init__(self, error_stuff):
        super().__init__(error_stuff)
        self.error_text = (
            f"There was a problem merging your mod(s). Details of the error:\n"
            f"""<textarea class="scroller" readonly id="error-msg">{
                getattr(error_stuff, "error_text", traceback.format_exc(-5))
            }</textarea>"""
            "Note that you this could leave your game in an unplayable state unless you remove"
            " the mod or mods responsible."
        )


class Messager:
    def __init__(self, window: Window):
        self.window = window
        self.log = get_data_dir() / "bcml.log"

    def write(self, string: str):
        from bcml.__main__ import LOG

        if (
            string.strip("") not in {"", "\n"}
            and not string.startswith("VERBOSE")
            and isinstance(string, str)
        ):
            self.window.evaluate_js(
                f"try {{ window.onMsg('{string}') }} catch(err) {{}};"
            )
        with LOG.open("a", encoding="utf-8") as log_file:
            if string.startswith("VERBOSE"):
                string = string[7:]
            log_file.write(f"{string}\n")

    def isatty(self):
        return False


if system() == "Windows":
    ZPATH = str(get_exec_dir() / "helpers" / "7z.exe")
else:
    ZPATH = str(get_exec_dir() / "helpers" / "7z")
