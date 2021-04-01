# Copyright 2020 Nicene Nerd <macadamiadaze@gmail.com>
# Licensed under GPLv3+
import multiprocessing
import shutil
from collections import namedtuple
from functools import partial, lru_cache
from math import ceil
from multiprocessing import Pool
from operator import itemgetter
from pathlib import Path
from typing import Dict, Union, List, Tuple
from zlib import crc32

import oead
from oead.byml import Hash, Array  # pylint: disable=import-error
import rstb
import rstb.util

from bcml import util, mergers

STATIC_PATH = Path("Map", "MainField", "Static.smubin")

KEY_MAP = {
    "DLCRestartPos": "UniqueName",
    "FldObj_DLC_ShootingStarCollaborationAnchor": "collaboSSFalloutFlagName",
    "KorokLocation": "Flag",
    "LocationMarker": "SaveFlag",
    "LocationPointer": "SaveFlag",
    "NonAutoGenArea": "Translate",
    "NonAutoPlacement": "Translate",
    "RoadNpcRestStation": "Translate",
    "StartPos": "PosName",
    "StaticGrudgeLocation": "Translate",
    "TargetPosMarker": "UniqueName",
    "TeraWaterDisable": "Translate",
    "TerrainHideCenterTag": "Translate",
}


@lru_cache(1024)
def key_from_coords(x: float, y: float, z: float) -> str:
    return str(ceil(x)) + str(ceil(y)) + str(ceil(z))


class MainfieldStaticMerger(mergers.Merger):
    # pylint: disable=abstract-method
    NAME: str = "mainstatic"

    def __init__(self):
        super().__init__(
            "mainfield static",
            "Merges changes the mainfield Static.smubin",
            "mainstatic.yml",
        )

    def generate_diff(self, mod_dir: Path, modded_files: List[Union[str, Path]]):
        static_path: Path
        if (
            mod_dir
            / util.get_dlc_path()
            / ("0010" if util.get_settings("wiiu") else "")
            / STATIC_PATH
        ) in modded_files:
            static_path = (
                mod_dir
                / util.get_dlc_path()
                / ("0010" if util.get_settings("wiiu") else "")
                / STATIC_PATH
            )
            stock_static_path = util.get_game_file(
                "Map/MainField/Static.smubin", aoc=True
            )
        elif (mod_dir / util.get_content_path() / STATIC_PATH) in modded_files:
            static_path = mod_dir / util.get_content_path() / STATIC_PATH
            stock_static_path = util.get_game_file("Map/MainField/Static.smubin")
        else:
            return None
        stock_static = Hash.from_binary(util.decompress(stock_static_path.read_bytes()))
        mod_static = Hash.from_binary(util.decompress(static_path.read_bytes()))
        diffs = Hash()
        get_trans = itemgetter("Translate")
        get_trans_id = lambda x: key_from_coords(x.x.v, x.y.v, x.z.v)
        for cat, key in KEY_MAP.items():
            if key == "Translate":
                id_getter = lambda x: get_trans_id(get_trans(x))
            else:
                id_getter = itemgetter(key)
            if cat not in stock_static:
                continue
            stock_items = {id_getter(item): item for item in stock_static[cat]}
            mod_items = {id_getter(item): item for item in mod_static[cat]}
            diffs[cat] = Hash(
                {
                    item_id: item
                    for item_id, item in mod_items.items()
                    if item_id not in stock_items or item != stock_items[item_id]
                }
            )
            for item_id, item in [
                (i1, i2) for i1, i2 in stock_items.items() if i1 not in mod_items
            ]:
                item["remove"] = True
                diffs[cat][item_id] = item
        return diffs

    def log_diff(self, mod_dir: Path, diff_material):
        if isinstance(diff_material, List):
            diff_material = self.generate_diff(mod_dir, diff_material)
        if diff_material:
            (mod_dir / "logs" / self._log_name).write_text(
                oead.byml.to_text(diff_material), encoding="utf-8"
            )
