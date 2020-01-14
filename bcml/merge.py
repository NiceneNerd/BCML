"""Provides functions for diffing and merging AAMP files"""
# Copyright 2019 Nicene Nerd <macadamiadaze@gmail.com>
# Licensed under GPLv3+

import multiprocessing
import os
from copy import deepcopy
from functools import partial, reduce
from pathlib import Path
from typing import List, Union

import aamp
import aamp.converters
from aamp.parameters import ParameterList, ParameterIO, ParameterObject
import aamp.yaml_util
import sarc
import yaml
from byml import yaml_util

import bcml.rstable
from bcml import util, install, mergers
from bcml.util import BcmlMod


def _aamp_diff(base: Union[ParameterIO, ParameterList],
               modded: Union[ParameterIO, ParameterList]) -> ParameterList:
    diffs = ParameterList()
    #diffs._crc32 = base._crc32
    for crc, plist in modded.lists.items():
        if crc not in base.lists:
            diffs.lists[crc] = plist
        else:
            diff = _aamp_diff(base.lists[crc], plist)
            if diff.lists or diff.objects:
                diffs.lists[crc] = diff
    for crc, obj in modded.objects.items():
        if crc not in base.objects:
            diffs.objects[crc] = obj
        else:
            base_obj = base.objects[crc]
            diff_obj = ParameterObject()
            #diff_obj._crc32 = base_obj._crc32
            changed = False
            for param, value in obj.params.items():
                if param not in base_obj.params or str(value) != str(base_obj.params[param]):
                    changed = True
                    diff_obj.params[param] = value
            if changed:
                diffs.objects[crc] = diff_obj
    return diffs


def _aamp_merge(base: Union[ParameterIO, ParameterList],
                modded: Union[ParameterIO, ParameterList]) -> ParameterIO:
    merged = deepcopy(base)
    for crc, plist in modded.lists.items():
        if crc not in base.lists:
            merged.lists[crc] = plist
        else:
            merge = _aamp_merge(base.lists[crc], plist)
            if merge.lists or merge.objects:
                merged.lists[crc] = merge
    for crc, obj in modded.objects.items():
        if crc not in base.objects:
            merged.objects[crc] = obj
        else:
            base_obj = base.objects[crc]
            merge_obj = deepcopy(base_obj)
            changed = False
            for param, value in obj.params.items():
                if param not in base_obj.params or value != base_obj.params[param]:
                    changed = True
                    merge_obj.params[param] = value
            if changed:
                merged.objects[crc] = merge_obj
    return merged


def get_aamp_diff(file: Union[Path, str], tmp_dir: Path):
    """
    Diffs a modded AAMP file from the stock game version

    :param file: The modded AAMP file to diff
    :type file: class:`typing.Union[class:pathlib.Path, str]`
    :param tmp_dir: The temp directory containing the mod
    :type tmp_dir: class:`pathlib.Path`
    :return: Returns a string representation of the AAMP file diff
    """
    if isinstance(file, str):
        nests = file.split('//')
        mod_bytes = util.get_nested_file_bytes(file)
        ref_path = str(util.get_game_file(
            Path(nests[0]).relative_to(tmp_dir))) + '//' + '//'.join(nests[1:])
        ref_bytes = util.get_nested_file_bytes(ref_path)
    else:
        with file.open('rb') as m_file:
            mod_bytes = m_file.read()
        mod_bytes = util.unyaz_if_needed(mod_bytes)
        with util.get_game_file(file.relative_to(tmp_dir)).open('rb') as r_file:
            ref_bytes = r_file.read()
        ref_bytes = util.unyaz_if_needed(ref_bytes)

    ref_aamp = aamp.Reader(ref_bytes).parse()
    mod_aamp = aamp.Reader(mod_bytes).parse()

    return _aamp_diff(ref_aamp, mod_aamp)


def get_deepmerge_mods() -> List[BcmlMod]:
    """ Gets a list of all installed mods that use deep merge """
    dmods = [mod for mod in util.get_installed_mods() if (
        mod.path / 'logs' / 'deepmerge.yml').exists()]
    return sorted(dmods, key=lambda mod: mod.priority)


def get_mod_deepmerge_files(mod: Union[Path, str, BcmlMod]) -> []:
    """ Gets a list of files logged for deep merge in a given mod """
    path = mod if isinstance(mod, Path) else Path(mod) if isinstance(mod, str) else mod.path
    dlog = path / 'logs' / 'deepmerge.yml'
    if not dlog.exists():
        return []
    loader = yaml.CSafeLoader
    yaml_util.add_constructors(loader)
    aamp.yaml_util.register_constructors(loader)
    with dlog.open('r', encoding='utf-8') as d_file:
        mod_diffs = yaml.load(d_file, Loader=loader)
    return [str(key) for key in mod_diffs.keys()]


def get_deepmerge_diffs(only_these: List[str] = None) -> dict:
    """
    Gets the logged file diffs for installed deep merge mods

    :return: Returns a dict of modified AAMP and BYML file paths and a list of diffs for each.
    :rtype: dict of str: dict of str: list of str
    """
    aamp_diffs = {}
    loader = yaml.CSafeLoader
    yaml_util.add_constructors(loader)
    aamp.yaml_util.register_constructors(loader)
    for mod in get_deepmerge_mods():
        with (mod.path / 'logs' / 'deepmerge.yml').open('r', encoding='utf-8') as d_file:
            mod_diffs = yaml.load(d_file, Loader=loader)
            for file in mod_diffs:
                if only_these is not None and file not in only_these:
                    continue
                if file not in aamp_diffs:
                    aamp_diffs[file] = []
                aamp_diffs[file].append(mod_diffs[file])
    return aamp_diffs


def consolidate_diff_files(diffs: dict) -> dict:
    """
    Consolidates the files which need to be deep merged to avoid any need to repeatedly open the
    same files.
    """
    consolidated_diffs = {}
    for file, diff_list in diffs.items():
        nest = reduce(lambda res, cur: {cur: res}, reversed(
            file.split("//")), diff_list)
        util.dict_merge(consolidated_diffs, nest)
    return consolidated_diffs


def nested_patch(pack: sarc.SARC, nest: dict) -> (sarc.SARCWriter, dict):
    """
    Recursively patches deep merge files in a SARC

    :param pack: The SARC in which to recursively patch.
    :type pack: class:`sarc.SARC`
    :param nest: A dict of nested patches to apply.
    :type nest: dict
    :return: Returns a new SARC with patches applied and a dict of any failed patches.
    :rtype: (class:`sarc.SARCWriter`, dict, dict)
    """
    new_sarc = sarc.make_writer_from_sarc(pack)
    failures = {}

    for file, stuff in nest.items():
        file_bytes = pack.get_file_data(file).tobytes()
        yazd = file_bytes[0:4] == b'Yaz0'
        file_bytes = util.decompress(file_bytes) if yazd else file_bytes

        if isinstance(stuff, dict):
            sub_sarc = sarc.SARC(file_bytes)
            new_sarc.delete_file(file)
            new_sub_sarc, sub_failures = nested_patch(sub_sarc, stuff)
            for failure in sub_failures:
                failure[file + '//' + failure] = sub_failures[failure]
            del sub_sarc
            new_bytes = new_sub_sarc.get_bytes()
            new_sarc.add_file(file, new_bytes if not yazd else util.compress(new_bytes))

        elif isinstance(stuff, list):
            try:
                if file_bytes[0:4] == b'AAMP':
                    aamp_contents = aamp.Reader(file_bytes).parse()
                    for change in stuff:
                        aamp_contents = _aamp_merge(aamp_contents, change)
                    aamp_bytes = aamp.Writer(aamp_contents).get_bytes()
                    del aamp_contents
                    new_bytes = aamp_bytes if not yazd else util.compress(aamp_bytes)
                    cache_merged_aamp(file, new_bytes)
                else:
                    raise ValueError('Wait, what the heck, this isn\'t an AAMP file?!')
            except ValueError:
                new_bytes = pack.get_file_data(file).tobytes()
                print(f'Deep merging {file} failed. No changed were made.')

            new_sarc.delete_file(file)
            new_sarc.add_file(file, new_bytes)
    return new_sarc, failures


def cache_merged_aamp(file: str, data: bytes):
    out = Path(util.get_master_modpack_dir() / 'logs' / 'dm' / file)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)


def get_merged_files() -> List[str]:
    """Gets a list of all currently deep merged files"""
    log = util.get_master_modpack_dir() / 'logs' / 'deepmerge.log'
    if not log.exists():
        return []
    else:
        with log.open('r') as l_file:
            return l_file.readlines()


def threaded_merge(item, verbose: bool) -> (str, dict):
    """Deep merges an individual file, suitable for multiprocessing"""
    file, stuff = item
    failures = {}

    base_file = util.get_game_file(file, file.startswith('aoc'))
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
        new_sarc, sub_failures = nested_patch(sarc.SARC(file_bytes), stuff)
        del file_bytes
        new_bytes = new_sarc.get_bytes()
        for failure, contents in sub_failures.items():
            print(f'Some patches to {failure} failed to apply.')
            failures[failure] = contents
    else:
        try:
            if magic == b'AAMP':
                aamp_contents = aamp.Reader(file_bytes).parse()
                for change in stuff:
                    aamp_contents = _aamp_merge(aamp_contents, change)
                aamp_bytes = aamp.Writer(aamp_contents).get_bytes()
                del aamp_contents
                new_bytes = aamp_bytes if not yazd else util.compress(aamp_bytes)
            else:
                raise ValueError(f'{file} is not a SARC or AAMP file.')
        except ValueError:
            new_bytes = file_bytes
            del file_bytes
            print(f'Deep merging file {file} failed. No changes were made.')

    new_bytes = new_bytes if not yazd else util.compress(new_bytes)
    output_file = (util.get_master_modpack_dir() / file)
    if base_file == output_file:
        output_file.unlink()
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_bytes(new_bytes)
    del new_bytes
    if magic == b'SARC' and verbose:
        print(f'Finished patching files inside {file}')
    elif verbose:
        print(f'Finished patching {file}')
    return util.get_canon_name(file), failures


def deep_merge(verbose: bool = False, wait_rstb: bool = False, only_these: List[str] = None):
    """Performs deep merge on all installed AAMP files"""
    mods = get_deepmerge_mods()
    if not mods:
        print('No deep merge necessary.')
        return
    if (util.get_master_modpack_dir() / 'logs' / 'rstb.log').exists():
        (util.get_master_modpack_dir() / 'logs' / 'rstb.log').unlink()
    merge_log = (util.get_master_modpack_dir() / 'logs' / 'deepmerge.log')
    old_merges = []
    if merge_log.exists():
        if only_these:
            old_merges = merge_log.read_text().splitlines()
        merge_log.unlink()


    print('Loading deep merge data...')
    diffs = consolidate_diff_files(get_deepmerge_diffs(only_these=only_these))

    print('Performing deep merge...')
    if not diffs:
        return
    num_threads = min(multiprocessing.cpu_count(), len(diffs))
    pool = multiprocessing.Pool(processes=num_threads)
    pool.map(partial(threaded_merge, verbose=verbose), diffs.items())
    pool.close()
    pool.join()

    if not wait_rstb:
        bcml.rstable.generate_master_rstb()

    (util.get_master_modpack_dir() / 'logs').mkdir(parents=True, exist_ok=True)
    with merge_log.open('w', encoding='utf-8') as l_file:
        for file_type in diffs:
            for file in diffs[file_type]:
                l_file.write(f'{file}\n')
                if only_these and file in old_merges:
                    old_merges.remove(file)
        if only_these:
            for file in old_merges:
                l_file.write(f'{file}\n')



class DeepMerger(mergers.Merger):
    NAME: str = 'deepmerge'

    def __init__(self):
        super().__init__('deep merge', 'Merges changes within arbitrary AAMP files',
                         'deepmerge.yml', options={})

    def generate_diff(self, mod_dir: Path, modded_files: List[Union[Path, str]]):
        print('Logging changes to AAMP files...')
        diffs = {}
        for file in [file for file in modded_files if Path(file).suffix in util.AAMP_EXTS]:
            try:
                diffs[file] = get_aamp_diff(str(mod_dir) + '/' + file, mod_dir)
            except (FileNotFoundError, KeyError, TypeError):
                continue
        return diffs

    def log_diff(self, mod_dir: Path, diff_material: Union[dict, List[Path]]):
        if isinstance(diff_material, List):
            diff_material = self.generate_diff(mod_dir, diff_material)
        if diff_material:
            dumper = yaml.CSafeDumper
            aamp.yaml_util.register_representers(dumper)
            setattr(dumper, '__aamp_reader', None)
            aamp.yaml_util._get_pstruct_name = lambda reader, idx, k, parent_crc32: k # pylint: disable=protected-access
            with (mod_dir / 'logs' / self._log_name).open('w', encoding='utf-8') as log:
                yaml.dump(diff_material, log, Dumper=dumper, allow_unicode=True, encoding='utf-8',
                          default_flow_style=None)

    def can_partial_remerge(self):
        return True

    def get_mod_affected(self, mod):
        return get_mod_deepmerge_files(mod)

    def get_mod_diff(self, mod: Path):
        if self.is_mod_logged(mod):
            with (mod.path / 'logs' / self._log_name).open('r', encoding='utf-8') as log:
                loader = yaml.CSafeLoader
                aamp.yaml_util.register_constructors(loader)
                return yaml.load(log, Loader=loader)
        else:
            return {}

    def get_all_diffs(self):
        if 'only_these' in self._options:
            return get_deepmerge_diffs(self._options['only_these'])
        else:
            return get_deepmerge_diffs()

    def consolidate_diffs(self, diffs: list):
        return consolidate_diff_files(self.get_all_diffs())

    def perform_merge(self):
        if 'only_these' in self._options:
            deep_merge(wait_rstb=True, only_these=self._options['only_these'])
        else:
            deep_merge(wait_rstb=True)

    def get_checkbox_options(self):
        return []
