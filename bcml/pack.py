"""Provides functions for diffing and merging SARC packs"""
# Copyright 2019 Nicene Nerd <macadamiadaze@gmail.com>
# Licensed under GPLv3+
import csv
import io
import os
from functools import partial
from multiprocessing import Pool, cpu_count
from pathlib import Path
from typing import List, Union

import sarc
import libyaz0
import xxhash

from bcml import data, util, mergers
from bcml.util import BcmlMod


def get_pack_mods() -> List[BcmlMod]:
    """
    Gets a list of all installed pack mods

    :return: Returns a list of mods that modify pack files
    :rtype: list of class:`bcml.util.BcmlMod`
    """
    pmods = [mod for mod in util.get_installed_mods() if (
        mod.path / 'logs' / 'packs.log').exists()]
    return sorted(pmods, key=lambda mod: mod.priority)


def get_modded_packs_in_mod(mod: Union[Path, str, BcmlMod]) -> List[str]:
    """
    Get all pack files modified by a given mod
    """
    path = mod if isinstance(mod, Path) else Path(
        mod) if isinstance(mod, str) else mod.path
    packs = []
    plog = path / 'logs' / 'packs.log'
    if not plog.exists():
        return []
    with plog.open('r') as rlog:
        csv_loop = csv.reader(rlog)
        for row in csv_loop:
            if 'logs' in str(row[1]) or str(row[0]) == 'name':
                continue
            packs.append(Path(str(row[1])).as_posix())
    return packs


def get_modded_sarcs() -> dict:
    """
    Gets all installed SARC modifications, along with their priorities

    :returns: Returns a dict of dicts with the path of each modified SARC and its priority for each
    canonical file.
    :rtype: dict of str: list of dict of str: int
    """
    packs = {}
    hashes = util.get_hash_table()
    for mod in get_pack_mods():
        with (mod.path / 'logs' / 'packs.log').open('r') as rlog:
            csv_loop = csv.reader(rlog)
            for row in csv_loop:
                if ('Bootup_' in row[0] and 'Bootup_Graphics' not in row[0]) \
                        or (row[0] == 'name') or row[0] not in hashes:
                    continue
                filepath = mod.path / str(row[1])
                if row[0] not in packs:
                    packs[row[0]] = []
                packs[row[0]].append({
                    'path': filepath,
                    'rel_path': Path(str(row[1])).as_posix(),
                    'priority': mod.priority
                })
    return packs


def get_sarc_versions(name: str, mod_list: dict) -> List[dict]:
    """
    Gets all of the modified versions of given SARC

    :param name: The canonical path of the SARC.
    :type name: str
    :param mod_list: The dict containing all modded SARC entries.
    :type mod_list: dict
    :returns: Returns a list of dicts containing each modified version
    of the given SARC with metadata.
    :rtype: list of dict of str: class:`sarc.SARC`, str: int, str: int, str: str
    """
    sarc_list = []
    for pack in mod_list[name]:
        try:
            with open(pack['path'], 'rb') as opened_pack:
                o_sarc = sarc.read_file_and_make_sarc(opened_pack)
                if o_sarc:
                    sarc_list.append({
                        'pack': o_sarc,
                        'priority': pack['priority'],
                        'nest_level': 1,
                        'name': name,
                        'base': False
                    })
        except FileNotFoundError:
            pass
    try:
        base_file = util.get_game_file(mod_list[name][0]['rel_path'])
        with base_file.open('rb') as s_file:
            b_sarc = sarc.read_file_and_make_sarc(s_file)
            if b_sarc:
                sarc_list.insert(0, {
                    'pack': b_sarc,
                    'priority': 1,
                    'nest_level': 1,
                    'name': name,
                    'base': True
                })
    except FileNotFoundError:
        pass
    return sarc_list


def merge_sarcs_old(sarc_list, verbose: bool = False, loose_files: dict = None) -> tuple:
    """
    Merges a list of SARC packs and returns the changes

    :param sarc_list: A list of dicts with SARCs to be merged and their metadata.
    Each entry must contain keys "pack", "priority", "nest_level", and "name".
    :type sarc_list: list
    :param verbose: Whether to display more detailed output, defaults to False
    :type verbose: bool, optional
    :returns: Returns tuple with a merged SARC and a list of changes made.
    :rtype: (class:`sarc.SARCWriter`, list of str)
    """
    hashes = util.get_hash_table()
    sarc_log = []
    sarc_list = sorted(sarc_list, key=lambda pack: pack['priority'])
    try:
        base_sarc = next(iter([msarc['pack']
                               for msarc in sarc_list if msarc['base']]))
    except StopIteration:
        base_sarc = sarc_list[-1]['pack']

    new_sarc = sarc.make_writer_from_sarc(base_sarc)
    output_spaces = '  ' * sarc_list[-1]['nest_level']

    modded_files = {}
    modded_sarcs = {}
    priority = 100
    for msarc in sarc_list:
        pack = msarc['pack']
        priority = msarc['priority']
        for file in pack.list_files():
            if file not in base_sarc.list_files():
                new_sarc.add_file(file, pack.get_file_data(file).tobytes())
                continue
            rfile = file.replace('.s', '.')
            fdata = util.unyaz_if_needed(
                pack.get_file_data(file).tobytes())
            if rfile not in hashes or hashes[rfile] != xxhash.xxh32(fdata).hexdigest():
                ext = os.path.splitext(rfile)[1]
                if ext in util.SARC_EXTS:
                    try:
                        nest_pack = sarc.SARC(fdata)
                    except ValueError:
                        modded_files[file] = priority
                        continue
                    modded_sarc = {
                        'pack': nest_pack,
                        'priority': priority,
                        'nest_level': sarc_list[-1]['nest_level'] + 1,
                        'name': rfile,
                        'base': False
                    }
                    if file not in modded_sarcs:
                        modded_sarcs[file] = []
                    modded_sarcs[file].append(modded_sarc)
                else:
                    modded_files[file] = priority

    # for modded_file in modded_files.keys():
    #    if not modded_files[modded_file] == priority:
    #        can_skip = False
    # if can_skip:
    #    if verbose:
    #        sarc_log.append(f'{output_spaces}No merges necessary, skipping')
    #    return new_sarc, sarc_log

    for modded_file in modded_files:
        if modded_file in base_sarc.list_files():
            new_sarc.delete_file(modded_file)
        ppack = next(
            iter(
                [pack for pack in sarc_list if pack['priority'] == modded_files[modded_file]]
            )
        )
        new_data = ppack['pack'].get_file_data(modded_file).tobytes()
        new_sarc.add_file(modded_file, new_data)
        if verbose:
            sarc_log.append(f'{output_spaces}Updated file {modded_file}')

    merged_sarcs = []
    for mod_sarc_list in modded_sarcs:
        if not modded_sarcs[mod_sarc_list]:
            continue
        new_pack, sub_log = merge_sarcs_old(
            modded_sarcs[mod_sarc_list], verbose, loose_files=loose_files)
        sarc_log.extend(sub_log)
        merged_sarcs.append({
            'file': mod_sarc_list,
            'pack': new_pack
        })

    for merged_sarc in merged_sarcs:
        if merged_sarc['file'] in base_sarc.list_files():
            new_sarc.delete_file(merged_sarc['file'])
        new_stream = io.BytesIO()
        merged_sarc['pack'].write(new_stream)
        new_data = new_stream.getvalue()
        del new_stream
        if '.s' in merged_sarc['file'] and not merged_sarc['file'].endswith('.sarc'):
            new_data = util.compress(new_data)
        new_sarc.add_file(merged_sarc['file'], new_data)
        del new_data

    for file in base_sarc.list_files():
        if file in loose_files:
            if file not in modded_files or loose_files[file] > modded_files[file]:
                mod = util.get_mod_by_priority(loose_files[file])
                prefix = 'content' if not file.startswith(
                    'Aoc/0010') else 'aoc/0010'
                modded_bytes = (mod / prefix /
                                file.replace('Aoc/0010', '')).read_bytes()
                new_sarc.delete_file(file)
                new_sarc.add_file(file, modded_bytes)

    if sarc_list[-1]['nest_level'] > 1:
        if verbose:
            sarc_log.append(
                f'{output_spaces[4:]}Updated nested pack {sarc_list[-1]["name"]}')

    if verbose:
        sarc_log.append(
            f'{output_spaces[4:]}Merged {len(sarc_list)} versions of {sarc_list[-1]["name"]}')
    return new_sarc, sarc_log


def threaded_merge_sarcs(pack, modded_sarcs, verbose, modded_files):
    """An interface for multiprocessing `merge_sarcs_old()`"""
    output_path = Path(util.get_master_modpack_dir() /
                       modded_sarcs[pack][0]['rel_path'])
    versions = get_sarc_versions(pack, modded_sarcs)
    try:
        new_sarc, log = merge_sarcs_old(versions, verbose, loose_files=modded_files)
    except IndexError:
        return []
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open('wb') as o_file:
        if output_path.suffix.startswith('.s') and output_path.suffix != '.sarc':
            o_file.write(util.compress(new_sarc.get_bytes()))
        else:
            new_sarc.write(o_file)
    return log


def merge_installed_packs(no_injection: bool = False, only_these: List[str] = None,
                          verbose: bool = False):
    """
    Merges all modified packs in installed BCML mods

    :param no_injection: Do not inject merged gamedata or savedata when possible, defaults to False
    :type no_injection: bool, optional
    :param verbose: Whether to display more detailed output, defaults to False
    :type verbose: bool, optional
    """
    print('Merging modified SARC packs...')
    modded_files = util.get_all_modded_files(only_loose=True)
    bcml_dir = util.get_master_modpack_dir()
    if only_these is None:
        if (bcml_dir / 'aoc').exists():
            print('Cleaning old aoc packs...')
            for file in (bcml_dir / 'aoc').rglob('**/*'):
                if file.is_file() and file.suffix in util.SARC_EXTS:
                    file.unlink()
        if (bcml_dir / 'content').exists():
            print('Cleaning old content packs...')
            for file in (bcml_dir / 'content').rglob('**/*'):
                if file.is_file() and file.suffix in util.SARC_EXTS and 'Bootup_' not in file.stem:
                    file.unlink()
    else:
        for file in only_these:
            if (bcml_dir / file).exists():
                (bcml_dir / file).unlink()
    print('Loading modded packs...')
    modded_sarcs = get_modded_sarcs()
    log_count = 0
    num_req = 0
    sarcs_to_merge = [
        pack for pack in modded_sarcs if len(modded_sarcs[pack]) > num_req]
    if only_these is not None:
        sarcs_to_merge = [
            pack for pack in sarcs_to_merge if modded_sarcs[pack][0]['rel_path'] in only_these]
    if sarcs_to_merge:
        print(f'Processing {len(sarcs_to_merge)} packs...')
        partial_thread_merge = partial(threaded_merge_sarcs, modded_sarcs=modded_sarcs,
                                       verbose=verbose, modded_files=modded_files)
        num_threads = min(cpu_count() - 1, len(modded_sarcs))
        pool = Pool(processes=num_threads)
        results = pool.map(partial_thread_merge, sarcs_to_merge)
        pool.close()
        pool.join()
        logs = [log for sublog in results for log in sublog]
        log_count = len([log for log in logs if log !=
                         'No merges necessary, skipping'])
    else:
        log_count = 0
    print(f'Pack merging complete. Merged {log_count} packs.')
    if 'Pack/Bootup.pack' in modded_sarcs and not no_injection:
        if only_these is not None and 'content/Pack/Bootup.pack' not in only_these:
            return
        if (util.get_master_modpack_dir() / 'logs' / 'gamedata.log').exists():
            print('Injecting merged gamedata.sarc into Bootup.pack...')
            with (util.get_master_modpack_dir() / 'logs' / 'gamedata.sarc').open('rb') as g_file:
                gamedata = sarc.read_sarc_and_make_writer(g_file)
            data.inject_gamedata_into_bootup(gamedata)
        if (util.get_master_modpack_dir() / 'logs' / 'savedata.log').exists():
            print('Injecting merged savedataformat.sarc into Bootup.pack...')
            with (util.get_master_modpack_dir() / 'logs' / 'savedata.sarc').open('rb') as s_file:
                savedata = sarc.read_sarc_and_make_writer(s_file)
            data.inject_savedata_into_bootup(savedata)
        if (util.get_master_modpack_dir() / 'logs' / 'eventinfo.log').exists():
            print('Injecting merged event info into Bootup.pack...')
            util.inject_file_into_bootup(
                'Event/EventInfo.product.sbyml',
                libyaz0.compress(
                    (util.get_master_modpack_dir() / 'logs' / 'eventinfo.byml').read_bytes(),
                    level=10
                )
            )


def merge_sarcs(file_name: str, sarcs: List[Union[Path, bytes]]) -> (str, bytes):
    opened_sarcs: List[sarc.SARC] = []
    if isinstance(sarcs[0], Path):
        for i, sarc_path in enumerate(sarcs):
            sarcs[i] = sarc_path.read_bytes()
    for sarc_bytes in sarcs:
        sarc_bytes = util.unyaz_if_needed(sarc_bytes)
        try:
            opened_sarcs.append(sarc.SARC(sarc_bytes))
        except ValueError:
            continue

    all_files = {key for open_sarc in opened_sarcs for key in open_sarc.list_files()}
    nested_sarcs = {}
    new_sarc = sarc.SARCWriter(be=True)
    files_added = []

    # for file in all_files:
    #     dm_cache = util.get_master_modpack_dir() / 'logs' / 'dm' / file
    #     if dm_cache.exists():
    #         file_data = dm_cache.read_bytes()
    #         new_sarc.add_file(file, file_data)
    #         files_added.append(file)

    for opened_sarc in reversed(opened_sarcs):
        for file in [file for file in opened_sarc.list_files() if file not in files_added]:
            data = opened_sarc.get_file_data(file).tobytes()
            if util.is_file_modded(file.replace('.s', '.'), data, count_new=True):
                if not Path(file).suffix in util.SARC_EXTS:
                    new_sarc.add_file(file, data)
                    files_added.append(file)
                else:
                    if file not in nested_sarcs:
                        nested_sarcs[file] = []
                    nested_sarcs[file].append(util.unyaz_if_needed(data))
    for file, sarcs in nested_sarcs.items():
        merged_bytes = merge_sarcs(file, sarcs)[1]
        if Path(file).suffix.startswith('.s') and not file.endswith('.sarc'):
            merged_bytes = util.compress(merged_bytes)
        new_sarc.add_file(file, merged_bytes)
        files_added.append(file)
    for file in [file for file in all_files if file not in files_added]:
        for opened_sarc in [open_sarc for open_sarc in opened_sarcs \
                            if file in open_sarc.list_files()]:
            new_sarc.add_file(file, opened_sarc.get_file_data(file).tobytes())
            break

    if 'Bootup.pack' in file_name:
        for merger in [merger() for merger in mergers.get_mergers() if merger.is_bootup_injector()]:
            inject = merger.get_bootup_injection()
            if not inject:
                continue
            file, data = inject
            try:
                new_sarc.delete_file(file)
            except KeyError:
                pass
            new_sarc.add_file(file, data)

    return (file_name, new_sarc.get_bytes())


class PackMerger(mergers.Merger):
    """ A merger for modified pack files """
    NAME: str = 'packs'

    def __init__(self):
        super().__init__('SARC pack merger', 'Merges modified files within SARCs', 'packs.log', {})

    def can_partial_remerge(self):
        return True

    def get_mod_affected(self, mod):
        return get_modded_packs_in_mod(mod)

    def generate_diff(self, mod_dir: Path, modded_files: List[Union[str, Path]]):
        packs = {}
        for file in [file for file in modded_files \
                     if isinstance(file, Path) and file.suffix in util.SARC_EXTS]:
            canon = util.get_canon_name(file.relative_to(mod_dir).as_posix())
            if canon and not any(ex in file.name for ex in ['Dungeon', 'Bootup_', 'AocMainField']):
                packs[canon] = file.relative_to(mod_dir).as_posix()
        return packs

    def log_diff(self, mod_dir: Path, diff_material: Union[dict, List[Path]]):
        if isinstance(diff_material, List):
            diff_material = self.generate_diff(mod_dir, diff_material)
        with (mod_dir / 'logs' / self._log_name).open('w', encoding='utf-8') as log:
            log.write('name,path\n')
            for canon, path in diff_material.items():
                if 'logs' in path:
                    continue
                log.write(f'{canon},{path}\n')

    def get_mod_diff(self, mod: util.BcmlMod):
        return get_modded_packs_in_mod(mod)

    def get_all_diffs(self):
        diffs = {}
        for mod in [mod for mod in util.get_installed_mods() if self.is_mod_logged(mod)]:
            diffs[mod] = get_modded_packs_in_mod(mod)
        return diffs

    def consolidate_diffs(self, diffs):
        all_sarcs = set()
        all_diffs = {}
        for mod in sorted(diffs.keys(), key=lambda mod: mod.priority):
            all_sarcs |= set(diffs[mod])
        for modded_sarc in all_sarcs:
            for mod, diff in diffs.items():
                if modded_sarc in diff:
                    if not modded_sarc in all_diffs:
                        all_diffs[modded_sarc] = []
                    if (mod.path / modded_sarc).exists():
                        all_diffs[modded_sarc].append(mod.path / modded_sarc)
        return all_diffs

    def perform_merge(self):
        print('Loading modded SARC list...')
        sarcs = self.consolidate_diffs(self.get_all_diffs())
        if 'only_these' in self._options:
            for sarc_file in self._options['only_these']:
                master_path = (util.get_master_modpack_dir() / sarc_file)
                if master_path.exists():
                    master_path.unlink()
            for sarc_file in [file for file in sarcs if file not in self._options['only_these']]:
                del sarcs[sarc_file]
        else:
            for file in [file for file in util.get_master_modpack_dir().rglob('**/*') \
                        if file.suffix in util.SARC_EXTS]:
                file.unlink()
        for sarc_file in sarcs:
            try:
                sarcs[sarc_file].insert(0, util.get_game_file(sarc_file))
            except FileNotFoundError:
                continue
        if not sarcs:
            print('No SARC merging necessary')
            return
        num_threads = min(cpu_count(), len(sarcs))
        pool = Pool(processes=num_threads)
        print(f'Merging {len(sarcs)} SARC files...')
        results = pool.starmap(merge_sarcs, sarcs.items())
        pool.close()
        pool.join()
        for result in results:
            file, data = result
            output_path = util.get_master_modpack_dir() / file
            output_path.parent.mkdir(parents=True, exist_ok=True)
            if output_path.suffix.startswith('.s'):
                data = util.compress(data)
            output_path.write_bytes(data)
        print('Finished merging SARCs')

    def perform_merge_old(self):
        if 'only_these' not in self._options:
            merge_installed_packs(no_injection=False)
        else:
            merge_installed_packs(no_injection=False, only_these=self._options['only_these'])

    def get_checkbox_options(self):
        return []
