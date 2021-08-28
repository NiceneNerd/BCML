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


@lru_cache(1024)
def key_from_coords(x: float, y: float, z: float) -> str:
    return str(ceil(x)) + str(ceil(y)) + str(ceil(z))


def get_id(item: Hash) -> str:
    def find_name(item: Hash) -> str:
        for k, v in item.items():
            if "name" in k.lower():
                return v
        else:
            return ""

    return (
        key_from_coords(
            item["Translate"]["X"].v,
            item["Translate"]["Y"].v,
            item["Translate"]["Z"].v,
        )
        + find_name(item)
    )


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
        mod_data: bytes
        stock_data: bytes
        if (
            mod_dir
            / util.get_dlc_path()
            / ("0010" if util.get_settings("wiiu") else "")
            / STATIC_PATH
        ) in modded_files:
            mod_data = (
                mod_dir
                / util.get_dlc_path()
                / ("0010" if util.get_settings("wiiu") else "")
                / STATIC_PATH
            ).read_bytes()
            stock_data = util.get_game_file(
                "Map/MainField/Static.smubin", aoc=True
            ).read_bytes()
        elif (
            f"{util.get_content_path()}/Pack/Bootup.pack//Map/MainField/Static.smubin"
        ) in modded_files:
            mod_data = util.get_nested_file_bytes(
                (
                    str(mod_dir / util.get_content_path() / "Pack" / "Bootup.pack")
                    + "//Map/MainField/Static.smubin"
                ),
                unyaz=False,
            )
            stock_data = util.get_nested_file_bytes(
                (
                    str(util.get_game_file("Pack/Bootup.pack"))
                    + "//Map/MainField/Static.smubin"
                ),
                unyaz=False,
            )
        else:
            return None
        stock_static: Hash = oead.byml.from_binary(util.decompress(stock_data))
        mod_static: Hash = oead.byml.from_binary(util.decompress(mod_data))
        diffs = Hash()
        for cat in stock_static:
            if cat not in stock_static:
                continue
            stock_items = {get_id(item): item for item in stock_static[cat]}
            mod_items = {get_id(item): item for item in mod_static[cat]}
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
            if not diffs[cat]:
                del diffs[cat]
        return diffs

    def log_diff(self, mod_dir: Path, diff_material):
        if isinstance(diff_material, List):
            diff_material = self.generate_diff(mod_dir, diff_material)
        if diff_material:
            (mod_dir / "logs" / self._log_name).write_text(
                oead.byml.to_text(diff_material), encoding="utf-8"
            )

    def get_mod_diff(self, mod: util.BcmlMod):
        diff = oead.byml.Hash()
        if self.is_mod_logged(mod):
            diff = oead.byml.from_text(
                (mod.path / "logs" / self._log_name).read_text("utf-8")
            )
        for opt in {d for d in (mod.path / "options").glob("*") if d.is_dir()}:
            if (opt / "logs" / self._log_name).exists():
                util.dict_merge(
                    diff,
                    oead.byml.from_text(
                        (opt / "logs" / self._log_name).read_text("utf-8")
                    ),
                    overwrite_lists=True,
                )
        return diff

    def get_all_diffs(self):
        diffs = []
        for m in util.get_installed_mods():
            diff = self.get_mod_diff(m)
            if diff:
                diffs.append(diff)
        return diffs

    def consolidate_diffs(self, diffs):
        if not diffs:
            return {}
        all_diffs = oead.byml.Hash()
        for diff in diffs:
            util.dict_merge(all_diffs, diff, overwrite_lists=True)
        return all_diffs

    @util.timed
    def perform_merge(self):
        diffs = self.consolidate_diffs(self.get_all_diffs())
        output: Path
        static_data: Path
        try:
            util.get_aoc_dir()
            output = (
                util.get_master_modpack_dir()
                / util.get_dlc_path()
                / ("0010" if util.get_settings("wiiu") else "")
                / STATIC_PATH
            )
            static_data = util.get_game_file(
                "Map/MainField/Static.smubin", aoc=True
            ).read_bytes()
        except FileNotFoundError:
            output = util.get_master_modpack_dir() / "logs" / "mainstatic.smubin"
            static_data = util.get_nested_file_bytes(
                (
                    str(util.get_game_file("Pack/Bootup.pack"))
                    + "//Map/MainField/Static.smubin"
                ),
                unyaz=False,
            )
        if not diffs:
            try:
                output.unlink()
            except:
                pass
            return
        stock_static = oead.byml.from_binary(util.decompress(static_data))
        merged = Hash()
        for cat in stock_static:
            if cat in diffs:
                items = {get_id(item): item for item in stock_static[cat]}
                util.dict_merge(items, diffs[cat])
                merged[cat] = Array(
                    [item for _, item in items.items() if "remove" not in item]
                )
            else:
                merged[cat] = stock_static[cat]
        data = util.compress(
            oead.byml.to_binary(merged, big_endian=util.get_settings("wiiu"))
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(data)
        if "mainstatic" in str(output):
            util.inject_file_into_sarc(
                "Map/MainField/Static.smubin",
                data,
                "Pack/Bootup.pack",
                create_sarc=True,
            )

    def get_checkbox_options(self):
        return []

    @staticmethod
    def is_bootup_injector():
        try:
            util.get_aoc_dir()
            return False
        except FileNotFoundError:
            return True

    def get_bootup_injection(self):
        tmp_sarc = util.get_master_modpack_dir() / "logs" / "mainstatic.smubin"
        if tmp_sarc.exists():
            return (
                "Map/MainField/Static.smubin",
                tmp_sarc,
            )
        return

    def get_mod_edit_info(self, mod: util.BcmlMod) -> set:
        return set(self.get_mod_diff(mod).keys())
