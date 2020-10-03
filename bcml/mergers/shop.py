"""Provides features for diffing and merging bshop and brecipe AAMP files """
# Copyright 2019 Nicene Nerd <macadamiadaze@gmail.com>
# 2020 Ginger Avalanche <chodness@gmail.com>
# Licensed under GPLv3+
import multiprocessing
import os
from functools import partial, reduce
from pathlib import Path
from typing import List, Union, Tuple

import oead
from oead.aamp import Parameter, ParameterIO, ParameterList, ParameterObject
from bcml import util, mergers


# pretty sure sbrecipe and sbshop arent a thing, but doesnt hurt to have them
EXT_FOLDERS = {
    ".bshop": "ShopData",
    ".sbshop": "ShopData",
}
EXT_PARAMS = {
    "bshop": [
        "ItemSort",
        "ItemName",
        "ItemNum",
        "ItemAdjustPrice",
        "ItemLookGetFlg",
        "ItemAmount",
    ],
}


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
    for _, table_list in pio.lists.items():
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


def get_named_pio(shop: ParameterIO, shop_type: str) -> ParameterIO:
    named_pio = ParameterIO()
    shop_keys = EXT_PARAMS[shop_type]

    for table_key, table_obj in shop.objects.items():
        if table_key.hash == oead.aamp.Name("Header").hash:
            tablenames = ParameterObject()
            named_pio.objects["TableNames"] = ParameterObject()
            tablenum = table_obj.params["TableNum"].v
            for idx in range(1, tablenum + 1):
                table_name = str(table_obj.params[f"Table{idx:02}"].v)
                tablenames.params[oead.aamp.Name(table_name)] = table_name
            named_pio.objects["TableNames"] = tablenames
            continue
        table_max = table_obj.params["ColumnNum"].v
        table_obj_new = ParameterList()
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
                    no_shop_key = curr_shop_key + entry_key
                    entry_value.params[curr_shop_key] = table_obj.params[no_shop_key]
            except KeyError:
                continue
            table_obj_new.objects[str(entry_value.params["ItemName"].v)] = entry_value
        named_pio.lists[table_key] = table_obj_new
    return named_pio


def nand_pio_into_plist(
    ref: Union[ParameterIO, ParameterList], mod: Union[ParameterIO, ParameterList],
) -> ParameterList:
    res_plist = ParameterList()
    for key, plist in mod.lists.items():
        if key not in ref.lists:
            res_plist.lists[key] = plist
        else:
            processed_list = nand_pio_into_plist(ref.lists[key], plist)
            if processed_list.lists or processed_list.objects:
                res_plist.lists[key] = processed_list
    for key, pobj in mod.objects.items():
        if key not in ref.objects:
            res_plist.objects[key] = pobj
        else:
            ref_pobj = ref.objects[key]
            res_plist.objects[key] = ref_pobj
            for param_key, param_value in pobj.params.items():
                if param_key not in ref_pobj.params:
                    continue  # new keys are garbage the game can't use, skip them
                if not param_value.v == ref_pobj.params[param_key].v:
                    res_plist.objects[key].params[param_key] = param_value
    return res_plist


def gen_diffs(ref: ParameterIO, mod: ParameterIO) -> ParameterList:
    diffs = ParameterList()
    tablenames_key = oead.aamp.Name("TableNames")
    # generate additions, modifications
    additions = nand_pio_into_plist(ref, mod)
    if len(additions.lists) != 0:
        additions.objects[tablenames_key] = ParameterObject()
        add_names = additions.objects[tablenames_key]
        mod_names = mod.objects[tablenames_key]
        for table_key in additions.lists.keys():
            add_names.params[table_key] = mod_names.params[table_key]
    diffs.lists["Additions"] = additions
    # generate deletions
    removals = nand_pio_into_plist(mod, ref)
    if len(removals.lists) != 0:
        removals.objects[tablenames_key] = ParameterObject()
        rem_names = removals.objects[tablenames_key]
        ref_names = ref.objects[tablenames_key]
        for table_key in removals.lists.keys():
            rem_names.params[table_key] = ref_names.params[table_key]
    diffs.lists["Removals"] = removals
    return diffs


def shop_merge(
    base: ParameterIO, ext: str, adds: ParameterList, rems: ParameterList
) -> ParameterIO:
    base_sorted = get_named_pio(base, ext)
    base_sorted = util.pio_subtract(base_sorted, rems)
    base_sorted = util.pio_merge(base_sorted, adds)

    if ext == "bshop":
        fix_itemsorts(base_sorted)

    merged = ParameterIO()
    merged.objects["Header"] = ParameterObject()
    merged.objects["Header"].params["TableNum"] = Parameter(len(base_sorted.lists))
    table_no = 1
    for table_key, table_list in base_sorted.lists.items():
        merged.objects["Header"].params[f"Table{table_no:02}"] = Parameter(
            base_sorted.objects["TableNames"].params[table_key].v
        )
        table_no += 1
        merged_table_obj = ParameterObject()
        merged_table_obj.params["ColumnNum"] = Parameter(len(table_list.objects))
        for _, item_obj in table_list.objects.items():
            if ext == "brecipe":
                entry_key = "%02d" % (item_obj.params["ItemSort"].v + 1)
            elif ext == "bshop":
                entry_key = "%03d" % (item_obj.params["ItemSort"].v + 1)
            else:
                raise KeyError(ext)
            for param_key in EXT_PARAMS[ext]:
                param_name = param_key + entry_key
                merged_table_obj.params[param_name] = item_obj.params[param_key]
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

    try:
        base_file = util.get_game_file(file, file.startswith(util.get_dlc_path()))
    except FileNotFoundError:
        return "", {}
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
        for file in [file for file in modded_files if Path(file).suffix in EXT_FOLDERS]:
            try:
                mod_bytes = util.get_nested_file_bytes(str(mod_dir) + "/" + str(file))
                nests = str(file).split("//", 1)
                try:
                    ref_path = str(util.get_game_file(Path(nests[0]))) + "//" + nests[1]
                except FileNotFoundError:
                    continue
                try:
                    ref_bytes = util.get_nested_file_bytes(ref_path)
                except AttributeError:
                    continue
                shop_type = str(file).split(".")[-1]

                mod_pio = get_named_pio(ParameterIO.from_binary(mod_bytes), shop_type)
                ref_pio = get_named_pio(ParameterIO.from_binary(ref_bytes), shop_type)

                file_names.params[oead.aamp.Name(file).hash] = Parameter(file)
                diffs.lists[file] = gen_diffs(ref_pio, mod_pio)
            except (KeyError, AttributeError) as err:
                raise err
        diffs.objects["Filenames"] = file_names
        return diffs

    def log_diff(
        self, mod_dir: Path, diff_material: Union[ParameterIO, List[Union[Path, str]]],
    ):
        """ Saves generated diffs to a log file """
        if isinstance(diff_material, list):
            diff_material = self.generate_diff(mod_dir, diff_material)
        if diff_material.objects["Filenames"].params:
            (mod_dir / "logs" / self._log_name).write_bytes(diff_material.to_binary())

    def get_mod_diff(self, mod: util.BcmlMod) -> ParameterIO:
        separate_diffs = []
        if self.is_mod_logged(mod):
            separate_diffs.append(
                ParameterIO.from_binary((mod.path / "logs" / self._log_name).read_bytes())
            )
        for opt in {d for d in (mod.path / "options").glob("*") if d.is_dir()}:
            if (opt / "logs" / self._log_name).exists():
                separate_diffs.append(
                    ParameterIO.from_binary((opt / "logs" / self._log_name).read_bytes())
                )
        return reduce(util.pio_merge, separate_diffs) if separate_diffs else None

    def get_all_diffs(self) -> list:
        diffs = []
        for mod in util.get_installed_mods():
            diff = self.get_mod_diff(mod)
            if diff:
                diffs.append(diff)
        return diffs

    def consolidate_diffs(self, diffs: list) -> dict:
        if not diffs:
            return {}
        all_diffs_pio: ParameterIO = reduce(util.pio_merge, diffs)
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
        diff = self.get_mod_diff(mod)
        if diff:
            for _, file_name in diff.objects["Filenames"].params.items():
                files.add(file_name)
        return files

    def perform_merge(self):
        """ Merges all installed shop mods """
        print("Loading and consolidating shop mods...")
        diffs = self.consolidate_diffs(self.get_all_diffs())
        new_shop_files_list = []
        for file_name in diffs:
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
        shop_merge_log.parent.mkdir(parents=True, exist_ok=True)
        with shop_merge_log.open("w", encoding="utf8") as s_log:
            for file_name in new_shop_files_list:
                print(file_name, file=s_log)

    def get_checkbox_options(self):
        return []

    def get_mod_edit_info(self, mod: util.BcmlMod) -> set:
        return self.get_mod_affected(mod)
