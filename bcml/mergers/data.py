"""
Provides functions to diff and merge BOTW gamedat and savedata.
"""
# Copyright 2020 Nicene Nerd <macadamiadaze@gmail.com>
# Licensed under GPLv3+
# pylint: disable=unsupported-assignment-operation
from functools import lru_cache
from math import ceil
from multiprocessing import Pool, pool
from operator import itemgetter
from pathlib import Path
from typing import List, Union, Dict

import oead
import xxhash
from oead.byml import Hash

from bcml import util, mergers
from bcml.mergers import rstable
from bcml.util import BcmlMod


def get_stock_gamedata() -> oead.Sarc:
    bootup = oead.Sarc(util.get_game_file("Pack/Bootup.pack").read_bytes())
    return oead.Sarc(util.decompress(bootup.get_file("GameData/gamedata.ssarc").data))


def get_stock_savedata() -> oead.Sarc:
    bootup = oead.Sarc(util.get_game_file("Pack/Bootup.pack").read_bytes())
    return oead.Sarc(
        util.decompress(bootup.get_file("GameData/savedataformat.ssarc").data)
    )


@lru_cache(None)
def get_gamedata_hashes() -> Dict[str, int]:
    gamedata = get_stock_gamedata()
    return {
        file.name: xxhash.xxh64_intdigest(file.data) for file in gamedata.get_files()
    }


@lru_cache(None)
def get_savedata_hashes() -> Dict[str, int]:
    savedata = get_stock_savedata()
    return {
        file.name: xxhash.xxh64_intdigest(file.data) for file in savedata.get_files()
    }


def consolidate_gamedata(gamedata: oead.Sarc) -> Hash:
    data = Hash()
    for file in gamedata.get_files():
        util.dict_merge(data, oead.byml.from_binary(file.data))
    del gamedata
    return data


def diff_gamedata_type(data_type: str, mod_data: dict, stock_data: dict) -> Hash:
    stock_entries = {entry["DataName"]: entry for entry in stock_data}
    del stock_data
    mod_entries = {entry["DataName"] for entry in mod_data}
    diffs = Hash(
        {
            "add": Hash(
                {
                    entry["DataName"]: entry
                    for entry in mod_data
                    if (
                        entry["DataName"] not in stock_entries
                        or entry != stock_entries[entry["DataName"]]
                    )
                }
            ),
            "del": oead.byml.Array(
                {entry for entry in stock_entries if entry not in mod_entries}
            ),
        }
    )
    del stock_entries
    del mod_entries
    del mod_data
    return Hash({data_type: diffs})


def get_modded_gamedata_entries(gamedata: oead.Sarc, pool: pool.Pool = None) -> Hash:
    this_pool = pool or Pool(maxtasksperchild=500)
    stock_data = consolidate_gamedata(get_stock_gamedata())
    mod_data = consolidate_gamedata(gamedata)
    del gamedata
    results = this_pool.starmap(
        diff_gamedata_type,
        ((key, mod_data[key], stock_data[key]) for key in mod_data),
    )
    diffs = Hash({data_type: diff for d in results for data_type, diff in d.items()})
    del results
    if not pool:
        this_pool.close()
        this_pool.join()
    del stock_data
    del mod_data
    return diffs


def get_modded_savedata_entries(savedata: oead.Sarc) -> Hash:
    ref_savedata = get_stock_savedata().get_files()
    ref_hashes = {
        int(item["HashValue"])
        for file in sorted(ref_savedata, key=lambda f: f.name)[0:-2]
        for item in oead.byml.from_binary(file.data)["file_list"][1]
    }
    new_entries = oead.byml.Array()
    mod_hashes = set()
    for file in savedata.get_files():
        data = oead.byml.from_binary(file.data)
        if data["file_list"][0]["file_name"] != "game_data.sav":
            continue
        entries = data["file_list"][1]
        mod_hashes |= {int(item["HashValue"]) for item in entries}
        new_entries.extend(
            [item for item in entries if int(item["HashValue"]) not in ref_hashes]
        )
    del ref_savedata
    return Hash(
        {
            "add": new_entries,
            "del": oead.byml.Array(
                oead.S32(item)
                for item in {item for item in ref_hashes if item not in mod_hashes}
            ),
        }
    )


class GameDataMerger(mergers.Merger):
    # pylint: disable=abstract-method
    NAME: str = "gamedata"

    def __init__(self):
        super().__init__(
            "game data", "Merges changes to gamedata.sarc", "gamedata.yml", options={}
        )

    def generate_diff(self, mod_dir: Path, modded_files: List[Union[Path, str]]):
        if (
            f"{util.get_content_path()}/Pack/Bootup.pack//GameData/gamedata.ssarc"
            in modded_files
        ):
            print("Logging changes to game data flags...")
            bootup_sarc = oead.Sarc(
                util.unyaz_if_needed(
                    (
                        mod_dir / util.get_content_path() / "Pack" / "Bootup.pack"
                    ).read_bytes()
                )
            )
            data_sarc = oead.Sarc(
                util.decompress(bootup_sarc.get_file("GameData/gamedata.ssarc").data)
            )
            diff = get_modded_gamedata_entries(data_sarc, pool=self._pool)
            del bootup_sarc
            del data_sarc
            return diff
        else:
            return {}

    def log_diff(self, mod_dir: Path, diff_material):
        if isinstance(diff_material, List):
            diff_material = self.generate_diff(mod_dir, diff_material)
        if diff_material:
            (mod_dir / "logs" / self._log_name).write_text(
                oead.byml.to_text(diff_material), encoding="utf-8"
            )
            del diff_material

    def get_mod_diff(self, mod: BcmlMod):
        diffs = Hash()
        if self.is_mod_logged(mod):
            util.dict_merge(
                diffs,
                oead.byml.from_text(
                    (mod.path / "logs" / self._log_name).read_text(encoding="utf-8")
                ),
                overwrite_lists=True,
            )
        for opt in {d for d in (mod.path / "options").glob("*") if d.is_dir()}:
            if (opt / "logs" / self._log_name).exists():
                util.dict_merge(
                    diffs,
                    oead.byml.from_text(
                        (opt / "logs" / self._log_name).read_text("utf-8")
                    ),
                    overwrite_lists=True,
                )
        return diffs

    def get_mod_edit_info(self, mod: util.BcmlMod) -> set:
        edited = set()
        diff = self.get_mod_diff(mod)
        for _, stuff in diff.items():
            for items in dict(stuff["add"]).values():
                edited |= set(items.keys())
            edited |= set(stuff["del"])
        return edited

    def get_all_diffs(self):
        diffs = []
        for mod in util.get_installed_mods():
            diff = self.get_mod_diff(mod)
            if diff:
                diffs.append(diff)
        return diffs

    def consolidate_diffs(self, diffs: list):
        all_diffs = Hash()
        for diff in diffs:
            util.dict_merge(all_diffs, diff, overwrite_lists=True)
        return all_diffs

    @util.timed
    def perform_merge(self):
        force = self._options.get("force", False)
        glog_path = util.get_master_modpack_dir() / "logs" / "gamedata.log"

        modded_entries = self.consolidate_diffs(self.get_all_diffs())
        if not modded_entries:
            print("No gamedata merging necessary.")
            if glog_path.exists():
                glog_path.unlink()
            if (util.get_master_modpack_dir() / "logs" / "gamedata.sarc").exists():
                (util.get_master_modpack_dir() / "logs" / "gamedata.sarc").unlink()
            return
        if glog_path.exists() and not force:
            with glog_path.open("r") as l_file:
                if xxhash.xxh64_hexdigest(str(modded_entries)) == l_file.read():
                    print("No gamedata merging necessary.")
                    return

        print("Loading stock gamedata...")
        gamedata = consolidate_gamedata(get_stock_gamedata())
        merged_entries = {
            data_type: Hash({entry["DataName"]: entry for entry in entries})
            for data_type, entries in gamedata.items()
        }
        del gamedata

        print("Merging changes...")
        for data_type in {d for d in merged_entries if d in modded_entries}:
            util.dict_merge(
                merged_entries[data_type],
                modded_entries[data_type]["add"],
                shallow=True,
            )
            for entry in modded_entries[data_type]["del"]:
                try:
                    del merged_entries[data_type][entry]
                except KeyError:
                    continue

        merged_entries = Hash(
            {
                data_type: oead.byml.Array([value for _, value in entries.items()])
                for data_type, entries in merged_entries.items()
            }
        )
        print("Creating and injecting new gamedata.sarc...")
        new_gamedata = oead.SarcWriter(
            endian=oead.Endianness.Big
            if util.get_settings("wiiu")
            else oead.Endianness.Little
        )
        for data_type in merged_entries:
            num_files = ceil(len(merged_entries[data_type]) / 4096)
            for i in range(num_files):
                end_pos = (i + 1) * 4096
                if end_pos > len(merged_entries[data_type]):
                    end_pos = len(merged_entries[data_type])
                new_gamedata.files[f"/{data_type}_{i}.bgdata"] = oead.byml.to_binary(
                    Hash({data_type: merged_entries[data_type][i * 4096 : end_pos]}),
                    big_endian=util.get_settings("wiiu"),
                )
        new_gamedata_bytes = new_gamedata.write()[1]
        del new_gamedata
        util.inject_file_into_sarc(
            "GameData/gamedata.ssarc",
            util.compress(new_gamedata_bytes),
            "Pack/Bootup.pack",
            create_sarc=True,
        )
        (util.get_master_modpack_dir() / "logs").mkdir(parents=True, exist_ok=True)
        (util.get_master_modpack_dir() / "logs" / "gamedata.sarc").write_bytes(
            new_gamedata_bytes
        )

        print("Updating RSTB...")
        rstable.set_size(
            "GameData/gamedata.sarc",
            rstable.calculate_size("GameData/gamedata.sarc", new_gamedata_bytes),
        )
        del new_gamedata_bytes

        glog_path.parent.mkdir(parents=True, exist_ok=True)
        with glog_path.open("w", encoding="utf-8") as l_file:
            l_file.write(xxhash.xxh64_hexdigest(str(modded_entries)))

    def get_checkbox_options(self):
        return [("force", "Remerge game data even if no changes detected")]

    @staticmethod
    def is_bootup_injector():
        return True

    def get_bootup_injection(self):
        tmp_sarc = util.get_master_modpack_dir() / "logs" / "gamedata.sarc"
        if tmp_sarc.exists():
            return ("GameData/gamedata.ssarc", util.compress(tmp_sarc.read_bytes()))
        else:
            return


class SaveDataMerger(mergers.Merger):
    # pylint: disable=abstract-method
    NAME: str = "savedata"

    def __init__(self):
        super().__init__(
            "save data", "Merge changes to savedataformat.ssarc", "savedata.yml"
        )

    def generate_diff(self, mod_dir: Path, modded_files: List[Union[Path, str]]):
        if (
            f"{util.get_content_path()}/Pack/Bootup.pack//GameData/savedataformat.ssarc"
            in modded_files
        ):
            print("Logging changes to save data flags...")
            bootup_sarc = oead.Sarc(
                util.unyaz_if_needed(
                    (
                        mod_dir / util.get_content_path() / "Pack" / "Bootup.pack"
                    ).read_bytes()
                )
            )
            save_sarc = oead.Sarc(
                util.decompress(
                    bootup_sarc.get_file("GameData/savedataformat.ssarc").data
                )
            )
            diff = get_modded_savedata_entries(save_sarc)
            del save_sarc
            del bootup_sarc
            return diff
        else:
            return {}

    def log_diff(self, mod_dir: Path, diff_material):
        if isinstance(diff_material, List):
            diff_material = self.generate_diff(mod_dir, diff_material)
        if diff_material:
            (mod_dir / "logs" / self._log_name).write_text(
                oead.byml.to_text(diff_material), encoding="utf-8"
            )
            del diff_material

    def get_mod_diff(self, mod: BcmlMod):
        diffs = []
        if self.is_mod_logged(mod):
            diffs.append(
                oead.byml.from_text(
                    (mod.path / "logs" / self._log_name).read_text(encoding="utf-8")
                )
            )
        for opt in {d for d in (mod.path / "options").glob("*") if d.is_dir()}:
            if (opt / "logs" / self._log_name).exists():
                diffs.append(
                    oead.byml.from_text(
                        (opt / "logs" / self._log_name).read_text("utf-8")
                    )
                )
        return diffs

    def get_all_diffs(self):
        diffs = []
        for mod in util.get_installed_mods():
            diff = self.get_mod_diff(mod)
            if diff:
                diffs.extend(diff)
        return diffs

    def consolidate_diffs(self, diffs: list):
        if not diffs:
            return {}
        all_diffs = Hash({"add": oead.byml.Array(), "del": oead.byml.Array()})
        hashes = set()
        for diff in reversed(diffs):
            for entry in diff["add"]:
                if entry["HashValue"].v not in hashes:
                    all_diffs["add"].append(entry)
                hashes.add(entry["HashValue"].v)
            for entry in diff["del"]:
                if entry not in all_diffs["del"]:
                    all_diffs["del"].append(entry)
        del hashes
        return all_diffs

    @util.timed
    def perform_merge(self):
        force = self._options.get("force", False)
        slog_path = util.get_master_modpack_dir() / "logs" / "savedata.log"

        new_entries = self.consolidate_diffs(self.get_all_diffs())
        if not new_entries:
            print("No savedata merging necessary.")
            if slog_path.exists():
                slog_path.unlink()
            if (util.get_master_modpack_dir() / "logs" / "savedata.sarc").exists():
                (util.get_master_modpack_dir() / "logs" / "savedata.sarc").unlink()
            return
        if slog_path.exists() and not force:
            with slog_path.open("r") as l_file:
                if xxhash.xxh64_hexdigest(str(new_entries)) == l_file.read():
                    print("No savedata merging necessary.")
                    return

        savedata = get_stock_savedata()
        save_files = sorted(savedata.get_files(), key=lambda f: f.name)[0:-2]
        del_ids = {item.v for item in new_entries["del"]}

        print("Merging changes...")
        merged_entries = oead.byml.Array(
            sorted(
                {
                    entry["HashValue"].v: entry
                    for entry in [
                        *[
                            e
                            for file in save_files
                            for e in oead.byml.from_binary(file.data)["file_list"][1]
                        ],
                        *new_entries["add"],
                    ]
                    if entry["HashValue"].v not in del_ids
                }.values(),
                key=itemgetter("HashValue"),
            )
        )
        print("Creating and injecting new savedataformat.sarc...")
        new_savedata = oead.SarcWriter(
            endian=oead.Endianness.Big
            if util.get_settings("wiiu")
            else oead.Endianness.Little
        )
        num_files = ceil(len(merged_entries) / 8192)
        for i in range(num_files):
            end_pos = (i + 1) * 8192
            if end_pos > len(merged_entries):
                end_pos = len(merged_entries)
            data = oead.byml.to_binary(
                Hash(
                    {
                        "file_list": oead.byml.Array(
                            [
                                {
                                    "IsCommon": False,
                                    "IsCommonAtSameAccount": False,
                                    "IsSaveSecureCode": True,
                                    "file_name": "game_data.sav",
                                },
                                oead.byml.Array(merged_entries[i * 8192 : end_pos]),
                            ]
                        ),
                        "save_info": oead.byml.Array(
                            [
                                {
                                    "directory_num": oead.S32(8),
                                    "is_build_machine": True,
                                    "revision": oead.S32(18203),
                                }
                            ]
                        ),
                    }
                ),
                big_endian=util.get_settings("wiiu"),
            )
            new_savedata.files[f"/saveformat_{i}.bgsvdata"] = data

        new_savedata.files[f"/saveformat_{num_files}.bgsvdata"] = oead.Bytes(
            savedata.get_file("/saveformat_6.bgsvdata").data
        )
        new_savedata.files[f"/saveformat_{num_files + 1}.bgsvdata"] = oead.Bytes(
            savedata.get_file("/saveformat_7.bgsvdata").data
        )

        del savedata
        new_save_bytes = new_savedata.write()[1]
        del new_savedata
        util.inject_file_into_sarc(
            "GameData/savedataformat.ssarc",
            util.compress(new_save_bytes),
            "Pack/Bootup.pack",
            create_sarc=True,
        )
        (util.get_master_modpack_dir() / "logs").mkdir(parents=True, exist_ok=True)
        (
            (util.get_master_modpack_dir() / "logs" / "savedata.sarc").write_bytes(
                new_save_bytes
            )
        )

        print("Updating RSTB...")
        rstable.set_size(
            "GameData/savedataformat.sarc",
            rstable.calculate_size("GameData/savedataformat.sarc", new_save_bytes),
        )
        del new_save_bytes

        slog_path.parent.mkdir(parents=True, exist_ok=True)
        with slog_path.open("w", encoding="utf-8") as l_file:
            l_file.write(xxhash.xxh64_hexdigest(str(new_entries)))

    def get_checkbox_options(self):
        return [("force", "Remerge save data even if no changes detected")]

    @staticmethod
    def is_bootup_injector():
        return True

    def get_bootup_injection(self):
        tmp_sarc = util.get_master_modpack_dir() / "logs" / "savedata.sarc"
        if tmp_sarc.exists():
            return (
                "GameData/savedataformat.ssarc",
                util.compress(tmp_sarc.read_bytes()),
            )
        return None

    def get_mod_edit_info(self, mod: util.BcmlMod) -> set:
        diff = self.consolidate_diffs(self.get_mod_diff(mod))
        if not diff:
            return set()
        return {entry["DataName"] for entry in diff["add"]} | {
            int(item) for item in diff["del"]
        }
