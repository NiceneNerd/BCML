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
            real_data = util.unyaz_if_needed(data)
            if util.is_file_modded(file.replace('.s', '.'), real_data, count_new=True):
                if not Path(file).suffix in util.SARC_EXTS:
                    del real_data
                    new_sarc.add_file(file, data)
                    files_added.append(file)
                else:
                    if file not in nested_sarcs:
                        nested_sarcs[file] = []
                    nested_sarcs[file].append(real_data)
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

    def __init__(self, pool: Pool = None):
        super().__init__(
            'SARC pack merger',
            'Merges modified files within SARCs',
            'packs.log',
            {},
            pool
        )

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
        pool = self._pool or Pool(processes=num_threads)
        print(f'Merging {len(sarcs)} SARC files...')
        results = pool.starmap(merge_sarcs, sarcs.items())
        for result in results:
            file, data = result
            output_path = util.get_master_modpack_dir() / file
            output_path.parent.mkdir(parents=True, exist_ok=True)
            if output_path.suffix.startswith('.s'):
                data = util.compress(data)
            output_path.write_bytes(data)
        if not self._pool:
            pool.close()
            pool.join()
        print('Finished merging SARCs')

    def get_checkbox_options(self):
        return []
