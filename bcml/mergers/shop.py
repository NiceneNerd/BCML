"""Provides features for diffing and merging bshop and brecipe AAMP files """
# Copyright 2019 Nicene Nerd <macadamiadaze@gmail.com>
# 2020 Ginger Avalanche <chodness@gmail.com>
# Licensed under GPLv3+
import multiprocessing
import os
from copy import deepcopy
from functools import partial, reduce
from pathlib import Path
from typing import List, Union, Tuple

import oead
from oead.aamp import Parameter, ParameterIO, ParameterList, ParameterObject
import sarc
from bcml import util, mergers
import zlib
import yaml


# pretty sure sbrecipe and sbshop arent a thing, but doesnt hurt to have them
EXT_FOLDERS = {
    ".brecipe": "Recipe",
    ".sbrecipe": "Recipe",
    ".bshop": "ShopData",
    ".sbshop": "ShopData",
}
EXT_PARAMS = {
    "brecipe": ["ItemName", "ItemNum"],
    "bshop": [
        "ItemSort",
        "ItemName",
        "ItemNum",
        "ItemAdjustPrice",
        "ItemLookGetFlg",
        "ItemAmount",
    ],
}
NAME_TABLE = oead.aamp.get_default_name_table()


def cache_merged_shop(file: str, data: bytes):
    out = Path(util.get_master_modpack_dir() / "logs" / "sh" / file)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)


def fix_itemsorts(pio: ParameterList) -> None:
    """
    Sorts items by their original ItemSort values.

    Since there is no real way of determining which mod
    added which item at a given ItemSort without keeping
    a metadata object that may or may not exist when we
    want it to, it doesn't attempt to. It just sorts them
    in the order it finds them.
    """
    for table_key, table_list in pio.lists.items():
        nested_sort: dict = {}
        max_sort = 0
        for item_key, item_obj in table_list.objects.items():
            current_sort = item_obj.params["ItemSort"].v
            if current_sort not in nested_sort.keys():
                nested_sort[current_sort] = []
            nested_sort[current_sort].append(item_key)
            max_sort = current_sort if current_sort > max_sort else max_sort
        current_sort = 0
        for idx in range(0, max_sort + 1):
            if idx in nested_sort.keys():
                for item_name in nested_sort[idx]:
                    table_list.objects[item_name].params["ItemSort"].v = current_sort
                    current_sort += 1


def get_stock_shop(actor_name: str, shop_user: str, file_ext: str) -> ParameterIO:
    pack_path = "Pack/TitleBG.pack//"
    actor_path = (
        f"Actor/{actor_name}.sbactorpack//{EXT_FOLDERS[file_ext]}/{shop_user}{file_ext}"
    )
    if util.get_game_file(pack_path + actor_path).exists():
        s_bytes = util.get_nested_file_bytes(
            str(util.get_game_file(pack_path + actor_path)), False
        )
    else:
        s_bytes = util.get_nested_file_bytes(str(util.get_game_file(actor_path)), False)

    return ParameterIO.from_binary(s_bytes)


def get_named_pio(shop: ParameterIO, shop_type: str) -> ParameterIO:
    named_pio = ParameterIO()
    shop_keys = EXT_PARAMS[shop_type]

    for table_key, table_list in shop.objects.items():
        if table_key.hash == oead.aamp.Name("Header").hash:
            continue
        table_max = table_list.params["ColumnNum"].v
        table_list_new = ParameterList()
        for idx in range(1, table_max + 1):
            if shop_type == "brecipe":
                entry_key = "%02d" % idx
            elif shop_type == "bshop":
                entry_key = "%03d" % idx
            else:
                raise KeyError(shop_type)
            entry_value = ParameterObject()
            try:
                for curr_shop_key in shop_keys:
                    entry_value.params[curr_shop_key] = table_list.params[
                        curr_shop_key + entry_key
                    ]
            except KeyError:
                continue
            table_list_new.objects[str(entry_value.params["ItemName"].v)] = entry_value
        named_pio.lists[table_key] = table_list_new
    return named_pio


def pio_deepcopy(ref: ParameterIO) -> ParameterIO:
    return ParameterIO.from_binary(ParameterIO.to_binary(ref))


def pio_merge(
    ref: Union[ParameterIO, ParameterList], mod: Union[ParameterIO, ParameterList]
) -> ParameterIO:
    if isinstance(ref, ParameterIO):
        merged = pio_deepcopy(ref)
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
) -> None:
    for key, plist in mod.lists.items():
        if key in ref.lists:
            pio_subtract(ref.lists[key], plist)
        if len(ref.lists[key].objects) == 0 and len(ref.lists[key].lists) == 0:
            del ref.lists[key]
    for key, pobj in mod.objects.items():
        if key in ref.objects:
            ref_pobj = ref.objects[key]
            for pkey, param in pobj.params.items():
                if pkey in ref_pobj.params:
                    del ref_pobj.params[pkey]
            if len(ref_pobj.params) == 0:
                del ref.objects[key]


def gen_diffs(ref: ParameterIO, mod: ParameterIO) -> ParameterList:
    diffs = ParameterList()
    additions = ParameterList()
    # generate additions, modifications
    for table_key, table_list in mod.lists.items():
        if table_key not in ref.lists:
            additions.lists[table_key] = table_list
        else:
            mod_table_list = table_list
            ref_table_list = ref.lists[table_key]
            for item_key, item_obj in mod_table_list.objects.items():
                if item_key not in ref_table_list.objects:
                    if table_key not in additions.lists:
                        additions.lists[table_key] = ParameterList()
                    add_table_list = additions.lists[table_key]
                    add_table_list.objects[item_key] = item_obj
                else:
                    mod_item_obj = item_obj
                    ref_item_obj = ref_table_list.objects[item_key]
                    for param_key, param_value in mod_item_obj.params.items():
                        if param_key not in ref_item_obj.params:
                            continue  # new keys are garbage the game can't use, skip them
                        if not param_value.v == ref_item_obj.params[param_key].v:
                            if table_key not in additions.lists:
                                additions.lists[table_key] = ParameterList()
                            add_table_list = additions.lists[table_key]
                            if item_key not in add_table_list.objects:
                                add_table_list.objects[item_key] = ParameterObject()
                            add_item_obj = add_table_list.objects[item_key]
                            add_item_obj.params[param_key] = param_value
    diffs.lists["Additions"] = additions
    # generate deletions
    removals = ParameterList()
    for table_key, table_list in ref.lists.items():
        if table_key not in mod.lists:
            removals.lists[table_key] = table_list
        else:
            ref_table_list = table_list
            mod_table_list = mod.lists[table_key]
            for item_key, item_obj in ref_table_list.objects.items():
                if item_key not in mod_table_list.objects:
                    if table_key not in removals.lists:
                        removals.lists[table_key] = ParameterList()
                    rem_table_list = removals.lists[table_key]
                    rem_table_list.objects[item_key] = item_obj
                # dont bother with parameters, they're either there or the mod itself is broken
    diffs.lists["Removals"] = removals
    return diffs


def shop_merge(
    base: ParameterIO, ext: str, adds: ParameterList, rems: ParameterList
) -> ParameterIO:
    base_sorted = get_named_pio(base, ext)
    base_sorted = pio_merge(base_sorted, adds)
    pio_subtract(base_sorted, rems)

    if ext == "bshop":
        fix_itemsorts(base_sorted)

    for key in EXT_PARAMS[ext]:
        NAME_TABLE.add_name(key)

    merged = ParameterIO()
    merged_header = ParameterObject()
    merged.objects["Header"] = merged_header
    merged_header.params["TableNum"] = Parameter(len(base_sorted.lists))
    table_no = 1
    for table_key, table_list in base_sorted.lists.items():
        merged_header.params[f"Table{table_no:02}"] = Parameter(
            NAME_TABLE.get_name(table_key.hash, 0, 0)
        )
        table_no += 1
        merged_table_obj = ParameterObject()
        merged_table_obj.params["ColumnNum"] = Parameter(len(table_list.objects))
        for item_key, item_obj in table_list.objects.items():
            if ext == "brecipe":
                entry_key = "%02d" % (item_obj.params["ItemSort"].v + 1)
            elif ext == "bshop":
                entry_key = "%03d" % (item_obj.params["ItemSort"].v + 1)
            else:
                raise KeyError(ext)
            for param_hash, param_value in item_obj.params.items():
                param_key = NAME_TABLE.get_name(param_hash.hash, 0, 0)
                merged_table_obj.params[param_key + entry_key] = param_value
        merged.objects[table_key] = merged_table_obj
    return merged


def nested_patch(pack: oead.Sarc, nest: dict) -> Tuple[oead.SarcWriter, dict]:
    new_sarc: oead.SarcWriter = oead.SarcWriter.from_sarc(pack)
    failures: dict = {}

    for file, stuff in nest.items():
        file_bytes = pack.get_file(file).data
        yazd = file_bytes[0:4] == b"Yaz0"
        file_bytes = util.decompress(file_bytes) if yazd else file_bytes

        if isinstance(stuff, dict):
            sub_sarc = oead.Sarc(file_bytes)
            new_sub_sarc, sub_failures = nested_patch(sub_sarc, stuff)
            for failure in sub_failures:
                failure[file + "//" + failure] = sub_failures[failure]
            del sub_sarc
            new_bytes = bytes(new_sub_sarc.write()[1])
            new_sarc.files[file] = new_bytes if not yazd else util.compress(new_bytes)

        elif isinstance(stuff, ParameterList):
            try:
                if file_bytes[0:4] == b"AAMP":
                    aamp_contents = ParameterIO.from_binary(file_bytes)
                    try:
                        file_ext = os.path.splitext(file)[1]
                        aamp_contents = shop_merge(
                            aamp_contents,
                            file_ext.replace(".", ""),
                            stuff.lists["Additions"],
                            stuff.lists["Removals"],
                        )
                        aamp_bytes = ParameterIO.to_binary(aamp_contents)
                    except:  # pylint: disable=bare-except
                        raise RuntimeError(f"AAMP file {file} could be merged.")
                    del aamp_contents
                    new_bytes = aamp_bytes if not yazd else util.compress(aamp_bytes)
                    cache_merged_shop(file, new_bytes)
                else:
                    raise ValueError("Wait, what the heck, this isn't an AAMP file?!")
            except ValueError:
                new_bytes = pack.get_file(file).data
                print(f"Deep merging {file} failed. No changes were made.")

            new_sarc.files[file] = oead.Bytes(new_bytes)
    return new_sarc, failures


def threaded_merge(item) -> Tuple[str, dict]:
    """Deep merges an individual file, suitable for multiprocessing"""
    file, stuff = item
    failures = {}

    base_file = util.get_game_file(file, file.startswith(util.get_dlc_path()))
    if (util.get_master_modpack_dir() / file).exists():
        base_file = util.get_master_modpack_dir() / file
    file_ext = os.path.splitext(file)[1]
    if file_ext in util.SARC_EXTS and (util.get_master_modpack_dir() / file).exists():
        base_file = util.get_master_modpack_dir() / file
    file_bytes = base_file.read_bytes()
    yazd = file_bytes[0:4] == b"Yaz0"
    file_bytes = file_bytes if not yazd else util.decompress(file_bytes)
    magic = file_bytes[0:4]

    if magic == b"SARC":
        new_sarc, sub_failures = nested_patch(oead.Sarc(file_bytes), stuff)
        del file_bytes
        new_bytes = bytes(new_sarc.write()[1])
        for failure, contents in sub_failures.items():
            print(f"Some patches to {failure} failed to apply.")
            failures[failure] = contents
    elif magic == b"AAMP":
        try:
            aamp_contents = ParameterIO.from_binary(file_bytes)
            try:
                aamp_contents = shop_merge(
                    aamp_contents,
                    file_ext.replace(".", ""),
                    stuff.lists["Additions"],
                    stuff.lists["Removals"],
                )
                aamp_bytes = ParameterIO.to_binary(aamp_contents)
            except:  # pylint: disable=bare-except
                raise RuntimeError(f"AAMP file {file} could be merged.")
            del aamp_contents
            new_bytes = aamp_bytes if not yazd else util.compress(aamp_bytes)
        except ValueError:
            new_bytes = file_bytes
            del file_bytes
            print(f"Deep merging file {file} failed. No changes were made.")
    else:
        raise ValueError(f"{file} is not a SARC or AAMP file.")

    new_bytes = new_bytes if not yazd else util.compress(new_bytes)
    output_file = util.get_master_modpack_dir() / file
    if base_file == output_file:
        output_file.unlink()
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_bytes(new_bytes)
    del new_bytes
    if magic == b"SARC":
        util.vprint(f"Finished patching files inside {file}")
    else:
        util.vprint(f"Finished patching {file}")
    return util.get_canon_name(file), failures


class ShopMerger(mergers.Merger):
    NAME: str = "shop"

    def __init__(self):
        super().__init__(
            "shop merge", "Merges changes to shop and recipe files", "shop.aamp", {}
        )

    def generate_diff(
        self, mod_dir: Path, modded_files: List[Union[Path, str]]
    ) -> ParameterIO:
        print("Logging changes to shop files...")
        diffs = ParameterIO()
        file_names = ParameterObject()
        for file in [
            file for file in modded_files if Path(file).suffix in EXT_FOLDERS.keys()
        ]:
            try:
                mod_bytes = util.get_nested_file_bytes(str(mod_dir) + "/" + str(file))
                nests = str(file).split("//", 1)
                ref_path = str(util.get_game_file(Path(nests[0]))) + "//" + nests[1]
                ref_bytes = util.get_nested_file_bytes(ref_path)
                shop_type = str(file).split(".")[-1]

                mod_pio = get_named_pio(ParameterIO.from_binary(mod_bytes), shop_type)
                ref_pio = get_named_pio(ParameterIO.from_binary(ref_bytes), shop_type)

                file_names.params[oead.aamp.Name(file).hash] = Parameter(file)
                diffs.lists[file] = gen_diffs(ref_pio, mod_pio)
            except (FileNotFoundError, KeyError, TypeError):
                continue
        diffs.objects["Filenames"] = file_names
        return diffs

    def log_diff(
        self, mod_dir: Path, diff_material: Union[ParameterIO, List[Union[Path, str]]],
    ):
        """ Saves generated diffs to a log file """
        if isinstance(diff_material, List):
            diff_material = self.generate_diff(mod_dir, diff_material)
        if diff_material:
            (mod_dir / "logs" / self._log_name).write_bytes(diff_material.to_binary())

    def get_mod_diff(self, mod: util.BcmlMod) -> ParameterIO:
        separate_diffs = []
        if self.is_mod_logged(mod):
            separate_diffs.append(
                ParameterIO.from_binary(
                    (mod.path / "logs" / self._log_name).read_bytes()
                )
            )
        for opt in {d for d in (mod.path / "options").glob("*") if d.is_dir()}:
            if (opt / "logs" / self._log_name).exists():
                separate_diffs.append(
                    ParameterIO.from_binary(
                        (opt / "logs" / self._log_name).read_bytes()
                    )
                )
        return reduce(pio_merge, separate_diffs)

    def get_all_diffs(self) -> list:
        diffs = []
        for mod in util.get_installed_mods():
            diffs.append(self.get_mod_diff(mod))
        return diffs

    def consolidate_diffs(self, diffs: list) -> dict:
        all_diffs_pio: ParameterIO = reduce(pio_merge, diffs)
        all_diffs: dict = {}
        for file_key, file_list in all_diffs_pio.lists.items():
            all_diffs[file_key] = file_list
        consolidated_diffs: dict = {}
        for file_key, diff_list in all_diffs.items():
            file_name = all_diffs_pio.objects["Filenames"].params[file_key].v
            nest = reduce(
                lambda res, cur: {cur: res}, reversed(file_name.split("//")), diff_list
            )
            util.dict_merge(consolidated_diffs, nest)
        return consolidated_diffs

    @staticmethod
    def can_partial_remerge() -> bool:
        return True

    def get_mod_affected(self, mod: util.BcmlMod) -> set:
        files = set()
        for _, file_name in self.get_mod_diff(mod).objects["Filenames"].params.items():
            files.add(file_name)
        return files

    def perform_merge(self):
        """ Merges all installed shop mods """
        print("Loading and consolidating shop mods...")
        diffs = self.consolidate_diffs(self.get_all_diffs())
        new_shop_files_list = []
        for file_name in diffs.keys():
            new_shop_files_list.append(file_name)
        shop_merge_log = util.get_master_modpack_dir() / "logs" / "shop.log"

        print("Performing shop merge...")
        if not self._pool:
            multiprocessing.set_start_method("spawn", True)
        pool = self._pool or multiprocessing.Pool()
        pool.map(partial(threaded_merge), diffs.items())
        if not self._pool:
            pool.close()
            pool.join()

        print("Saving shop merge log...")
        with shop_merge_log.open("w") as s_log:
            for file_name in new_shop_files_list:
                print(file_name, file=s_log)

    def get_checkbox_options(self):
        return []

    def get_mod_edit_info(self, mod: util.BcmlMod) -> set:
        return self.get_mod_affected(mod)
