# pylint: disable=missing-docstring,no-member,too-many-lines,invalid-name
# Copyright 2020 Nicene Nerd <macadamiadaze@gmail.com>
# Licensed under GPLv3+
import functools
import gc
import json
import multiprocessing
import os
import re
import shutil
import socket
import sys
import urllib.error
import urllib.request
from base64 import b64decode
from collections import OrderedDict
from collections.abc import Mapping
from configparser import ConfigParser
from contextlib import AbstractContextManager
from copy import deepcopy
from datetime import datetime
from functools import lru_cache
from io import StringIO
from multiprocessing import current_process
from pathlib import Path
from platform import system, python_version_tuple
from pprint import pformat
from subprocess import run, PIPE
from tempfile import mkdtemp
from time import time_ns
from typing import Union, List, Dict, ByteString, Tuple, Any, Optional, IO
from xml.dom import minidom

import oead
import requests
import xxhash  # pylint: disable=wrong-import-order
from oead.aamp import ParameterIO, ParameterList  # pylint:disable=import-error
from webview import Window  # pylint: disable=wrong-import-order

from bcml import bcml as rsext, locks
from bcml import pickles, DEBUG  # pylint: disable=unused-import
from bcml.__version__ import VERSION


CREATE_NO_WINDOW = 0x08000000
SARC_EXTS = {
    ".sarc",
    ".pack",
    ".bactorpack",
    ".bmodelsh",
    ".beventpack",
    # ".stera",
    ".stats",
    ".ssarc",
    ".sbactorpack",
    ".sbmodelsh",
    ".sbeventpack",
    # ".sstera",
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
    ".bwinfo",
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
        try:
            self._info = json.loads((self.path / "info.json").read_text("utf-8"))
            assert "name" in self._info
            assert "id" in self._info
            assert "priority" in self._info
        except (KeyError, AttributeError, json.decoder.JSONDecodeError):
            name = getattr(self, "_info", {}).get("name", "One of your mods")
            raise ValueError(
                f"{name} has an invalid or correct <code>info.json</code> meta file "
                "and cannot be loaded. You will need to manually correct the file "
                "or remove the mod folder and reinstall."
            )
        self.priority = self._info["priority"]
        self._preview = None

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
            "date": self.date,
            "priority": self.priority,
            "path": str(self.path),
            "disabled": (self.path / ".disabled").exists(),
            "id": self.id,
        }

    @staticmethod
    def from_json(json_data: dict):
        return BcmlMod(Path(json_data["path"]))

    @staticmethod
    def from_info(info_path: Path):
        return BcmlMod(info_path.parent)

    @staticmethod
    def meta_from_id(mod_id: str) -> Tuple[str, ...]:
        return tuple(b64decode(mod_id).decode("utf8").split("=="))

    @property
    def name(self) -> str:
        return self._info["name"]

    @property
    def id(self) -> str:
        return self._info["id"]

    @property
    def date(self) -> str:
        format_str = (
            "%m/%d/%Y %#I:%M %p" if system() == "Windows" else "%m/%d/%Y %-I:%M %p"
        )
        return datetime.fromtimestamp(
            (self.path / "info.json").stat().st_mtime
        ).strftime(format_str)

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
        return f"{self.priority:04}_" + re.sub(
            r"(?u)[^-\w.]", "", self.name.strip().replace(" ", "")
        )

    def _save_changes(self):
        self.info_path.write_text(
            json.dumps(self._info, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @property
    def mergers(self) -> list:
        # pylint: disable=import-outside-toplevel
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
        if self._preview is None:
            if not list(self.path.glob("thumbnail.*")):
                if not self.image:
                    if self.url and "gamebanana.com" in self.url:
                        response = urllib.request.urlopen(self.url)
                        rdata = response.read().decode()
                        img_match = re.search(
                            r"<meta property=\"og:image\" ?content=\"(.+?)\" />", rdata
                        )
                        if img_match:
                            image_path = "thumbnail.jfif"
                            (self.path / image_path).write_bytes(
                                requests.get(img_match.group(1)).content
                            )
                        else:
                            raise IndexError(
                                f"Rule for {self.url} failed to find the remote preview"
                            )
                    else:
                        raise KeyError("No preview image available")
                else:
                    image_path = self.image
                    if image_path.startswith("http"):
                        (
                            self.path / f"thumbnail.{image_path.split('.')[-1]}"
                        ).write_bytes(
                            requests.get(image_path, allow_redirects=True).content
                        )
                        image_path = f"thumbnail.{image_path.split('.')[-1]}"
                    if not os.path.isfile(str(self.path / image_path)):
                        raise FileNotFoundError(
                            f"Preview {image_path} specified in rules.txt not found"
                        )
            else:
                for thumb in self.path.glob("thumbnail.*"):
                    image_path = str(thumb)
            self._preview = self.path / image_path
        return self._preview


decompress = oead.yaz0.decompress
compress = oead.yaz0.compress


def vprint(content):
    if "Pool" in current_process().name:
        return
    if not isinstance(content, str):
        if isinstance(content, (oead.byml.Hash, oead.byml.Array)):
            content = oead.byml.to_text(content)
        elif isinstance(content, oead.aamp.ParameterIO):
            content = content.to_text()
        else:
            try:
                content = json.dumps(content, ensure_ascii=False, indent=2)
            except:  # pylint: disable=bare-except
                try:
                    content = pformat(content, compact=True, indent=2)
                except:  # pylint: disable=bare-except
                    return
    print(f"VERBOSE{content}")


def timed(func):
    def timed_function(*args, **kwargs):
        start = time_ns()
        res = func(*args, **kwargs)
        vprint(f"{func.__qualname__} took {(time_ns() - start) / 1000000000} seconds")
        return res

    return timed_function


def clear_all_caches():
    gc.collect()
    for wrap in {
        a for a in gc.get_objects() if isinstance(a, functools._lru_cache_wrapper)
    }:
        wrap.cache_clear()


def start_pool():
    return multiprocessing.Pool(processes=min(63, os.cpu_count()), maxtasksperchild=500)


def sanity_check():
    ver = python_version_tuple()
    if int(ver[0]) < 3 or (int(ver[0]) >= 3 and int(ver[1]) < 7):
        raise RuntimeError(
            f"BCML requires Python 3.7 or higher, but you have {ver[0]}.{ver[1]}"
        )
    is_64bits = sys.maxsize > 2**32
    if not is_64bits:
        raise RuntimeError(
            "BCML requires 64 bit Python, but you appear to be running 32 bit."
        )
    settings = get_settings()
    get_storage_dir()
    get_game_dir()
    if settings["wiiu"]:
        get_update_dir()
    if not settings["no_cemu"]:
        get_cemu_dir()


@lru_cache(1)
def get_exec_dir() -> Path:
    return Path(os.path.dirname(os.path.realpath(__file__)))


@lru_cache(2)
def get_python_exe(gui: bool) -> Path:
    embedded = [
        d
        for d in get_exec_dir().parents
        if (d / "python37._pth").exists() and (d / "pythonw.exe").exists()
    ]
    if embedded:
        return embedded[0] / ("pythonw.exe" if gui else "python.exe")
    else:
        if SYSTEM == "Windows":
            return (
                sys.executable.replace("pythonw.exe", "python.exe")
                if not gui
                else sys.executable.replace("python.exe", "pythonw.exe")
            )
        else:
            return sys.executable


@lru_cache(1)
def get_is_portable_mode() -> bool:
    return "--portable" in sys.argv


@lru_cache(None)
def get_data_dir() -> Path:
    if get_is_portable_mode():
        data_dir = Path(os.getcwd()) / "bcml-data"
    elif system() == "Windows":
        data_dir = Path(os.path.expandvars("%LOCALAPPDATA%")) / "bcml"
    else:
        data_dir = Path.home() / ".config" / "bcml"
    if not data_dir.exists():
        data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_storage_dir() -> Path:
    folder = get_settings("store_dir")
    if not folder:
        raise FileNotFoundError("No storage folder available")
    store_dir = Path(folder)
    if not store_dir.exists():
        store_dir.mkdir(parents=True, exist_ok=True)
    return store_dir


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


DEFAULT_SETTINGS = {
    "cemu_dir": "",
    "game_dir": "",
    "game_dir_nx": "",
    "update_dir": "",
    "dlc_dir": "",
    "dlc_dir_nx": "",
    "store_dir": str(get_data_dir()),
    "export_dir": "",
    "export_dir_nx": "",
    "load_reverse": False,
    "site_meta": "",
    "dark_theme": False,
    "no_guess": False,
    "lang": "",
    "no_cemu": False,
    "wiiu": True,
    "no_hardlinks": False,
    "force_7z": False,
    "suppress_update": False,
    "nsfw": False,
    "last_version": VERSION,
    "changelog": True,
    "strip_gfx": False,
    "auto_gb": True,
    "show_gb": False,
}


def get_settings(name: str = "") -> Any:
    try:
        if not hasattr(get_settings, "settings"):
            settings = {}
            settings_path = get_data_dir() / "settings.json"
            if not settings_path.exists():
                settings = DEFAULT_SETTINGS.copy()
                with settings_path.open("w", encoding="utf-8") as s_file:
                    json.dump(settings, s_file)
            else:
                tmp_settings_path = get_data_dir() / "tmp_settings.json"
                if tmp_settings_path.exists():
                    settings.update(json.loads(tmp_settings_path.read_text()))
                else:
                    settings.update(json.loads(settings_path.read_text()))
                for k, v in DEFAULT_SETTINGS.items():
                    if k not in settings:
                        settings[k] = v
                if settings["store_dir"] == "" or not settings["store_dir"]:
                    settings["store_dir"] = str(get_data_dir())
                if settings["cemu_dir"] and not settings["no_cemu"]:
                    settings["export_dir"] = str(
                        Path(settings["cemu_dir"])
                        / "graphicPacks"
                        / "BreathOfTheWild_BCML"
                    )
            setattr(get_settings, "settings", settings)
        if name:
            return getattr(get_settings, "settings", {}).get(name, False)
        return getattr(get_settings, "settings", {})
    except Exception as err:
        raise RuntimeError("BCML could not load its settings file") from err


def save_settings():
    with (get_data_dir() / "settings.json").open("w", encoding="utf-8") as s_file:
        json.dump(get_settings.settings, s_file, indent=2)


def get_cemu_dir() -> Path:
    cemu_dir = str(get_settings("cemu_dir"))
    if not cemu_dir or not Path(cemu_dir).is_dir():
        raise FileNotFoundError("The Cemu directory has moved or not been saved yet.")
    return Path(cemu_dir)


def set_cemu_dir(path: Path):
    settings = get_settings()
    settings["cemu_dir"] = str(path.resolve())
    save_settings()


def parse_cemu_settings(path: Path = None):
    path = path or get_cemu_dir() / "settings.xml"
    if not path.exists():
        raise FileNotFoundError("The Cemu settings file could not be found.")
    setread = ""
    with path.open("r", encoding="utf-8") as setfile:
        for line in setfile:
            setread += line.strip()
    return minidom.parseString(setread)


def get_game_dir() -> Path:
    game_dir = str(
        get_settings("game_dir")
        if get_settings("wiiu")
        else get_settings("game_dir_nx")
    )
    game_path = Path(game_dir)
    if not game_dir or not game_path.is_dir():
        raise FileNotFoundError(
            "The BOTW game dump directory has not been set or does not exist."
        )
    if not (game_path / "Pack" / "Dungeon000.pack").exists():
        raise FileNotFoundError(
            "The BOTW game dump directory is not set correctly. "
            "See the in-app help to correct this."
        )
    return game_path


def set_site_meta(site_meta: str):
    settings = get_settings()
    if "site_meta" not in settings:
        settings["site_meta"] = ""
    else:
        settings["site_meta"] = str(settings["site_meta"] + f"{site_meta};")
    save_settings()


def guess_game_dir(mlc_dir: Path) -> Optional[Path]:
    ids = {
        ("00050000", "101C9400"),
        ("00050000", "101C9500"),
        ("00050000", "101C9300"),
    }
    for (id1, id2) in ids:
        target = mlc_dir / "usr" / "title" / id1 / id2 / "content"
        if target.exists():
            return target
    return None


@lru_cache(None)
def get_title_id(game_dir: Path = None) -> Tuple[str, str]:
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
    return (title_id[0:7] + "0", title_id[8:])


def guess_update_dir(mlc_dir: Path, game_dir: Path) -> Optional[Path]:
    title_id = get_title_id(game_dir)
    mlc_dir = mlc_dir / "usr" / "title"
    # First try the 1.15.11c mlc layout
    if (mlc_dir / f"{title_id[0][0:7]}E" / title_id[1] / "content").exists():
        return mlc_dir / f"{title_id[0][0:7]}E" / title_id[1] / "content"
    # Then try the legacy layout
    if (mlc_dir / title_id[0] / title_id[1] / "content").exists():
        return mlc_dir / title_id[0] / title_id[1] / "content"
    return None


@lru_cache(None)
def get_update_dir() -> Path:
    if not get_settings("wiiu"):
        return get_game_dir()
    update_str = get_settings("update_dir")
    if not update_str:
        raise FileNotFoundError(
            "The BOTW update directory has not been set or does not exist"
        )
    update_dir = Path(update_str)
    if not update_dir.exists():
        raise FileNotFoundError(
            "The BOTW update directory has not been set or does not exist"
        )
    if not (
        update_dir / "Actor" / "Pack" / "FldObj_MountainSnow_A_M_02.sbactorpack"
    ).exists():
        raise FileNotFoundError(
            "The BOTW update directory is set incorrectly or missing files. "
            "See the in-app help to correct this."
        )
    return update_dir


def guess_aoc_dir(mlc_dir: Path, game_dir: Path) -> Optional[Path]:
    title_id = get_title_id(game_dir)
    mlc_dir = mlc_dir / "usr" / "title"
    # First try the 1.15.11c mlc layout
    if (mlc_dir / f"{title_id[0][0:7]}C" / title_id[1] / "content" / "0010").exists():
        return mlc_dir / f"{title_id[0][0:7]}C" / title_id[1] / "content" / "0010"
    # Then try the legacy layout
    if (mlc_dir / title_id[0] / title_id[1] / "aoc" / "content" / "0010").exists():
        return mlc_dir / title_id[0] / title_id[1] / "aoc" / "content" / "0010"
    return None


def get_aoc_dir() -> Path:
    dlc_str = (
        get_settings("dlc_dir") if get_settings("wiiu") else get_settings("dlc_dir_nx")
    )
    if not dlc_str:
        raise FileNotFoundError("The BOTW DLC directory has not been set.")
    aoc_dir = Path(dlc_str)
    if not aoc_dir.exists():
        raise FileNotFoundError(
            "The BOTW DLC directory has not been set or does not exist."
        )
    if not (aoc_dir / "Pack" / "AocMainField.pack").exists():
        raise FileNotFoundError(
            "The BOTW DLC directory is set incorrectly or missing files. "
            "See the in-app help to correct this."
        )
    return aoc_dir


def get_content_path() -> str:
    return "content" if get_settings("wiiu") else "01007EF00011E000/romfs"


def get_dlc_path() -> str:
    return "aoc" if get_settings("wiiu") else "01007EF00011F001/romfs"


def get_user_languages(folder: Optional[Path] = None) -> set:
    langs = set()
    for file in ((folder or get_update_dir()) / "Pack").glob("Bootup_????.pack"):
        langs.add(get_file_language(file.name))
    return langs


class TempSettingsContext(AbstractContextManager):
    _settings: dict
    _tmp_settings: dict

    def __init__(self, tmp_settings: dict):
        self._settings = get_settings().copy()
        self._tmp_settings = tmp_settings

    def __enter__(self):
        clear_all_caches()
        getattr(get_settings, "settings").update(self._tmp_settings)
        with (get_data_dir() / "tmp_settings.json").open(
            "w", encoding="utf-8"
        ) as s_file:
            json.dump(get_settings.settings, s_file, indent=2)

    def __exit__(self, exctype, excinst, exctb):
        setattr(get_settings, "settings", self._settings)
        clear_all_caches()
        (get_data_dir() / "tmp_settings.json").unlink()


class TempModContext(TempSettingsContext):
    _tmpdir: Path

    def __init__(self, path: Path = None):
        self._tmpdir = path or Path(mkdtemp())
        no_hardlinks: bool
        if SYSTEM == "Windows":
            no_hardlinks = get_storage_dir().drive != self._tmpdir.drive
        else:
            no_hardlinks = get_storage_dir().stat().st_dev != self._tmpdir.stat().st_dev
        super().__init__({"store_dir": str(self._tmpdir), "no_hardlinks": no_hardlinks})

    def __exit__(self, exctype, excinst, exctb):
        shutil.rmtree(self._tmpdir, ignore_errors=True)
        super().__exit__(exctype, excinst, exctb)


def get_modpack_dir() -> Path:
    return get_storage_dir() / ("mods" if get_settings("wiiu") else "mods_nx")


def get_profiles_dir() -> Path:
    return get_storage_dir() / ("profiles" if get_settings("wiiu") else "profiles_nx")


class ProfileNotFoundError(Exception):
    pass


def get_profiles() -> List[Dict[str, str]]:
    profiles = []
    profiles_dir = get_profiles_dir().glob("*")
    for entry in profiles_dir:
        if not entry.is_dir():
            continue
        profile = parse_profile_file(entry / ".profile")
        profile["path"] = str(entry)
        profiles.append(profile)
    return profiles


def get_profile(profile_name: str) -> Dict[str, str]:
    profiles_dir = get_profiles_dir().glob("*")
    for entry in profiles_dir:
        if not entry.is_dir():
            continue
        profile = parse_profile_file(entry / ".profile")
        if profile["name"] == profile_name:
            profile["path"] = str(entry)
            return profile
    raise ProfileNotFoundError(f"No profile found with name: '{profile_name}'")


def get_profile_path(profile_name: str) -> Path:
    profiles_dir = get_profiles_dir().glob("*")
    for entry in profiles_dir:
        if not entry.is_dir():
            continue
        profile = parse_profile_file(entry / ".profile")
        if profile["name"] == profile_name:
            return str(entry)
    raise ProfileNotFoundError(f"No profile found with name: '{profile_name}'")


def get_current_profile() -> Union[Dict[str, str], None]:
    current_profile_file = get_modpack_dir() / ".profile"
    if not current_profile_file.exists():
        return None
    profile = parse_profile_file(current_profile_file)
    try:
        profile["path"] = get_profile_path(profile["name"])
    except ProfileNotFoundError:
        profile["path"] = None
    return profile


def parse_profile_file(profile_file: Path) -> Dict[str, str]:
    if not profile_file.exists():
        raise FileNotFoundError(f"Profile file not found: '{profile_file}'")
    profile_data = profile_file.read_text("utf-8").split("\t")
    return {"name": profile_data[0]}


def set_profile(profile_name: str) -> None:
    profile_path = get_profile_path(profile_name)
    mod_dir = get_modpack_dir()
    with locks.mod_dir:
        shutil.rmtree(mod_dir)
        shutil.copytree(profile_path, mod_dir)


def delete_profile(profile_name: str) -> None:
    profile_path = get_profile_path(profile_name)
    shutil.rmtree(profile_path)
    current_profile = get_current_profile()
    if current_profile and current_profile["name"] == profile_name:
        with locks.mod_dir:
            os.remove(get_modpack_dir() / ".profile")


def save_profile(profile_name: str) -> None:
    profile_data = [profile_name]
    mod_dir = get_modpack_dir()
    profile_file = mod_dir / ".profile"
    profile_file.write_text("\t".join(profile_data))
    profile_dir = get_profiles_dir() / get_safe_pathname(profile_name)
    if profile_dir.exists():
        shutil.rmtree(profile_dir)
    with locks.mod_dir:
        shutil.copytree(mod_dir, profile_dir)


@lru_cache(None)
def get_game_file(path: Union[Path, str], aoc: bool = False) -> Path:
    if str(path).replace("\\", "/").startswith(f"{get_content_path()}/"):
        path = Path(str(path).replace("\\", "/").replace(f"{get_content_path()}/", ""))
    if isinstance(path, str):
        path = Path(path)
    game_dir = get_game_dir()
    if get_settings("wiiu"):
        update_dir = get_update_dir()
    aoc_dir: Optional[Path]
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
        raise FileNotFoundError(
            f"{path} is a DLC file, but the DLC directory is missing."
        )
    if get_settings("wiiu"):
        if (update_dir / path).exists():
            return update_dir / path
    if (game_dir / path).exists():
        return game_dir / path
    if aoc_dir and (aoc_dir / path).exists():
        return aoc_dir / path
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


@lru_cache(1)
def get_merged_modpack_dir() -> Path:
    if get_settings("wiiu"):
        return get_storage_dir() / "merged"
    else:
        return get_storage_dir() / "merged_nx"


@lru_cache(2)
def get_hash_table(wiiu: bool = True) -> Dict[str, List[int]]:
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
def get_canon_name(file: Union[str, Path], allow_no_source: bool = False) -> str:
    if isinstance(file, str):
        file = Path(file)
    name = (
        file.as_posix()
        .replace("\\", "/")
        .replace("atmosphere/", "")
        .replace("contents/", "")
        .replace("titles/", "")
        .replace("7EF0", "7ef0")
        .replace("1E0", "1e0")
        .replace("1F0", "1f0")
        .replace("01007ef00011e000/romfs", "content")
        .replace("01007ef00011e000/romfs", "content")
        .replace("01007ef00011e001/romfs", "aoc/0010")
        .replace("01007ef00011e002/romfs", "aoc/0010")
        .replace("01007ef00011f001/romfs", "aoc/0010")
        .replace("01007ef00011f002/romfs", "aoc/0010")
        .replace(".s", ".")
    )
    if "aoc/" in name:
        name = name.replace("aoc/content", "aoc").replace("aoc", "Aoc")
    elif "content/" in name and "/aoc" not in name:
        name = name.replace("content/", "")
    elif not allow_no_source:
        raise ValueError(f"{file} does not begin with a valid content directory.")
    return name


@lru_cache(None)
def get_mod_id(mod_name: str, priority: int) -> str:
    return f"{priority:04}_" + get_safe_pathname(mod_name)


def get_safe_pathname(name: str, delimiter: str = "") -> str:
    return re.sub(r"(?u)[^-\w.]", "", name.strip().replace(" ", delimiter))


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
    if lang_match:
        return lang_match.group(1)
    else:
        raise ValueError(f"File {file} does not have a language specifier in its path")


def is_file_modded(name: str, file: Union[bytes, Path], count_new: bool = True) -> bool:
    table = get_hash_table(get_settings("wiiu"))
    if name not in table:
        return count_new
    contents = (
        file
        if isinstance(file, bytes)
        else file.read_bytes()
        if isinstance(file, Path)
        else bytes(file)
    )
    if contents[0:4] == b"Yaz0":
        try:
            contents = decompress(contents)
        except RuntimeError as err:
            raise ValueError(f"Invalid yaz0 file {name}") from err
    fhash = xxhash.xxh64_intdigest(contents)
    return not fhash in table[name]


@lru_cache(None)
def is_file_sarc(path: str) -> bool:
    ext = os.path.splitext(str(path))[1]
    return ext in SARC_EXTS


def unyaz_if_needed(file_bytes: bytes) -> bytes:
    if file_bytes[0:4] == b"Yaz0":
        return bytes(decompress(file_bytes))
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
            decompress(title_sarc.get_file(f"Actor/Pack/{actor}.sbactorpack").data)
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
            for m in reversed(get_installed_mods()):
                try:
                    actor_path = list(m.path.rglob(f"{actor}.sbactorpack"))[0]
                    break
                except IndexError:
                    continue
            else:
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
def get_mod_preview(mod: BcmlMod) -> Path:
    if mod.url:
        url = mod.url
    if not list(mod.path.glob("thumbnail.*")):
        if not mod.image:
            if url and "gamebanana.com" in url:
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
                raise KeyError("No preview image available")
        else:
            image_path = mod.image
            if image_path.startswith("http"):
                urllib.request.urlretrieve(
                    image_path,
                    str(mod.path / ("thumbnail." + image_path.split(".")[-1])),
                )
                image_path = "thumbnail." + image_path.split(".")[-1]
            if not os.path.isfile(str(mod.path / image_path)):
                raise FileNotFoundError(
                    f"Preview {image_path} specified in meta not found"
                )
    else:
        for thumb in mod.path.glob("thumbnail.*"):
            image_path = str(thumb)
    return mod.path / image_path


def get_mod_link_meta(mod: BcmlMod):
    # pylint: disable=too-many-branches
    url = mod.url
    mod_domain = ""
    if "www." in url:
        mod_domain = url.split(".")[1]
    elif "http" in url:
        mod_domain = url.split("//")[1].split(".")[0]
    site_name = mod_domain.capitalize()
    fetch_site_meta = True
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
                or (not disabled and (info.parent / ".disabled").exists())
            )
        },
        key=lambda mod: mod.priority,
    )


def create_bcml_graphicpack_if_needed():
    """Creates the BCML master modpack if it doesn't exist"""
    bcml_mod_dir = get_modpack_dir() / "9999_BCML"
    (bcml_mod_dir / "logs").mkdir(parents=True, exist_ok=True)
    rules = bcml_mod_dir / "rules.txt"
    if not (rules.exists() or get_settings("no_cemu")):
        rules.write_text(
            "[Definition]\n"
            "titleIds = 00050000101C9300,00050000101C9400,00050000101C9500\n"
            "name = BCML\n"
            "path = The Legend of Zelda: Breath of the Wild/Mods/BCML\n"
            "description = Complete pack of mods merged using BCML\n"
            "version = 7\n"
            "default = true\n"
            "fsPriority = 9999",
            encoding="utf-8",
        )


def create_shortcuts(desktop: bool, start_menu: bool):
    if desktop:
        rsext.manager.create_shortcut(
            str(get_python_exe(True)),
            str(get_exec_dir() / "data" / "bcml.ico"),
            str(Path(r"~\Desktop\BCML.lnk").expanduser()),
        )
    if start_menu:
        rsext.manager.create_shortcut(
            str(get_python_exe(True)),
            str(get_exec_dir() / "data" / "bcml.ico"),
            str(
                Path(
                    r"~\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\BCML.lnk"
                ).expanduser()
            ),
        )


def download_webview2():
    from bcml import native_msg

    native_msg(
        "Neither CEF nor Edge WebView2 is available. "
        " Click OK to download the WebView2 runtime at https://go.microsoft.com/fwlink/p/?LinkId=2124703. "
        " Run 'pip install cefpython3' in CMD to install CEF. "
        "Once both have been installed, restart BCML.",
        "Error",
    )
    path = Path(mkdtemp()) / f"webview.exe"
    try:
        res: requests.Response = requests.get(
            "https://go.microsoft.com/fwlink/p/?LinkId=2124703"
        )
        with path.open("wb") as tmp_file:
            for chunk in res.iter_content(chunk_size=1024):
                tmp_file.write(chunk)
    except (
        FileNotFoundError,
        PermissionError,
        OSError,
        requests.ConnectionError,
        requests.RequestException,
    ) as err:
        native_msg(str(err), "Error")
    try:
        run(
            [str(path)],
            stdout=PIPE,
            stderr=PIPE,
            creationflags=CREATE_NO_WINDOW,
            check=True,
        )
    except Exception as err:
        native_msg(str(err), "Error")
    sys.exit(0)


UNDERRIDE = "UNDERRIDE_CONST"


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
            and (isinstance(dct[k], (dict, oead.byml.Hash)))
            and (isinstance(merge_dct[k], (Mapping, oead.byml.Hash)))
        ):
            dict_merge(dct[k], merge_dct[k], overwrite_lists=overwrite_lists)
        elif (
            k in dct
            and (isinstance(dct[k], (list, oead.byml.Array)))
            and (isinstance(merge_dct[k], (list, oead.byml.Array)))
        ):
            if overwrite_lists:
                dct[k] = merge_dct[k]
            else:
                dct[k].extend(merge_dct[k])
        else:
            dct[k] = (
                merge_dct[k] if (merge_dct[k] != UNDERRIDE or k not in dct) else dct[k]
            )


def pio_merge(
    ref: Union[ParameterIO, ParameterList], mod: Union[ParameterIO, ParameterList]
) -> Union[ParameterIO, ParameterList]:
    if isinstance(ref, ParameterIO):
        merged = deepcopy(ref)
    else:
        merged = ref
    for key, plist in mod.lists.items():
        if key not in merged.lists:
            merged.lists[key] = plist
        else:
            merged_list = pio_merge(merged.lists[key], plist)
            if merged_list.lists or merged_list.objects:
                merged.lists[key] = merged_list
    for key, pobj in mod.objects.items():
        if key not in merged.objects:
            merged.objects[key] = pobj
        else:
            merged_pobj = merged.objects[key]
            for pkey, param in pobj.params.items():
                if pkey not in merged_pobj.params or param != merged_pobj.params[pkey]:
                    merged_pobj.params[pkey] = param
    return merged


def pio_subtract(
    ref: Union[ParameterIO, ParameterList], mod: Union[ParameterIO, ParameterList]
) -> Union[ParameterIO, ParameterList]:
    if isinstance(ref, ParameterIO):
        merged = deepcopy(ref)
    else:
        merged = ref
    for key, plist in mod.lists.items():
        if key in merged.lists:
            pio_subtract(merged.lists[key], plist)
            if (
                len(merged.lists[key].objects) == 0
                and len(merged.lists[key].lists) == 0
            ):
                del merged.lists[key]
    for key, pobj in mod.objects.items():
        if key in merged.objects:
            merged_pobj = merged.objects[key]
            for pkey in pobj.params:
                if pkey in merged_pobj.params:
                    del merged_pobj.params[pkey]
            if len(merged_pobj.params) == 0:
                del merged.objects[key]
    return merged


def get_open_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@lru_cache(1)
def get_latest_bcml() -> str:
    try:
        res = requests.get("https://pypi.org/rss/project/bcml/releases.xml")
        doc = minidom.parseString(res.text)
        versions = sorted(
            (
                item.getElementsByTagName("title")[0].childNodes[0].data
                for item in doc.getElementsByTagName("item")
            ),
            reverse=True,
        )
        if DEBUG:
            return versions[0]
        return next(v for v in versions if "a" not in v and "b" not in v)
    except:  # pylint: disable=bare-except
        return "0.0.0"


class RulesParser(ConfigParser):
    # pylint: disable=arguments-differ,too-many-ancestors
    def __init__(self):
        ConfigParser.__init__(self, dict_type=MultiDict)

    def write(self, fileobject):
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
    def __init__(self, error_stuff, mod_name: str = "your mod"):
        super().__init__(
            f"An error occured when installing {mod_name}. {str(error_stuff)}\n"
            "Your mod is being removed, and no changes have been made."
        )


class MergeError(Exception):
    def __init__(self, error_stuff):
        super().__init__(
            f"An error occured when merging your mod(s). {str(error_stuff)}\n"
            "Note that you this could leave your game in an unplayable state."
        )


class Messager:
    def __init__(self, window: Window):
        self.window = window
        self.log_file = get_data_dir() / "bcml.log"
        self.log: List[str] = []
        self.i = 0

    def write(self, s: str):
        stripped = s.replace("VERBOSE", "")
        self.log.append(stripped)
        self.i += 1
        if self.i == 256:
            self.save()
            self.i = 0
        if DEBUG:
            sys.__stdout__.write(stripped)

    def isatty(self):  # pylint: disable=no-self-use
        return False

    def save(self):
        self.log_file.write_text("\n".join(self.log))

    def __del__(self):
        self.save()
        del self.log


@lru_cache(1)
def get_7z_path():
    if system() == "Windows":
        return str(get_exec_dir() / "helpers" / "7z.exe")
    bundle_path = get_exec_dir() / "helpers" / "7z"
    if not os.access(bundle_path, os.X_OK):
        if not os.access(bundle_path, os.W_OK):
            raise PermissionError(
                f"{bundle_path} is not executable and we don't have the permissions to change that"
            )
        os.chmod(bundle_path, 0o755)
    if get_settings("force_7z"):
        return str(bundle_path)
    return shutil.which("7z") or str(bundle_path)


LOG = get_data_dir() / "bcml.log"
SYSTEM = system()
