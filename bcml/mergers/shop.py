"""Provides features for diffing and merging bshop AAMP files """
# Copyright 2019 Nicene Nerd <macadamiadaze@gmail.com>
# 2020 Ginger Avalanche <chodness@gmail.com>
# Licensed under GPLv3+
from functools import reduce, partial
from multiprocessing import Pool
from pathlib import Path
from typing import Union, List, ByteString, Optional, Dict, Any
from zlib import crc32

from oead.aamp import (
    ParameterIO,
    ParameterList,
    ParameterObject,
    Parameter,
    get_default_name_table,
)
from oead import Sarc, SarcWriter, InvalidDataError, FixedSafeString64
from bcml import util, mergers


HANDLES = {".bshop"}
SHOP_KEYS = ["ItemName", "ItemNum", "ItemAdjustPrice", "ItemLookGetFlg", "ItemAmount"]
name_table = get_default_name_table()


def is_string(p: Parameter) -> bool:
    return p.type() in [
        Parameter.Type.String32,
        Parameter.Type.String64,
        Parameter.Type.String256,
        Parameter.Type.StringRef,
    ]


def get_shop_diffs(file: str, tree: dict, tmp_dir: Path) -> Optional[dict]:
    try:
        ref_sarc = Sarc(util.unyaz_if_needed(util.get_game_file(file).read_bytes()))
    except (FileNotFoundError, InvalidDataError, ValueError, RuntimeError) as err:
        util.vprint(f"{file} ignored on stock side, cuz {err}")
        return None
    try:
        sarc = Sarc(util.unyaz_if_needed((tmp_dir / file).read_bytes()))
    except (FileNotFoundError, InvalidDataError, ValueError, RuntimeError):
        util.vprint(f"{file} corrupt, ignored")
        return None
    diffs = _get_diffs_from_sarc(sarc, ref_sarc, tree, file)
    del sarc
    del ref_sarc
    return diffs


def _get_diffs_from_sarc(sarc: Sarc, ref_sarc: Sarc, edits: dict, path: str) -> dict:
    diffs = {}
    for file, edits in edits.items():
        if edits:
            try:
                rsub_sarc = Sarc(util.unyaz_if_needed(ref_sarc.get_file(file).data))
            except (AttributeError, InvalidDataError, ValueError, RuntimeError) as err:
                util.vprint(f'Skipping "{path}//{file}", {err}')
                continue
            sub_sarc = Sarc(util.unyaz_if_needed(sarc.get_file(file).data))
            diffs.update(
                _get_diffs_from_sarc(sub_sarc, rsub_sarc, edits, path + "//" + file)
            )
            del sub_sarc
            del rsub_sarc
        else:
            full_path = f"{path}//{file}"
            try:
                ref_pio = ParameterIO.from_binary(ref_sarc.get_file(file).data)
            except AttributeError:
                continue
            try:
                pio = ParameterIO.from_binary(sarc.get_file(file).data)
            except AttributeError as err:
                raise ValueError(
                    f"Failed to read nested file:\n{path}//{file}"
                ) from err
            except (ValueError, RuntimeError, InvalidDataError) as err:
                raise ValueError(f"Failed to parse AAMP file:\n{path}//{file}")
            try:
                diffs.update({full_path: get_shop_diff(pio, ref_pio)})
            except KeyError as e:
                raise RuntimeError(
                    f"The shop file {path + '//' + file} appears to be missing a key: "
                    + str(e)
                ) from e
    return diffs


def make_shopdata(pio: ParameterIO) -> ParameterList:
    shopdata = ParameterList()
    tables: List[Parameter] = [
        str(t.v) for _, t in pio.objects["Header"].params.items() if is_string(t)
    ]
    if not tables:
        raise InvalidDataError("A shop file is invalid: has no tables")
    shopdata.objects["TableNames"] = ParameterObject()
    for table in tables:
        table_plist = ParameterList()
        shopdata.objects["TableNames"].params[table] = Parameter(
            FixedSafeString64(table)
        )
        table_hash = crc32(table.encode())
        items: Dict[str, List[int]] = {
            str(p.v): k.hash
            for k, p in pio.objects[table_hash].params.items()
            if is_string(p)
        }
        total_params = len(pio.objects[table_hash].params)
        for item in items.keys():
            item_no = int(
                name_table.get_name(items[item], total_params, table_hash).replace(
                    "ItemName", ""
                )
            )
            item_obj = ParameterObject()
            for shop_key in SHOP_KEYS:
                try:
                    item_obj.params[shop_key] = pio.objects[table_hash].params[
                        f"{shop_key}{item_no:03d}"
                    ]
                except KeyError:
                    raise KeyError(f"{shop_key}{item_no:03d}")
            table_plist.objects[item] = item_obj
        if table_plist.objects:
            shopdata.lists[table_hash] = table_plist
    return shopdata


def subtract_plists(plist: ParameterList, other_plist: ParameterList):
    for key in other_plist.lists.keys():
        if key in plist.lists:
            for key2 in other_plist.lists[key].objects.keys():
                if key2 in plist.lists[key].objects:
                    del plist.lists[key].objects[key2]
            if not plist.lists[key].lists and not plist.lists[key].objects:
                del plist.lists[key]
    # ignore wholesale table deletions, otherwise all hell breaks loose with old diffs
    # for key in other_plist.objects.keys():
    # if key in plist.lists:
    # del plist.lists[key]


def get_shop_diff(pio: ParameterIO, ref_pio: ParameterIO) -> ParameterList:
    def diff_plist(
        plist: Union[ParameterList, ParameterIO],
        ref_plist: Union[ParameterIO, ParameterList],
    ) -> ParameterList:
        diff = ParameterList()
        for key, sublist in plist.lists.items():
            if key not in ref_plist.lists:
                diff.lists[key] = sublist
            elif ref_plist.lists[key] != sublist:
                diff.lists[key] = diff_plist(sublist, ref_plist.lists[key])
        for key, obj in plist.objects.items():
            if key not in ref_plist.objects:
                diff.objects[key] = obj
            elif ref_plist.objects[key] != obj:
                diff.objects[key] = diff_pobj(obj, ref_plist.objects[key])
        return diff

    def diff_pobj(pobj: ParameterObject, ref_pobj: ParameterObject) -> ParameterObject:
        diff = ParameterObject()
        for param, value in pobj.params.items():
            if param not in ref_pobj.params or ref_pobj.params[param] != value:
                diff.params[param] = value
        return diff

    diff = ParameterList()
    shopdata = make_shopdata(pio)
    ref_shopdata = make_shopdata(ref_pio)
    adds = diff_plist(shopdata, ref_shopdata)
    if adds:
        diff.lists["Additions"] = adds
    rems = diff_plist(ref_shopdata, shopdata)
    if rems:
        subtract_plists(rems, adds)
        diff.lists["Removals"] = rems
    return diff


def merge_shopdata(pio: ParameterIO, plist: ParameterList):
    def make_bshop(plist: ParameterList) -> ParameterIO:
        bshop = ParameterIO()
        bshop.type = "xml"
        tables: List[str] = [
            str(t.v) for _, t in plist.objects["TableNames"].params.items()
        ]
        bshop.objects["Header"] = ParameterObject()
        bshop.objects["Header"].params["TableNum"] = Parameter(len(tables))
        for i, table in enumerate(tables, 1):
            table_hash = crc32(table.encode())
            bshop.objects["Header"].params[f"Table{i:02d}"] = Parameter(
                FixedSafeString64(table)
            )
            table_pobj = ParameterObject()
            table_pobj.params["ColumnNum"] = Parameter(
                len(plist.lists[table_hash].objects)
            )
            for j, item in enumerate(
                [item for _, item in plist.lists[table_hash].objects.items()], 1
            ):
                table_pobj.params[f"ItemSort{j:03d}"] = Parameter(j - 1)
                for shop_key in SHOP_KEYS:
                    table_pobj.params[f"{shop_key}{j:03d}"] = item.params[shop_key]
            if table_pobj.params:
                bshop.objects[table_hash] = table_pobj
        return bshop

    shopdata = make_shopdata(pio)
    subtract_plists(shopdata, plist.lists["Removals"])
    merge_plists(shopdata, plist.lists["Additions"])
    return make_bshop(shopdata)


def merge_plists(
    plist: Union[ParameterList, ParameterIO],
    other_plist: Union[ParameterList, ParameterIO],
    file_table: bool = False,
):
    def merge_pobj(pobj: ParameterObject, other_pobj: ParameterObject):
        for param, value in other_pobj.params.items():
            pobj.params[param] = value

    for key, sublist in other_plist.lists.items():
        if key in plist.lists:
            merge_plists(plist.lists[key], sublist)
        else:
            plist.lists[key] = sublist
    for key, obj in other_plist.objects.items():
        if key in plist.objects:
            if key != "Filenames" or not file_table:
                merge_pobj(plist.objects[key], obj)
            else:
                file_list = {f.v for i, f in plist.objects[key].params.items()} | {
                    f.v for i, f in other_plist.objects[key].params.items()
                }
                for i, file in enumerate({f for f in file_list if f}):
                    plist.objects[key].params[f"File{i}"] = file
        else:
            plist.objects[key] = obj


def merge_shop_files(file: str, tree: dict):
    try:
        base_file = util.get_game_file(file)
    except FileNotFoundError:
        util.vprint(f"Skipping {file}, not found in dump")
        return
    if (util.get_master_modpack_dir() / file).exists():
        base_file = util.get_master_modpack_dir() / file
    try:
        sarc = Sarc(util.unyaz_if_needed(base_file.read_bytes()))
    except (ValueError, InvalidDataError, RuntimeError):
        return
    new_data = _merge_in_sarc(sarc, tree)
    if base_file.suffix.startswith(".s") and base_file.suffix != ".ssarc":
        new_data = util.compress(new_data)
    (util.get_master_modpack_dir() / file).parent.mkdir(parents=True, exist_ok=True)
    (util.get_master_modpack_dir() / file).write_bytes(bytes(new_data))


def _merge_in_sarc(sarc: Sarc, edits: dict) -> ByteString:
    new_sarc = SarcWriter.from_sarc(sarc)
    for file, stuff in edits.items():
        if isinstance(stuff, dict):
            try:
                ofile = sarc.get_file(file)
                if ofile == None:
                    raise FileNotFoundError(
                        f"Could not find nested file {file} in SARC"
                    )
                sub_sarc = Sarc(util.unyaz_if_needed(ofile.data))
            except (
                InvalidDataError,
                ValueError,
                AttributeError,
                RuntimeError,
                FileNotFoundError,
            ):
                util.vprint(f"Couldn't merge into nested SARC {file}")
                continue
            nsub_bytes = _merge_in_sarc(sub_sarc, stuff)
            new_sarc.files[file] = (
                util.compress(nsub_bytes)
                if file[file.rindex(".") :].startswith(".s")
                else nsub_bytes
            )
        elif isinstance(stuff, ParameterList):
            try:
                ofile = sarc.get_file(file)
                if ofile == None:
                    raise FileNotFoundError(
                        f"Could not find nested file {file} in SARC"
                    )
                pio = ParameterIO.from_binary(ofile.data)
            except (
                AttributeError,
                ValueError,
                InvalidDataError,
                FileNotFoundError,
            ) as err:
                util.vprint(f"Couldn't open {file}: {err}")
                continue
            new_pio = merge_shopdata(pio, stuff)
            new_sarc.files[file] = new_pio.to_binary()
    return new_sarc.write()[1]


class ShopMerger(mergers.Merger):
    NAME: str = "shop"

    def __init__(self):
        super().__init__(
            "Shop merger",
            "Merges changes to shop files",
            "shop.aamp",
            options={},
        )

    def generate_diff(self, mod_dir: Path, modded_files: List[Union[str, Path]]):
        print("Detecting changes to shop files...")
        shops = {
            m
            for m in modded_files
            if isinstance(m, str) and m[m.rindex(".") :] in HANDLES and "Dummy" not in m
        }
        if not shops:
            return None

        consolidated: Dict[str, Any] = {}
        for shop in shops:
            util.dict_merge(
                consolidated,
                reduce(
                    lambda res, cur: {cur: res if res is not None else {}},  # type: ignore
                    reversed(shop.split("//")),
                    None,
                ),
            )
        this_pool = self._pool or Pool(maxtasksperchild=500)
        results = this_pool.starmap(
            partial(get_shop_diffs, tmp_dir=mod_dir), list(consolidated.items())
        )
        if not self._pool:
            this_pool.close()
            this_pool.join()
        del consolidated
        del shops

        diffs = ParameterIO()
        diffs.objects["Filenames"] = ParameterObject()
        i: int = 0
        for file, diff in sorted(
            (k, v) for r in [r for r in results if r is not None] for k, v in r.items()
        ):
            diffs.objects["Filenames"].params[file] = Parameter(file)
            diffs.lists[file] = diff
            i += 1
        return diffs

    def log_diff(self, mod_dir: Path, diff_material):
        if isinstance(diff_material, list):
            diff_material = self.generate_diff(mod_dir, diff_material)
        if diff_material:
            (mod_dir / "logs" / self._log_name).write_bytes(diff_material.to_binary())
        del diff_material

    def get_mod_diff(self, mod: util.BcmlMod):
        diff = None
        if self.is_mod_logged(mod):
            diff = ParameterIO.from_binary(
                (mod.path / "logs" / self._log_name).read_bytes()
            )
        for opt in {d for d in (mod.path / "options").glob("*") if d.is_dir()}:
            if (opt / "logs" / self._log_name).exists():
                if not diff:
                    diff = ParameterIO()
                merge_plists(
                    diff,
                    ParameterIO.from_binary(
                        (opt / "logs" / self._log_name).read_bytes()
                    ),
                    True,
                )
        return diff

    def get_all_diffs(self):
        diffs = ParameterIO()
        for mod in util.get_installed_mods():
            diff = self.get_mod_diff(mod)
            if diff:
                merge_plists(diffs, diff, True)
        return diffs if diffs.lists or diffs.objects else None

    def consolidate_diffs(self, diffs: ParameterIO):
        if not diffs:
            return None
        consolidated: Dict[str, Any] = {}
        for _, file in diffs.objects["Filenames"].params.items():
            try:
                util.dict_merge(
                    consolidated,
                    reduce(
                        lambda res, cur: {cur: res},
                        reversed(file.v.split("//")),
                        diffs.lists[file.v],
                    ),
                )
            except KeyError:
                util.vprint(diffs)
                raise Exception(f"{_}: {file} in diff lists: {file.v in diffs.lists}")
        return consolidated

    @util.timed
    def perform_merge(self):
        print("Loading deep merge logs...")
        diffs = self.consolidate_diffs(self.get_all_diffs())
        if not diffs:
            print("No deep merge needed")
            return
        new_shop_files_list = []
        for file_name in diffs:
            new_shop_files_list.append(file_name)
        shop_merge_log = util.get_master_modpack_dir() / "logs" / "shop.log"

        print("Performing shop merge...")
        pool = self._pool or Pool(maxtasksperchild=500)
        pool.starmap(merge_shop_files, diffs.items())

        if not self._pool:
            pool.close()
            pool.join()
        print("Finished deep merge")

    def get_checkbox_options(self):
        return []

    def get_mod_edit_info(self, mod: util.BcmlMod):
        diff = self.get_mod_diff(mod)
        if not diff:
            return set()
        return set(file.v for _, file in diff.objects["Filenames"].params.items())
