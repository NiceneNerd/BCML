import csv
import glob
import struct
import zlib
from copy import deepcopy
from pathlib import Path
from typing import List, Union

import rstb
from bcml import texts, util
from bcml.util import BcmlMod
from rstb import ResourceSizeTable
from rstb.util import read_rstb, write_rstb


def get_stock_rstb() -> rstb.ResourceSizeTable:
    """ Gets the unmodified RSTB """
    if not hasattr(get_stock_rstb, 'table'):
        get_stock_rstb.table = read_rstb(
            str(util.get_game_file('System/Resource/ResourceSizeTable.product.srsizetable')), True)
    return deepcopy(get_stock_rstb.table)


def calculate_size(path: Path) -> int:
    """
    Calculates the resource size value for the given file
    
    :returns: The proper RSTB value for the file if it can be calculated, otherwise 0.
    :rtype: int
    """
    try:
        return rstb.SizeCalculator().calculate_file_size(file_name=str(path), wiiu=True, force=False)
    except struct.error:
        return 0


def get_mod_rstb_values(mod: Union[Path, str, BcmlMod], log_name: str = 'rstb.log') -> {}:
    """ Gets all of the RSTB values for a given mod """
    path = mod if isinstance(mod, Path) else Path(mod) if isinstance(mod, str) else mod.path
    changes = {}
    leave = (path / 'logs' / '.leave').exists()
    shrink = (path / 'logs' / '.shrink').exists()
    with (path / 'logs' / log_name).open('r') as lf:
        log_loop = csv.reader(lf)
        for row in log_loop:
            if row[0] != 'name':
                changes[row[0]] = {
                    'size': row[1],
                    'leave': leave,
                    'shrink': shrink
                }
    return changes


def merge_rstb(table: ResourceSizeTable, changes: dict, verbose: bool = False) -> List[str]:
    """
    Merges changes from a list of RSTB mods into a single RSTB

    :param table: The base RSTB to merge into. This will be directly modified.
    :type table: :class:`rstb.ResourceSizeTable`
    :param changes: A dict of resources and their RSTB sizes.
    :type changes: dict of str: int
    :param verbose: Whether to log changes in full detail. Defaults to false.
    :type verbose: bool, optional
    :returns: Returns a list of strings recording RSTB changes made.
    :rtype: list of str
    """
    change_list = []
    d = '  '
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
                        change_list.append((f'{d}WARNING: Could not calculate or safely remove RSTB size for {change}. '
                                           'This may need to be corrected manually, or the game could become unstable',
                                            False))
                        change_count['warning'] += 1
                        continue
                    else:
                        table.delete_entry(change)
                        change_list.append((f'{d}Deleted RSTB entry for {change}', True))
                        change_count['deleted'] += 1
                        continue
                else:
                    change_list.append((f'{d}Skipped deleting RSTB entry for {change}', True))
                    continue
            oldsize = table.get_size(change)
            if newsize <= oldsize:
                if changes[change]['shrink']:
                    table.set_size(change, newsize)
                    change_list.append((f'{d}Updated RSTB entry for {change} from {oldsize} to {newsize}', True))
                    change_count['updated'] += 1
                    continue
                else:
                    change_list.append((f'{d}Skipped updating RSTB entry for {change}', True))
                    continue
            elif newsize > oldsize:
                table.set_size(change, newsize)
                change_list.append((f'{d}Updated RSTB entry for {change} from {oldsize} to {newsize}', True))
                change_count['updated'] += 1
        else:
            newsize = int(changes[change]['size'])
            if newsize == 0:
                change_list.append((f'{d}Could not calculate size for new entry {change}, skipped', True))
                continue
            table.set_size(change, newsize)
            change_list.append((f'{d}Added new RSTB entry for {change} with value {newsize}', True))
            change_count['added'] += 1
    change_list.append((f'RSTB merge complete: updated {change_count["updated"]} entries,'
                       f' deleted {change_count["deleted"]} entries, added {change_count["added"]} entries', False))
    return change_list


def generate_master_rstb(verbose: bool = False):
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
        rstb_values.update(get_mod_rstb_values(util.get_master_modpack_dir(), log_name='map.log'))

    rstb_changes = merge_rstb(table, rstb_values, verbose)
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
    write_rstb(table, str(rstb_path), True)

    rstb_log = util.get_master_modpack_dir() / 'logs' / 'master-rstb.log'
    rstb_log.parent.mkdir(parents=True, exist_ok=True)
    with rstb_log.open('w') as rf:
        rf.write('\n'.join([change[0].strip() for change in rstb_changes]))
