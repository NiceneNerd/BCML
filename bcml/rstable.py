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
from fnmatch import fnmatch
from pathlib import Path
from typing import List, Union

import rstb
from rstb import ResourceSizeTable
from rstb.util import read_rstb
import wszst_yaz0

from bcml import util, install
from bcml.util import BcmlMod


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
        wszst_yaz0.compress(buf.getvalue())
    )


def guess_bfres_size(file: Union[Path, bytes], name: str = '') -> int:
    """
    Attempts to estimate a proper RSTB value for a BFRES file

    :param file: The file to estimate, either as a path or bytes
    :type file: Union[class:`pathlib.Path`, bytes]
    :param name: The name of the file, needed when passing as bytes, defaults to ''
    :type name: str, optional
    :return: Returns an estimated RSTB value
    :rtype: int
    """
    real_bytes = file if isinstance(file, bytes) else file.read_bytes()
    if real_bytes[0:4] == b'Yaz0':
        real_bytes = wszst_yaz0.decompress(real_bytes)
    real_size = len(real_bytes)
    del real_bytes
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
    """
    Attempts to estimate a proper RSTB value for an AAMP file. Will only attempt for the following
    kinds: .baiprog, .bgparamlist, .bdrop, .bshop, .bxml, .brecipe, otherwise will return 0.

    :param file: The file to estimate, either as a path or bytes
    :type file: Union[class:`pathlib.Path`, bytes]
    :param name: The name of the file, needed when passing as bytes, defaults to ''
    :type name: str, optional
    :return: Returns an estimated RSTB value
    :rtype: int"""
    real_bytes = file if isinstance(file, bytes) else file.read_bytes()
    if real_bytes[0:4] == b'Yaz0':
        real_bytes = wszst_yaz0.decompress(real_bytes)
    real_size = len(real_bytes)
    del real_bytes
    if ext == '':
        if isinstance(file, Path):
            ext = file.suffix
        else:
            raise ValueError(
                'AAMP extension must not be blank if passing file as bytes.')
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


def log_merged_files_rstb():
    """ Generates an RSTB log for the master BCML modpack containing merged files """
    print('Updating RSTB...')
    modded_files = install.find_modded_files(util.get_master_modpack_dir())[0]
    sarc_files = [file for file in modded_files if util.is_file_sarc(file) if 'Bootup_' not in file]
    modded_sarc_files = {}
    if sarc_files:
        num_threads = min(len(sarc_files), multiprocessing.cpu_count())
        pool = multiprocessing.Pool(processes=num_threads)
        thread_sarc_search = partial(
            install.threaded_find_modded_sarc_files,
            modded_files=modded_files,
            tmp_dir=util.get_master_modpack_dir(),
            deep_merge=False,
            verbose=False
        )
        results = pool.map(thread_sarc_search, sarc_files)
        pool.close()
        pool.join()
        for result in results:
            modded_sarcs = result[0]
            if modded_sarcs:
                modded_sarc_files.update(modded_sarcs)
    (util.get_master_modpack_dir() / 'logs').mkdir(parents=True, exist_ok=True)
    with (util.get_master_modpack_dir() / 'logs' / 'rstb.log').open('w', encoding='utf-8') as log:
        log.write('name,rstb\n')
        modded_files.update(modded_sarc_files)
        for file in modded_files:
            ext = os.path.splitext(file)[1]
            if ext not in install.RSTB_EXCLUDE and 'ActorInfo' not in file:
                path = str(modded_files[file]["path"]).replace('\\', '/')
                log.write(f'{file},{modded_files[file]["rstb"]},{path}\n')


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

    for bootup_pack in util.get_modpack_dir().rglob('**/Bootup_*.pack'):
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
            r_file.write(wszst_yaz0.compress(buf.getvalue()))

    rstb_log = util.get_master_modpack_dir() / 'logs' / 'master-rstb.log'
    rstb_log.parent.mkdir(parents=True, exist_ok=True)
    with rstb_log.open('w', encoding='utf-8') as r_file:
        r_file.write('\n'.join([change[0].strip() for change in rstb_changes]))
