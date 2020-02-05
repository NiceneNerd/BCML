"""Provides functions for diffing and merging the BotW Resource Size Table"""
# Copyright 2019 Nicene Nerd <macadamiadaze@gmail.com>
# Licensed under GPLv3+
import csv
import io
import os
import multiprocessing
import struct
import zlib
from copy import deepcopy
from functools import partial
from pathlib import Path
from typing import List, Union

import rstb
from rstb import ResourceSizeTable
from rstb.util import read_rstb
import sarc
import syaz0

from bcml import util, install, mergers
from bcml.util import BcmlMod

RSTB_EXCLUDE_EXTS = ['.pack', '.bgdata', '.txt', '.bgsvdata', '.yml',
                     '.bat', '.ini', '.png', '.bfstm', '.py', '.sh']
RSTB_EXCLUDE_NAMES = ['ActorInfo.product.byml']


def get_stock_rstb() -> rstb.ResourceSizeTable:
    """ Gets the unmodified RSTB """
    if not hasattr(get_stock_rstb, 'table'):
        get_stock_rstb.table = read_rstb(
            str(util.get_game_file('System/Resource/ResourceSizeTable.product.srsizetable')),
            True
        )
    return deepcopy(get_stock_rstb.table)


def calculate_size(path: Path) -> int:
    """
    Calculates the resource size value for the given file

    :returns: The proper RSTB value for the file if it can be calculated, otherwise 0.
    :rtype: int
    """
    if not hasattr(calculate_size, 'rstb_calc'):
        calculate_size.rstb_calc = rstb.SizeCalculator()
    try:
        return calculate_size.rstb_calc.calculate_file_size(
            file_name=str(path),
            wiiu=True,
            force=False
        )
    except struct.error:
        return 0


def set_size(entry: str, size: int):
    """
    Sets the size of a resource in the current master RSTB

    :param entry: The resource to set
    :type entry: str
    :param size: The resource size
    :type size: int
    """
    rstb_path = util.get_master_modpack_dir() / 'content' / 'System' / 'Resource' /\
                'ResourceSizeTable.product.srsizetable'
    if rstb_path.exists():
        table = read_rstb(rstb_path, be=True)
    else:
        table = get_stock_rstb()
        rstb_path.parent.mkdir(parents=True, exist_ok=True)
    table.set_size(entry, size)
    buf = io.BytesIO()
    table.write(buf, be=True)
    rstb_path.write_bytes(
        util.compress(buf.getvalue())
    )


def guess_bfres_size(file: Union[Path, bytes], name: str = '') -> int:
    if isinstance(file, bytes):
        real_size = len(file)
        del file
    else:
        if file.suffix.startswith('.s'):
            with file.open('rb') as f:
                real_size = syaz0.get_header(f.read(16)).uncompressed_size
        else:
            real_size = file.stat().st_size
    if name == '':
        if isinstance(file, Path):
            name = file.name
        else:
            raise ValueError('BFRES name must not be blank if passing file as bytes.')
    if '.Tex' in name:
        if real_size < 100:
            return real_size * 9
        elif 100 < real_size <= 2000:
            return real_size * 7
        elif 2000 < real_size <= 3000:
            return real_size * 5
        elif 3000 < real_size <= 4000:
            return real_size * 4
        elif 4000 < real_size <= 8500:
            return real_size * 3
        elif 8500 < real_size <= 12000:
            return real_size * 2
        elif 12000 < real_size <= 17000:
            return int(real_size * 1.75)
        elif 17000 < real_size <= 30000:
            return int(real_size * 1.5)
        elif 30000 < real_size <= 45000:
            return int(real_size * 1.3)
        elif 45000 < real_size <= 100000:
            return int(real_size * 1.2)
        elif 100000 < real_size <= 150000:
            return int(real_size * 1.1)
        elif 150000 < real_size <= 200000:
            return int(real_size * 1.07)
        elif 200000 < real_size <= 250000:
            return int(real_size * 1.045)
        elif 250000 < real_size <= 300000:
            return int(real_size * 1.035)
        elif 300000 < real_size <= 600000:
            return int(real_size * 1.03)
        elif 600000 < real_size <= 1000000:
            return int(real_size * 1.015)
        elif 1000000 < real_size <= 1800000:
            return int(real_size * 1.009)
        elif 1800000 < real_size <= 4500000:
            return int(real_size * 1.005)
        elif 4500000 < real_size <= 6000000:
            return int(real_size * 1.002)
        else:
            return int(real_size * 1.0015)
    else:
        if real_size < 500:
            return real_size * 7
        elif 500 < real_size <= 750:
            return real_size * 4
        elif 750 < real_size <= 2000:
            return real_size * 3
        elif 2000 < real_size <= 400000:
            return int(real_size * 1.75)
        elif 400000 < real_size <= 600000:
            return int(real_size * 1.7)
        elif 600000 < real_size <= 1500000:
            return int(real_size * 1.6)
        elif 1500000 < real_size <= 3000000:
            return int(real_size * 1.5)
        else:
            return int(real_size * 1.25)


def guess_aamp_size(file: Union[Path, bytes], ext: str = '') -> int:
    if isinstance(file, bytes):
        real_size = len(file)
        del file
    else:
        if file.suffix.startswith('.s'):
            with file.open('rb') as f:
                real_size = syaz0.get_header(f.read(16)).uncompressed_size
        else:
            real_size = file.stat().st_size
    if ext == '':
        if isinstance(file, Path):
            ext = file.suffix
        else:
            raise ValueError('AAMP extension must not be blank if passing file as bytes.')
    ext = ext.replace('.s', '.')
    if ext == '.baiprog':
        if real_size <= 380:
            return real_size * 7
        elif 380 < real_size <= 400:
            return real_size * 6
        elif 400 < real_size <= 450:
            return int(real_size * 5.5)
        elif 450 < real_size <= 600:
            return real_size * 5
        elif 600 < real_size <= 1000:
            return real_size * 4
        elif 1000 < real_size <= 1750:
            return int(real_size * 3.5)
        else:
            return real_size * 3
    elif ext == '.bgparamlist':
        if real_size <= 100:
            return real_size * 20
        elif 100 < real_size <= 150:
            return real_size * 12
        elif 150 < real_size <= 250:
            return real_size * 10
        elif 250 < real_size <= 350:
            return real_size * 8
        elif 350 < real_size <= 450:
            return real_size * 7
        else:
            return real_size * 6
    elif ext == '.bdrop':
        if real_size < 200:
            return int(real_size * 8.5)
        elif 200 < real_size <= 250:
            return real_size * 7
        elif 250 < real_size <= 350:
            return real_size * 6
        elif 350 < real_size <= 450:
            return int(real_size * 5.25)
        elif 450 < real_size <= 850:
            return int(real_size * 4.5)
        else:
            return real_size * 4
    elif ext == '.bxml':
        if real_size < 350:
            return real_size * 6
        elif 350 < real_size <= 450:
            return real_size * 5
        elif 450 < real_size <= 550:
            return int(real_size * 4.5)
        elif 550 < real_size <= 650:
            return real_size * 4
        elif 650 < real_size <= 800:
            return int(real_size * 3.5)
        else:
            return real_size * 3
    elif ext == '.brecipe':
        if real_size < 100:
            return int(real_size * 12.5)
        elif 100 < real_size <= 160:
            return int(real_size * 8.5)
        elif 160 < real_size <= 200:
            return int(real_size * 7.5)
        elif 200 < real_size <= 215:
            return real_size * 7
        else:
            return int(real_size * 6.5)
    elif ext == '.bshop':
        if real_size < 200:
            return int(real_size * 7.25)
        elif 200 < real_size <= 400:
            return real_size * 6
        elif 400 < real_size <= 500:
            return real_size * 5
        else:
            return int(real_size * 4.05)
    elif ext == '.bas':
        real_size = int(1.05 * real_size)
        if real_size < 100:
            return real_size * 20
        elif 100 < real_size <= 200:
            return int(real_size * 12.5)
        elif 200 < real_size <= 300:
            return real_size * 10
        elif 300 < real_size <= 600:
            return real_size * 8
        elif 600 < real_size <= 1500:
            return real_size * 6
        elif 1500 < real_size <= 2000:
            return int(real_size * 5.5)
        elif 2000 < real_size <= 15000:
            return real_size * 5
        else:
            return int(real_size * 4.5)
    elif ext == '.baslist':
        real_size = int(1.05 * real_size)
        if real_size < 100:
            return real_size * 15
        elif 100 < real_size <= 200:
            return real_size * 10
        elif 200 < real_size <= 300:
            return real_size * 8
        elif 300 < real_size <= 500:
            return real_size * 6
        elif 500 < real_size <= 800:
            return real_size * 5
        elif 800 < real_size <= 4000:
            return real_size * 4
        else:
            return int(real_size * 3.5)
    elif ext == '.bdmgparam':
        return int(((-0.0018 * real_size) + 6.6273) * real_size) + 500
    else:
        return 0


def get_mod_rstb_values(mod: Union[Path, str, BcmlMod], log_name: str = 'rstb.log') -> {}:
    """ Gets all of the RSTB values for a given mod """
    path = mod if isinstance(mod, Path) else Path(
        mod) if isinstance(mod, str) else mod.path
    changes = {}
    leave = (path / 'logs' / '.leave').exists()
    shrink = (path / 'logs' / '.shrink').exists()
    with (path / 'logs' / log_name).open('r') as l_file:
        log_loop = csv.reader(l_file)
        for row in log_loop:
            if row[0] != 'name':
                changes[row[0]] = {
                    'size': row[1],
                    'leave': leave,
                    'shrink': shrink
                }
    return changes


def merge_rstb(table: ResourceSizeTable, changes: dict) -> (ResourceSizeTable, List[str]):
    """
    Merges changes from a list of RSTB mods into a single RSTB

    :param table: The base RSTB to merge into. This will be directly modified.
    :type table: class:`rstb.ResourceSizeTable`
    :param changes: A dict of resources and their RSTB sizes.
    :type changes: dict of str: int
    :param verbose: Whether to log changes in full detail. Defaults to false.
    :type verbose: bool, optional
    :returns: Returns a list of strings recording RSTB changes made.
    :rtype: list of str
    """
    change_list = []
    spaces = '  '
    change_count = {
        'updated': 0,
        'deleted': 0,
        'added': 0,
        'warning': 0
    }
    for change in changes:
        if zlib.crc32(change.encode()) in table.crc32_map:
            newsize = int(changes[change]['size'])
            if newsize == 0:
                if not changes[change]['leave']:
                    if change.endswith('.bas') or change.endswith('.baslist'):
                        change_list.append((
                            f'{spaces}WARNING: Could not calculate or safely remove RSTB size for'
                            f'{change}. This may need to be corrected manually, or the game could '
                            'become unstable',
                            False
                        ))
                        change_count['warning'] += 1
                        continue
                    else:
                        table.delete_entry(change)
                        change_list.append(
                            (f'{spaces}Deleted RSTB entry for {change}', True))
                        change_count['deleted'] += 1
                        continue
                else:
                    change_list.append(
                        (f'{spaces}Skipped deleting RSTB entry for {change}', True))
                    continue
            oldsize = table.get_size(change)
            if newsize <= oldsize:
                if changes[change]['shrink']:
                    table.set_size(change, newsize)
                    change_list.append((
                        f'{spaces}Updated RSTB entry for {change} from {oldsize} to {newsize}',
                        True
                    ))
                    change_count['updated'] += 1
                    continue
                else:
                    change_list.append(
                        (f'{spaces}Skipped updating RSTB entry for {change}', True))
                    continue
            elif newsize > oldsize:
                table.set_size(change, newsize)
                change_list.append(
                    (f'{spaces}Updated RSTB entry for {change} from {oldsize} to {newsize}', True))
                change_count['updated'] += 1
        else:
            newsize = int(changes[change]['size'])
            if newsize == 0:
                change_list.append(
                    (f'{spaces}Could not calculate size for new entry {change}, skipped', True))
                continue
            table.set_size(change, newsize)
            change_list.append(
                (f'{spaces}Added new RSTB entry for {change} with value {newsize}', True))
            change_count['added'] += 1
    change_list.append((
        f'RSTB merge complete: updated {change_count["updated"]} entries, deleted'
        f' {change_count["deleted"]} entries, added {change_count["added"]} entries',
        False
    ))
    return table, change_list


def _get_sizes_in_sarc(file: Union[Path, sarc.SARC]) -> {}:
    calc = rstb.SizeCalculator()
    sizes = {}
    guess = util.get_settings_bool('guess_merge')
    if isinstance(file, Path):
        with file.open('rb') as s_file:
            file = sarc.read_file_and_make_sarc(s_file)
        if not file:
            return {}
    for nest_file in file.list_files():
        canon = nest_file.replace('.s', '.')
        data = util.unyaz_if_needed(file.get_file_data(nest_file).tobytes())
        ext = Path(canon).suffix
        if util.is_file_modded(canon, data) and ext not in RSTB_EXCLUDE_EXTS and canon not in RSTB_EXCLUDE_NAMES:
            size = calc.calculate_file_size_with_ext(
                data,
                wiiu=True,
                ext=ext
            )
            if ext == '.bdmgparam':
                size = 0
            if size == 0 and guess:
                if ext in util.AAMP_EXTS:
                    size = guess_aamp_size(data, ext)
                elif ext in ['.bfres', '.sbfres']:
                    size = guess_bfres_size(data, canon)
            sizes[canon] = size
            if util.is_file_sarc(nest_file) and not nest_file.endswith('.ssarc'):
                try:
                    nest_sarc = sarc.SARC(data)
                except ValueError:
                    continue
                sizes.update(_get_sizes_in_sarc(nest_sarc))
    return sizes


def log_merged_files_rstb():
    """ Generates an RSTB log for the master BCML modpack containing merged files """
    print('Updating RSTB for merged files...')
    diffs = {}
    files = [item for item in util.get_master_modpack_dir().rglob('**/*') if item.is_file()]
    guess = util.get_settings_bool('guess_merge')
    for file in files:
        if file.parent == 'logs':
            continue
        if file.suffix not in RSTB_EXCLUDE_EXTS and file.name not in RSTB_EXCLUDE_NAMES:
            size = calculate_size(file)
            if size == 0 and guess:
                if file.suffix in util.AAMP_EXTS:
                    size = guess_aamp_size(file)
                elif file.suffix in ['.bfres', '.sbfres']:
                    size = guess_bfres_size(file)
            canon = util.get_canon_name(file.relative_to(util.get_master_modpack_dir()))
            if canon:
                diffs[canon] = size
    sarc_files = [file for file in files if util.is_file_sarc(str(file)) \
                  and file.suffix != '.ssarc']
    if sarc_files:
        num_threads = min(multiprocessing.cpu_count(), len(sarc_files))
        pool = multiprocessing.Pool(processes=num_threads)
        results = pool.map(_get_sizes_in_sarc, sarc_files)
        pool.close()
        pool.join()
        for result in results:
            diffs.update(result)
    with (util.get_master_modpack_dir() / 'logs' / 'rstb.log').open('w', encoding='utf-8') as log:
        log.write('name,size,path\n')
        for canon, size in diffs.items():
            log.write(f'{canon},{size},//\n')

def generate_master_rstb(verbose: bool = False):
    """Merges all installed RSTB modifications"""
    print('Merging RSTB changes...')
    if (util.get_master_modpack_dir() / 'logs' / 'master-rstb.log').exists():
        (util.get_master_modpack_dir() / 'logs' / 'master-rstb.log').unlink()

    table = get_stock_rstb()
    rstb_values = {}
    for mod in util.get_installed_mods():
        rstb_values.update(get_mod_rstb_values(mod))
    if (util.get_master_modpack_dir() / 'logs' / 'rstb.log').exists():
        rstb_values.update(get_mod_rstb_values(util.get_master_modpack_dir()))
    if (util.get_master_modpack_dir() / 'logs' / 'map.log').exists():
        rstb_values.update(get_mod_rstb_values(
            util.get_master_modpack_dir(), log_name='map.log'))

    table, rstb_changes = merge_rstb(table, rstb_values)
    for change in rstb_changes:
        if not change[1] or (change[1] and verbose):
            print(change[0])

    for bootup_pack in util.get_master_modpack_dir().glob('content/Pack/Bootup_*.pack'):
        lang = util.get_file_language(bootup_pack)
        if table.is_in_table(f'Message/Msg_{lang}.product.sarc'):
            table.delete_entry(f'Message/Msg_{lang}.product.sarc')

    rstb_path = util.get_master_modpack_dir() / 'content' / 'System' / 'Resource' / \
                                                'ResourceSizeTable.product.srsizetable'
    if not rstb_path.exists():
        rstb_path.parent.mkdir(parents=True, exist_ok=True)
    with rstb_path.open('wb') as r_file:
        with io.BytesIO() as buf:
            table.write(buf, True)
            r_file.write(util.compress(buf.getvalue()))

    rstb_log = util.get_master_modpack_dir() / 'logs' / 'master-rstb.log'
    rstb_log.parent.mkdir(parents=True, exist_ok=True)
    with rstb_log.open('w', encoding='utf-8') as r_file:
        r_file.write('\n'.join([change[0].strip() for change in rstb_changes]))


class RstbMerger(mergers.Merger):
    """ A merger for the ResourceSizeTable.product.srsizetable """
    NAME: str = 'rstb'

    def __init__(self, guess: bool = False, leave: bool = False, shrink: bool = False):
        super().__init__('RSTB merge', 'Merges changes to ResourceSizeTable.product.srsizetable',
                         'rstb.log')
        self._options = {
            'guess': guess,
            'leave': leave,
            'shrink': shrink
        }

    def generate_diff(self, mod_dir: Path, modded_files: List[Path]):
        rstb_diff = {}
        open_sarcs = {}
        for file in modded_files:
            if isinstance(file, Path):
                canon = util.get_canon_name(file.relative_to(mod_dir).as_posix())
                if Path(canon).suffix not in RSTB_EXCLUDE_EXTS and\
                Path(canon).name not in RSTB_EXCLUDE_NAMES:
                    size = calculate_size(file)
                    if file.suffix == '.bdmgparam':
                        size = 0
                    if size == 0 and self._options['guess']:
                        if file.suffix in util.AAMP_EXTS:
                            size = guess_aamp_size(file)
                        elif file.suffix in ['.bfres', '.sbfres']:
                            size = guess_bfres_size(file)
                    rstb_diff[file] = size
            elif isinstance(file, str):
                parts = file.split('//')
                name = parts[-1]
                if parts[0] not in open_sarcs:
                    with (mod_dir / parts[0]).open('rb') as s_file:
                        open_sarcs[parts[0]] = sarc.read_file_and_make_sarc(s_file)
                for part in parts[1:-1]:
                    if part not in open_sarcs:
                        open_sarcs[part] = sarc.SARC(
                            util.unyaz_if_needed(
                                open_sarcs[parts[parts.index(part) - 1]]\
                                    .get_file_data(part).tobytes()
                            )
                        )
                ext = Path(name).suffix
                data = util.unyaz_if_needed(open_sarcs[parts[-2]].get_file_data(name).tobytes())
                rstb_val = rstb.SizeCalculator().calculate_file_size_with_ext(
                    data,
                    wiiu=True,
                    ext=ext
                )
                if ext == '.bdmgparam':
                    rstb_val = 0
                if rstb_val == 0 and self._options['guess']:
                    if ext in util.AAMP_EXTS:
                        rstb_val = guess_aamp_size(data, ext)
                    elif ext in ['.bfres', '.sbfres']:
                        rstb_val = guess_bfres_size(data, name)
                rstb_diff[file] = rstb_val
        for open_sarc in open_sarcs:
            del open_sarc
        return rstb_diff

    def log_diff(self, mod_dir: Path, diff_material: Union[dict, List[Path]]):
        diffs = {}
        if isinstance(diff_material, dict):
            diffs = diff_material
        elif isinstance(diff_material, List):
            diffs = self.generate_diff(mod_dir, diff_material)

        log_path = mod_dir / 'logs' / self._log_name
        with log_path.open('w', encoding='utf-8') as log:
            log.write('name,rstb,path\n')
            for diff, value in diffs.items():
                ext = Path(diff).suffix
                if isinstance(diff, Path):
                    canon = util.get_canon_name(str(diff.relative_to(mod_dir)))
                    path = diff.relative_to(mod_dir).as_posix()
                elif isinstance(diff, str):
                    canon = diff.split('//')[-1].replace('.s', '.')
                    path = diff
                if ext not in RSTB_EXCLUDE_EXTS and canon not in RSTB_EXCLUDE_NAMES:
                    log.write(f'{canon},{value},{path}\n')

        if 'leave' in self._options and self._options['leave']:
            (mod_dir / 'logs' / '.leave').write_bytes(b'')
        if 'shrink' in self._options and self._options['shrink']:
            (mod_dir / 'logs' / '.shrink').write_bytes(b'')

    def get_mod_diff(self, mod: util.BcmlMod):
        if not self._options:
            self._options['leave'] = (mod.path / 'logs' / '.leave').exists()
            self._options['shrink'] = (mod.path / 'logs' / '.shrink').exists()

        diffs = {}
        log_path = mod.path / 'logs' / self._log_name
        stock_rstb = get_stock_rstb()
        with log_path.open('r', encoding='utf-8') as log:
            for line in log.readlines()[1:]:
                row = line.split(',')
                name = row[0]
                try:
                    size = int(row[1])
                except ValueError:
                    size = int(float(row[1]))
                old_size = 0
                if stock_rstb.is_in_table(name):
                    old_size = stock_rstb.get_size(name)
                if (size == 0 and self._options['leave']) or \
                   (size < old_size and self._options['shrink']):
                    continue
                diffs[row[0]] = size
        return diffs

    def get_all_diffs(self):
        diffs = []
        for mod in util.get_installed_mods():
            diffs.append(self.get_mod_diff(mod))
        return diffs

    def consolidate_diffs(self, diffs: List[dict]):
        all_diffs = {}
        for diff in diffs:
            all_diffs.update(diff)
        return all_diffs

    def get_checkbox_options(self) -> List[tuple]:
        return [
            ('leave', 'Don\'t remove RSTB entries for complex file types'),
            ('shrink', 'Shrink RSTB values when smaller than the base game'),
            ('guess', 'Attempt to estimate RSTB values for AAMP and BFRES files'),
        ]

    def perform_merge(self):
        print('Perfoming RSTB merge...')
        log_merged_files_rstb()
        generate_master_rstb()

    def perform_merge_2(self):
        print('Perfoming RSTB merge...')
        log_merged_files_rstb()
        master_diffs = [
            *self.get_all_diffs(),
            self.get_mod_diff(BcmlMod('Master BCML', 9999, util.get_master_modpack_dir()))
        ]
        diffs = self.consolidate_diffs(master_diffs)
        new_rstb = get_stock_rstb()
        counts = {
            'add': 0,
            'update': 0,
            'del': 0
        }
        for file, size in diffs.items():
            if size > 0:
                if new_rstb.is_in_table(file):
                    counts['update'] += 1
                else:
                    counts['add'] += 1
                new_rstb.set_size(file, size)
            else:
                if new_rstb.is_in_table(file):
                    new_rstb.delete_entry(file)
                    counts['del'] += 1
        rstb_path = util.get_master_modpack_dir() / 'content' / 'System' / 'Resource' /\
                    'ResourceSizeTable.product.srsizetable'
        if not rstb_path.exists():
            rstb_path.parent.mkdir(parents=True, exist_ok=True)
        buf = io.BytesIO()
        new_rstb.write(buf, be=True)
        rstb_path.write_bytes(util.compress(buf.getvalue()))
        print(
            f'RSTB merge complete: updated {counts["update"]} entries, '
            f'added {counts["add"]} entries, deleted {counts["del"]} entries'
        )
