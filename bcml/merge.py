# Copyright 2019 Nicene Nerd <macadamiadaze@gmail.com>
# Licensed under GPLv3+

import multiprocessing
import os
from copy import deepcopy
from fnmatch import fnmatch
from functools import partial, reduce
from pathlib import Path
from typing import List, Union

import aamp
import aamp.converters
import aamp.yaml_util
import sarc
import wszst_yaz0
import yaml
from aamp.parameters import ParameterList, ParameterIO, ParameterObject
from byml import yaml_util

import bcml.rstable
from bcml import util, install
from bcml.util import BcmlMod


def _aamp_diff(base: Union[ParameterIO, ParameterList],
               modded: Union[ParameterIO, ParameterList]) -> ParameterList:
    diffs = ParameterList()
    diffs._crc32 = base._crc32
    for crc, plist in modded.lists.items():
        if crc not in base.lists:
            diffs.lists[crc] = plist
        else:
            diff = _aamp_diff(base.lists[crc], plist)
            if len(diff.lists) > 0 or len(diff.objects) > 0:
                diffs.lists[crc] = diff
    for crc, obj in modded.objects.items():
        if crc not in base.objects:
            diffs.objects[crc] = obj
        else:
            base_obj = base.objects[crc]
            diff_obj = ParameterObject()
            diff_obj._crc32 = base_obj._crc32
            changed = False
            for param, value in obj.params.items():
                if param not in base_obj.params or value != base_obj.params[param]:
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
            if len(merge.lists) > 0 or len(merge.objects) > 0:
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
    :type file: :class:`typing.Union[:class:pathlib.Path, str]`
    :param tmp_dir: The temp directory containing the mod
    :type tmp_dir: :class:`pathlib.Path`
    :return: Returns a string representation of the AAMP file diff
    """
    if isinstance(file, str):
        nests = file.split('//')
        mod_bytes = util.get_nested_file_bytes(file)
        ref_path = str(util.get_game_file(
            Path(nests[0]).relative_to(tmp_dir))) + '//' + '//'.join(nests[1:])
        ref_bytes = util.get_nested_file_bytes(ref_path)
    else:
        with file.open('rb') as mf:
            mod_bytes = mf.read()
        mod_bytes = util.unyaz_if_needed(mod_bytes)
        with util.get_game_file(file.relative_to(tmp_dir)).open('rb') as rf:
            ref_bytes = rf.read()
        ref_bytes = util.unyaz_if_needed(ref_bytes)

    ref_aamp = aamp.Reader(ref_bytes).parse()
    mod_aamp = aamp.Reader(mod_bytes).parse()

    return _aamp_diff(ref_aamp, mod_aamp)


def get_deepmerge_mods() -> List[BcmlMod]:
    """ Gets a list of all installed mods that use deep merge """
    dmods = [mod for mod in util.get_installed_mods() if (
        mod.path / 'logs' / 'deepmerge.yml').exists()]
    return sorted(dmods, key=lambda mod: mod.priority)


def get_mod_deepmerge_files(mod: Union[Path, str, BcmlMod]) -> dict:
    """ Gets a list of files logged for deep merge in a given mod """
    path = mod if isinstance(mod, Path) else Path(
        mod) if isinstance(mod, str) else mod.path
    loader = yaml.CSafeLoader
    yaml_util.add_constructors(loader)
    aamp.yaml_util.register_constructors(loader)
    with (mod.path / 'logs' / 'deepmerge.yml').open('r', encoding='utf-8') as df:
        mod_diffs = yaml.load(df, Loader=loader)
    return [str(key) for key in mod_diffs.keys()]


def get_deepmerge_diffs(only_these: List[str] = None) -> dict:
    """
    Gets the logged file diffs for installed deep merge mods

    :return: Returns a dict containing modified AAMP and BYML file paths and a list of diffs for each.
    :rtype: dict of str: dict of str: list of str
    """
    aamp_diffs = {}
    loader = yaml.CSafeLoader
    yaml_util.add_constructors(loader)
    aamp.yaml_util.register_constructors(loader)
    for mod in get_deepmerge_mods():
        with (mod.path / 'logs' / 'deepmerge.yml').open('r', encoding='utf-8') as df:
            mod_diffs = yaml.load(df, Loader=loader)
            for file in mod_diffs:
                if only_these is not None and file not in only_these:
                    continue
                if file not in aamp_diffs:
                    aamp_diffs[file] = []
                aamp_diffs[file].append(mod_diffs[file])
                for file, diffs in list(aamp_diffs.items()):
                    if len(diffs) < 2 and '//' not in file:
                        del aamp_diffs[file]
    return aamp_diffs


def consolidate_diff_files(diffs: dict) -> dict:
    """ Consolidates the files which need to be deep merged to avoid any need to repeatedly open the same files. """
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
    :type pack: :class:`sarc.SARC`
    :param nest: A dict of nested patches to apply.
    :type nest: dict
    :return: Returns a new SARC with patches applied and a dict of any failed patches.
    :rtype: (:class:`sarc.SARCWriter`, dict, dict)
    """
    new_sarc = sarc.make_writer_from_sarc(pack)
    failures = {}

    for file, stuff in nest.items():
        file_bytes = pack.get_file_data(file).tobytes()
        yazd = file_bytes[0:4] == b'Yaz0'
        file_bytes = wszst_yaz0.decompress(file_bytes) if yazd else file_bytes

        if isinstance(stuff, dict):
            sub_sarc = sarc.SARC(file_bytes)
            new_sarc.delete_file(file)
            new_sub_sarc, sub_failures = nested_patch(sub_sarc, stuff)
            for failure in sub_failures:
                failure[file + '//' + failure] = sub_failures[failure]
            del sub_sarc
            new_bytes = new_sub_sarc.get_bytes()
            new_sarc.add_file(
                file, new_bytes if not yazd else wszst_yaz0.compress(new_bytes))

        elif isinstance(stuff, list):
            try:
                if file_bytes[0:4] == b'AAMP':
                    aamp_contents = aamp.Reader(file_bytes).parse()
                    for change in stuff:
                        aamp_contents = _aamp_merge(aamp_contents, change)
                    aamp_bytes = aamp.Writer(aamp_contents).get_bytes()
                    del aamp_contents
                    new_bytes = aamp_bytes if not yazd else wszst_yaz0.compress(
                        aamp_bytes)
                else:
                    raise ValueError(
                        'Wait, what the heck, this isn\'t an AAMP file?!')
            except:
                new_bytes = pack.get_file_data(file).tobytes()
                print(f'Deep merging {file} failed. No changed were made.')

            new_sarc.delete_file(file)
            new_sarc.add_file(file, new_bytes)
    return new_sarc, failures


def get_merged_files() -> List[str]:
    log = util.get_master_modpack_dir() / 'logs' / 'deepmerge.log'
    if not log.exists():
        return []
    else:
        with log.open('r') as lf:
            return lf.readlines()


def threaded_merge(item, verbose: bool) -> (str, dict):
    file, stuff = item
    failures = {}
    dumper = yaml.CDumper
    yaml_util.add_representers(dumper)
    loader = yaml.CSafeLoader
    yaml_util.add_constructors(loader)

    base_file = util.get_game_file(file, file.startswith('aoc'))
    if (util.get_master_modpack_dir() / file).exists():
        base_file = util.get_master_modpack_dir() / file
    file_ext = os.path.splitext(file)[1]
    if file_ext in util.SARC_EXTS and (util.get_master_modpack_dir() / file).exists():
        base_file = (util.get_master_modpack_dir() / file)
    with base_file.open('rb') as bf:
        file_bytes = bf.read()
    yazd = file_bytes[0:4] == b'Yaz0'
    file_bytes = file_bytes if not yazd else wszst_yaz0.decompress(file_bytes)
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
                new_bytes = aamp_bytes if not yazd else wszst_yaz0.compress(
                    aamp_bytes)
            else:
                raise ValueError(f'{file} is not a SARC or AAMP file.')
        except:
            new_bytes = file_bytes
            del file_bytes
            print(f'Deep merging file {file} failed. No changes were made.')

    new_bytes = new_bytes if not yazd else wszst_yaz0.compress(new_bytes)
    output_file = (util.get_master_modpack_dir() / file)
    if base_file == output_file:
        output_file.unlink()
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open('wb') as of:
        of.write(new_bytes)
    del new_bytes
    if magic == b'SARC' and verbose:
        print(f'Finished patching files inside {file}')
    elif verbose:
        print(f'Finished patching {file}')
    return util.get_canon_name(file), failures


def deep_merge(verbose: bool = False, wait_rstb: bool = False, only_these: List[str] = None):
    mods = get_deepmerge_mods()
    if (util.get_master_modpack_dir() / 'logs' / 'rstb.log').exists():
        (util.get_master_modpack_dir() / 'logs' / 'rstb.log').unlink()
    if (util.get_master_modpack_dir() / 'logs' / 'deepmerge.log').exists():
        (util.get_master_modpack_dir() / 'logs' / 'deepmerge.log').unlink()
    if len(mods) < 2:
        print('No deep merge necessary.')
        return

    print('Loading deep merge data...')
    diffs = consolidate_diff_files(get_deepmerge_diffs(only_these=only_these))
    failures = {}

    print('Performing deep merge...')
    if len(diffs) == 0:
        return
    num_threads = min(multiprocessing.cpu_count(), len(diffs))
    p = multiprocessing.Pool(processes=num_threads)
    results = p.map(partial(threaded_merge, verbose=verbose), diffs.items())
    p.close()
    p.join()
    for name, fails in results:
        failures.update(fails)

    print('Updating RSTB...')
    modded_files = install.find_modded_files(util.get_master_modpack_dir())[0]
    sarc_files = [file for file in modded_files if util.is_file_sarc(file) and not fnmatch(
        file, '*Bootup_????.pack')]
    modded_sarc_files = {}
    if len(sarc_files) > 0:
        num_threads = min(len(sarc_files), multiprocessing.cpu_count())
        p = multiprocessing.Pool(processes=num_threads)
        thread_sarc_search = partial(install.threaded_find_modded_sarc_files, modded_files=modded_files,
                                     tmp_dir=util.get_master_modpack_dir(), deep_merge=False, verbose=verbose)
        results = p.map(thread_sarc_search, sarc_files)
        p.close()
        p.join()
        for result in results:
            modded_sarcs, sarc_changes, nested_diffs = result
            if len(modded_sarcs) > 0:
                modded_sarc_files.update(modded_sarcs)
    (util.get_master_modpack_dir() / 'logs').mkdir(parents=True, exist_ok=True)
    with Path(util.get_master_modpack_dir() / 'logs' / 'rstb.log').open('w') as rf:
        rf.write('name,rstb\n')
        modded_files.update(modded_sarc_files)
        for file in modded_files:
            ext = os.path.splitext(file)[1]
            if ext not in install.RSTB_EXCLUDE and 'ActorInfo' not in file:
                rf.write('{},{},{}\n'
                         .format(file, modded_files[file]["rstb"], str(modded_files[file]["path"]).replace('\\', '/'))
                         )
    if not wait_rstb:
        bcml.rstable.generate_master_rstb()

    with (util.get_master_modpack_dir() / 'logs' / 'deepmerge.log').open('w') as lf:
        for file_type in diffs:
            for file in diffs[file_type]:
                lf.write(f'{file}\n')
    if len(failures) > 0:
        with (util.get_work_dir() / 'failures.yml').open('w') as ff:
            yaml.safe_dump(failures, ff)
        print(f'In {len(failures)} files, one or more patches failed to apply. For more information, the following log'
              f'file contains the resultant contents of all of the files which had patch failures:\n'
              f'{str(util.get_work_dir() / "failures.yml")}')
