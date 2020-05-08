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
import sarc
from bcml import util, mergers
import zlib
import yaml


#pretty sure sbrecipe and sbshop arent a thing, but doesnt hurt to have them
EXT_FOLDERS = {'.brecipe':'Recipe', '.sbrecipe':'Recipe', '.bshop':'ShopData', '.sbshop':'ShopData'}
EXT_PARAMS = {'brecipe':['ItemName', 'ItemNum'], 'bshop':['ItemSort', 'ItemName', 'ItemNum', 'ItemAdjustPrice', 'ItemLookGetFlg', 'ItemAmount']}
NAME_TABLE = oead.aamp.get_default_name_table()


def cache_merged_shop(file: str, data: bytes):
    out = Path(util.get_master_modpack_dir() / 'logs' / 'sh' / file)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)


def fix_itemsorts(pio: oead.aamp.ParameterList) -> None:
    """
    Sorts items by their original ItemSort values.

    Since there is no real way of determining which mod
    added which item at a given ItemSort without keeping
    a metadata object that may or may not exist when we
    want it to, it doesn't attempt to. It just sorts them
    in the order it finds them.
    """
    for table_key, table_value in pio.lists.items():
        nested_sort: dict = {}
        max_sort = 0
        for item_key, item_obj in table_value.objects.items():
            current_sort = item_obj.params['ItemSort'].v
            if current_sort not in nested_sort.keys():
                nested_sort[current_sort] = []
            nested_sort[current_sort].append(item_key)
            max_sort = current_sort if current_sort > max_sort else max_sort
        current_sort = 0
        for idx in range(0, max_sort+1):
            if idx in nested_sort.keys():
                for item_name in nested_sort[idx]:
                    table_value.objects[item_name].params['ItemSort'].v = current_sort
                    current_sort += 1


def get_stock_shop(actor_name: str, shop_user: str, file_ext: str) -> oead.aamp.ParameterIO:
    pack_path = 'Pack/TitleBG.pack//'
    actor_path = f'Actor/{actor_name}.sbactorpack//{EXT_FOLDERS[file_ext]}/{shop_user}{file_ext}'
    if util.get_game_file(pack_path + actor_path).exists():
        s_bytes = util.get_nested_file_bytes(str(util.get_game_file(pack_path + actor_path)), False)
    else:
        s_bytes = util.get_nested_file_bytes(str(util.get_game_file(actor_path)), False)
    
    return oead.aamp.ParameterIO.from_binary(s_bytes)


def get_named_pio(shop: oead.aamp.ParameterIO, shop_type: str) -> oead.aamp.ParameterIO:
    shop_return = oead.aamp.ParameterIO()
    shop_keys = EXT_PARAMS[shop_type]
    for key in shop_keys:
        NAME_TABLE.add_name(key)

    for table_key, table_value in shop.objects.items():
        if table_key.hash == oead.aamp.Name('Header').hash:
            for idx in range(1, table_value.params['TableNum'].v + 1):
                NAME_TABLE.add_name(str(table_value.params[f'Table{idx:02}'].v))
            continue
        table_max = table_value.params['ColumnNum'].v
        table_value_storage = oead.aamp.ParameterList()
        for idx in range(1, table_max + 1):
            if shop_type == 'brecipe':
                entry_key = '%02d' % idx
            elif shop_type == 'bshop':
                entry_key = '%03d' % idx
            else:
                raise KeyError(shop_type)
            entry_value = oead.aamp.ParameterObject()
            try:
                for curr_shop_key in shop_keys:
                    entry_value.params[curr_shop_key] = table_value.params[curr_shop_key + entry_key]
            except KeyError:
                continue
            table_value_storage.objects[str(entry_value.params['ItemName'].v)] = entry_value
        shop_return.lists[table_key] = table_value_storage
    return shop_return


def gen_diffs(ref: oead.aamp.ParameterIO, mod: oead.aamp.ParameterIO) -> oead.aamp.ParameterList:
    diffs = oead.aamp.ParameterList()
    additions = oead.aamp.ParameterList()
    #generate additions, modifications
    for table_key, table_list in mod.lists.items():
        if table_key not in ref.lists:
            additions.lists[table_key] = table_list
        else:
            for item_key, item_obj in mod.lists[table_key].objects.items():
                if item_key not in ref.lists[table_key].objects:
                    try:
                        additions.lists[table_key].objects[item_key] = item_obj
                    except KeyError:
                        additions.lists[table_key] = oead.aamp.ParameterList()
                        additions.lists[table_key].objects[item_key] = item_obj
                else:
                    for param_key, param_value in mod.lists[table_key].objects[item_key].params.items():
                        if param_key not in ref.lists[table_key].objects[item_key].params:
                            continue #new keys are garbage the game can't use, skip them
                        if not param_value.v == ref.lists[table_key].objects[item_key].params[param_key].v:
                            try:
                                additions.lists[table_key].objects[item_key].params[param_key] = param_value
                            except KeyError:
                                additions.lists[table_key].objects[item_key] = oead.aamp.ParameterObject()
                                additions.lists[table_key].objects[item_key].params[param_key] = param_value
    diffs.lists['Additions'] = additions
    #generate deletions
    removals = oead.aamp.ParameterList()
    for table_key, table_list in ref.lists.items():
        if table_key not in mod.lists:
            removals.lists[table_key] = table_list
        else:
            for item_key, item_obj in ref.lists[table_key].objects.items():
                if item_key not in mod.lists[table_key].objects:
                    try:
                        removals.lists[table_key].objects[item_key] = item_obj
                    except KeyError:
                        removals.lists[table_key] = oead.aamp.ParameterList()
                        removals.lists[table_key].objects[item_key] = item_obj
                #dont bother with parameters, they're either there or the mod itself is broken
    diffs.lists['Removals'] = removals
    return diffs


def shop_merge(base: oead.aamp.ParameterIO, ext: str,
                adds: oead.aamp.ParameterList, rems: oead.aamp.ParameterList) -> oead.aamp.ParameterIO:
    base_sorted = get_named_pio(base, ext)
    for table_key, table_list in adds.lists.items():
        if table_key not in base_sorted.lists.keys():
            base_sorted.lists[table_key] = table_list
        else:
            for item_key, item_obj in table_list.objects.items():
                if item_key not in base_sorted.lists[table_key].objects.keys():
                    base_sorted.lists[table_key].objects[item_key] = item_obj
                else:
                    for param_key, param_value in item_obj.params.items():
                        base_sorted.lists[table_key].objects[item_key].params[param_key] = param_value
    for table_key, table_list in rems.lists.items():
        if table_key in base_sorted.lists.keys():
            for item_key in table_list.objects.keys():
                del base_sorted.lists[table_key].objects[item_key]
            if len(base_sorted.lists[table_key].objects) == 0:
                del base_sorted.lists[table_key]
    if ext == 'bshop':
        fix_itemsorts(base_sorted)
    merged = oead.aamp.ParameterIO()
    merged.objects['Header'] = oead.aamp.ParameterObject()
    merged.objects['Header'].params['TableNum'] = oead.aamp.Parameter(len(base_sorted.lists))
    table_no = 1
    for table_key, table_list in base_sorted.lists.items():
        merged.objects['Header'].params[f'Table{table_no:02}'] = oead.aamp.Parameter(NAME_TABLE.get_name(table_key.hash,0,0))
        table_no += 1
        merged.objects[table_key] = oead.aamp.ParameterObject()
        merged.objects[table_key].params['ColumnNum'] = oead.aamp.Parameter(len(table_list.objects))
        for item_key, item_obj in table_list.objects.items():
            if ext == 'brecipe':
                entry_key = '%02d' % (item_obj.params['ItemSort'].v + 1)
            elif ext == 'bshop':
                entry_key = '%03d' % (item_obj.params['ItemSort'].v + 1)
            else:
                raise KeyError(ext)
            for param_key, param_value in item_obj.params.items():
                merged.objects[table_key].params[NAME_TABLE.get_name(param_key.hash,0,0) + entry_key] = param_value
    return merged


def nested_patch(pack: oead.Sarc, nest: dict) -> Tuple[oead.SarcWriter, dict]:
    new_sarc: oead.SarcWriter = oead.SarcWriter.from_sarc(pack)
    failures: dict = {}

    for file, stuff in nest.items():
        file_bytes = pack.get_file(file).data
        yazd = file_bytes[0:4] == b'Yaz0'
        file_bytes = util.decompress(file_bytes) if yazd else file_bytes

        if isinstance(stuff, dict):
            sub_sarc = oead.Sarc(file_bytes)
            new_sub_sarc, sub_failures = nested_patch(sub_sarc, stuff)
            for failure in sub_failures:
                failure[file + '//' + failure] = sub_failures[failure]
            del sub_sarc
            new_bytes = bytes(new_sub_sarc.write()[1])
            new_sarc.files[file] = new_bytes if not yazd else util.compress(new_bytes)

        elif isinstance(stuff, oead.aamp.ParameterList):
            try:
                if file_bytes[0:4] == b'AAMP':
                    aamp_contents = oead.aamp.ParameterIO.from_binary(file_bytes)
                    try:
                        file_ext = os.path.splitext(file)[1]
                        aamp_contents = shop_merge(
                            aamp_contents,
                            file_ext.replace('.',''),
                            stuff.lists['Additions'],
                            stuff.lists['Removals']
                        )
                        aamp_bytes = oead.aamp.ParameterIO.to_binary(aamp_contents)
                    except:  # pylint: disable=bare-except
                        raise RuntimeError(f'AAMP file {file} could be merged.')
                    del aamp_contents
                    new_bytes = aamp_bytes if not yazd else util.compress(aamp_bytes)
                    cache_merged_shop(file, new_bytes)
                else:
                    raise ValueError('Wait, what the heck, this isn\'t an AAMP file?!')
            except ValueError:
                new_bytes = pack.get_file(file).data
                print(f'Deep merging {file} failed. No changes were made.')

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
        base_file = (util.get_master_modpack_dir() / file)
    file_bytes = base_file.read_bytes()
    yazd = file_bytes[0:4] == b'Yaz0'
    file_bytes = file_bytes if not yazd else util.decompress(file_bytes)
    magic = file_bytes[0:4]

    if magic == b'SARC':
        new_sarc, sub_failures = nested_patch(oead.Sarc(file_bytes), stuff)
        del file_bytes
        new_bytes = bytes(new_sarc.write()[1])
        for failure, contents in sub_failures.items():
            print(f'Some patches to {failure} failed to apply.')
            failures[failure] = contents
    elif magic == b'AAMP':
        try:
            aamp_contents = oead.aamp.ParameterIO.from_binary(file_bytes)
            try:
                aamp_contents = shop_merge(
                    aamp_contents,
                    file_ext.replace('.',''),
                    stuff.lists['Additions'],
                    stuff.lists['Removals']
                )
                aamp_bytes = oead.aamp.ParameterIO.to_binary(aamp_contents)
            except:  # pylint: disable=bare-except
                raise RuntimeError(f'AAMP file {file} could be merged.')
            del aamp_contents
            new_bytes = aamp_bytes if not yazd else util.compress(aamp_bytes)
        except ValueError:
            new_bytes = file_bytes
            del file_bytes
            print(f'Deep merging file {file} failed. No changes were made.')
    else:
        raise ValueError(f'{file} is not a SARC or AAMP file.')

    new_bytes = new_bytes if not yazd else util.compress(new_bytes)
    output_file = (util.get_master_modpack_dir() / file)
    if base_file == output_file:
        output_file.unlink()
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_bytes(new_bytes)
    del new_bytes
    if magic == b'SARC':
        util.vprint(f'Finished patching files inside {file}')
    else:
        util.vprint(f'Finished patching {file}')
    return util.get_canon_name(file), failures


class ShopMerger(mergers.Merger):
    NAME: str = 'shop'

    def __init__(self):
        super().__init__('shop merge', 'Merges changes to shop and recipe files',
                         'shop.yml', {})

    def generate_diff(self, mod_dir: Path, modded_files: List[Union[Path, str]]) -> oead.aamp.ParameterIO:
        print('Logging changes to shop files...')
        diffs = oead.aamp.ParameterIO()
        NAME_TABLE.add_name('Additions')
        NAME_TABLE.add_name('Removals')
        for file in [file for file in modded_files if Path(file).suffix in EXT_FOLDERS.keys()]:
            try:
                mod_bytes = util.get_nested_file_bytes(str(mod_dir) + '/' + str(file))
                nests = str(file).split('//', 1)
                ref_path = str(util.get_game_file(Path(nests[0]))) + '//' + nests[1]
                ref_bytes = util.get_nested_file_bytes(ref_path)
                shop_type = str(file).split('.')[-1]
                    
                mod_pio = get_named_pio(oead.aamp.ParameterIO.from_binary(mod_bytes), shop_type)
                ref_pio = get_named_pio(oead.aamp.ParameterIO.from_binary(ref_bytes), shop_type)

                NAME_TABLE.add_name(file)
                diffs.lists[file] = gen_diffs(ref_pio, mod_pio)
            except (FileNotFoundError, KeyError, TypeError):
                continue
        return diffs

    def log_diff(self, mod_dir: Path, diff_material: Union[oead.aamp.ParameterIO, List[Union[Path, str]]]):
        """ Saves generated diffs to a log file """
        if isinstance(diff_material, List):
            diff_material = self.generate_diff(mod_dir, diff_material)
        if diff_material:
            (mod_dir / 'logs' / self._log_name).write_text(
                diff_material.to_text(),
                encoding='utf-8'
            )

    def get_mod_diff(self, mod: util.BcmlMod) -> oead.aamp.ParameterIO:
        separate_diffs = []
        if self.is_mod_logged(mod):
            separate_diffs.append(
                oead.aamp.ParameterIO.from_text(
                    (mod.path / 'logs' / self._log_name).read_text(encoding='utf-8')
                )
            )
        for opt in {d for d in (mod.path / 'options').glob('*') if d.is_dir()}:
            if (opt / 'logs' / self._log_name).exists():
                separate_diffs.append(
                    oead.aamp.ParameterIO.from_text(
                        (opt / 'logs' / self._log_name).read_text(encoding='utf-8')
                    )
                )
        return self.consolidate_diffs(separate_diffs)

    def get_all_diffs(self) -> list:
        diffs = []
        for mod in util.get_installed_mods():
            diffs.append(self.get_mod_diff(mod))
        return diffs

    def consolidate_diffs(self, diffs: list) -> dict:
        all_diffs: dict = {}
        for diffs_pio in diffs:
            for file_key, file_list in diffs_pio.lists.items():
                if file_key not in all_diffs.keys():
                    all_diffs[file_key] = file_list
                else:
                    for addrem_key, addrem_list in file_list.lists.items():
                        if addrem_key not in all_diffs[file_key].lists.keys():
                            all_diffs[file_key].lists[addrem_key] = addrem_list
                        else:
                            for table_key, table_list in addrem_list.lists.items():
                                if table_key not in all_diffs[file_key].lists[addrem_key].lists.keys():
                                    all_diffs[file_key].lists[addrem_key].lists[table_key] = table_list
                                else:
                                    for item_key, item_obj in table_list.objects.items():
                                        if item_key not in all_diffs[file_key].lists[addrem_key].lists[table_key].objects.keys():
                                            all_diffs[file_key].lists[addrem_key].lists[table_key].objects[item_key] = item_obj
                                        else:
                                            for param, value in item_obj.items():
                                                all_diffs[file_key].lists[addrem_key].lists[table_key].objects[item_key].params[param] = value
                if 'Additions' in all_diffs[file_key].lists.keys() and 'Removals' in all_diffs[file_key].lists.keys():
                    for rem_table_key in all_diffs[file_key].lists['Removals'].lists.keys():
                        if rem_table_key in all_diffs[file_key].lists['Additions'].lists.keys():
                            for rem_obj_key in all_diffs[file_key].lists['Removals'].lists[rem_table_key].objects.keys():
                                if rem_obj_key in all_diffs[file_key].lists['Additions'].lists[rem_table_key].objects.keys():
                                    #additions override deletions
                                    del all_diffs[file_key].lists['Removals'].lists[rem_table_key].objects[rem_obj_key]
                            if len(all_diffs[file_key].lists['Removals'].lists[rem_table_key].objects) == 0:
                                #remove empty removal tables
                                del all_diffs[file_key].lists['Removals'].lists[rem_table_key]
        consolidated_diffs: dict = {}
        for file_key, diff_list in all_diffs.items():
            file_name = NAME_TABLE.get_name(file_key.hash,0,0)
            nest = reduce(lambda res, cur: {cur: res}, reversed(file_name.split('//')), diff_list)
            util.dict_merge(consolidated_diffs, nest)
        return consolidated_diffs

    @staticmethod
    def can_partial_remerge() -> bool:
        return True

    def get_mod_affected(self, mod: util.BcmlMod) -> set:
        files = set()
        for diff_pio in self.get_mod_diff(mod):
            files |= set(diff_pio.lists.keys())
        return files

    def perform_merge(self):
        """ Merges all installed shop mods """
        print('Loading and consolidating shop mods...')
        diffs = self.consolidate_diffs(self.get_all_diffs())
        new_shop_files_list = []
        for file_name in diffs.keys():
            new_shop_files_list.append(file_name)
        shop_merge_log = util.get_master_modpack_dir() / 'logs' / 'shop.log'

        print('Performing shop merge...')
        if not self._pool:
            multiprocessing.set_start_method('spawn', True)
        pool = self._pool or multiprocessing.Pool()
        pool.map(partial(threaded_merge), diffs.items())
        if not self._pool:
            pool.close()
            pool.join()

        print('Saving shop merge log...')
        with shop_merge_log.open('w') as s_log:
            for file_name in new_shop_files_list:
                print(file_name, file=s_log)

    def get_checkbox_options(self):
        return []
    
    def get_mod_edit_info(self, mod: util.BcmlMod) -> set:
        return self.get_mod_affected(mod)
