"""
Provides functions to diff and merge various kinds of BotW data, including gamedata, savedata, and
actorinfo.
"""
# Copyright 2019 Nicene Nerd <macadamiadaze@gmail.com>
# Licensed under GPLv3+
import zlib
from copy import deepcopy
from io import BytesIO
from math import ceil
from pathlib import Path
from typing import List

import byml
from byml import yaml_util
import rstb
import rstb.util
import sarc
import wszst_yaz0
import xxhash
import yaml

from bcml import util
from bcml.util import BcmlMod


def get_stock_gamedata() -> sarc.SARC:
    """ Gets the contents of the unmodded gamedata.sarc """
    if not hasattr(get_stock_gamedata, 'gamedata'):
        with util.get_game_file('Pack/Bootup.pack').open('rb') as b_file:
            bootup = sarc.read_file_and_make_sarc(b_file)
        get_stock_gamedata.gamedata = sarc.SARC(wszst_yaz0.decompress(
            bootup.get_file_data('GameData/gamedata.ssarc')))
    return get_stock_gamedata.gamedata


def get_stock_savedata() -> sarc.SARC:
    """ Gets the contents of the unmodded savedataformat.sarc """
    if not hasattr(get_stock_savedata, 'savedata'):
        with util.get_game_file('Pack/Bootup.pack').open('rb') as b_file:
            bootup = sarc.read_file_and_make_sarc(b_file)
        get_stock_savedata.savedata = sarc.SARC(wszst_yaz0.decompress(
            bootup.get_file_data('GameData/savedataformat.ssarc')
        ))
    return get_stock_savedata.savedata


def get_gamedata_hashes() -> {}:
    """ Gets a hash table for the unmodded contents of gamedata.sarc """
    if not hasattr(get_gamedata_hashes, 'gamedata_hashes'):
        get_gamedata_hashes.gamedata_hashes = {}
        gamedata = get_stock_gamedata()
        for file in gamedata.list_files():
            get_gamedata_hashes.gamedata_hashes[file] = xxhash.xxh32(
                gamedata.get_file_data(file)).hexdigest()
    return get_gamedata_hashes.gamedata_hashes


def get_savedata_hashes() -> {}:
    """ Gets a hash table for the unmodded contents of savedataformat.sarc """
    if not hasattr(get_savedata_hashes, 'savedata_hashes'):
        get_savedata_hashes.savedata_hashes = {}
        savedata = get_stock_savedata()
        for file in savedata.list_files():
            get_savedata_hashes.savedata_hashes[file] = xxhash.xxh32(
                savedata.get_file_data(file)).hexdigest()
    return get_savedata_hashes.savedata_hashes


def inject_gamedata_into_bootup(bgdata: sarc.SARCWriter, bootup_path: Path = None) -> int:
    """
    Packs a gamedata SARC into Bootup.pack and returns the RSTB size of the new gamedata.sarc

    :param bgdata: A SARCWriter for the new gamedata
    :type bgdata: :class:`sarc.SARCWriter`
    :param bootup_path: Path to the Bootup.pack to update, defaults to a master BCML copy
    :type bootup_path: :class:`pathlib.Path`, optional
    :returns: Returns the RSTB size of the new gamedata.sarc
    :rtype: int
    """
    if not bootup_path:
        master_boot = util.get_master_modpack_dir() / 'content' / 'Pack' / 'Bootup.pack'
        bootup_path = master_boot if master_boot.exists() \
            else util.get_game_file('Pack/Bootup.pack')
    with bootup_path.open('rb') as b_file:
        bootup_pack = sarc.read_file_and_make_sarc(b_file)
    new_pack = sarc.make_writer_from_sarc(bootup_pack)
    new_pack.delete_file('GameData/gamedata.ssarc')
    gamedata_bytes = bgdata.get_bytes()
    new_pack.add_file('GameData/gamedata.ssarc',
                      wszst_yaz0.compress(gamedata_bytes))
    (util.get_master_modpack_dir() / 'content' /
     'Pack').mkdir(parents=True, exist_ok=True)
    with (util.get_master_modpack_dir() / 'content' / 'Pack' / 'Bootup.pack').open('wb') as b_file:
        new_pack.write(b_file)
    return rstb.SizeCalculator().calculate_file_size_with_ext(gamedata_bytes, True, '.sarc')


def inject_savedata_into_bootup(bgsvdata: sarc.SARCWriter, bootup_path: Path = None) -> int:
    """
    Packs a savedata SARC into Bootup.pack and returns the RSTB size of the new savedataformat.sarc

    :param bgsvdata: A SARCWriter for the new savedata
    :type bgsvdata: :class:`sarc.SARCWriter`
    :param bootup_path: Path to the Bootup.pack to update, defaults to a master BCML copy
    :type bootup_path: :class:`pathlib.Path`, optional
    :returns: Returns the RSTB size of the new savedataformat.sarc
    :rtype: int
    """
    if not bootup_path:
        installed_bootups = list(
            util.get_modpack_dir().rglob('**/Pack/Bootup.pack'))
        bootup_path = installed_bootups[len(installed_bootups) - 1] if installed_bootups \
                      else util.get_game_file('Pack/Bootup.pack')
    with bootup_path.open('rb') as b_file:
        bootup_pack = sarc.read_file_and_make_sarc(b_file)
    new_pack = sarc.make_writer_from_sarc(bootup_pack)
    new_pack.delete_file('GameData/savedataformat.ssarc')
    savedata_bytes = bgsvdata.get_bytes()
    new_pack.add_file('GameData/savedataformat.ssarc',
                      wszst_yaz0.compress(savedata_bytes))
    with (util.get_master_modpack_dir() / 'content' / 'Pack' / 'Bootup.pack').open('wb') as b_file:
        new_pack.write(b_file)
    return rstb.SizeCalculator().calculate_file_size_with_ext(savedata_bytes, True, '.sarc')


def get_modded_bgdata(gamedata: sarc.SARC) -> {}:
    """
    Gets all modded .bgdata files in a gamedata.sarc and their contents

    :returns: Returns a dictionary of modified files with their modded and (if applicable)
    original contents loaded from YAML.
    :rtype: dict of str: dict of str: Union[list, dict]
    """
    hashes = get_gamedata_hashes()
    modded_files = {}
    ref_gdata = get_stock_gamedata()
    bg_files = list(gamedata.list_files())
    # To anyone trying to understand a lot of what's going on here:
    # .bgdata files in gamedata.sarc are *supposed* to be stored with a
    # leading slash (e.g. "/bool_data_0.bgdata"), but sometimes they are
    # repacked without them (e.g. "bool_data_0.bgdata"). So much of the
    # weirdness here is trying to account for both possibilities.
    fix_slash = '/' if not bg_files[0].startswith('/') else ''
    single_gamedatas = [file for file in bg_files
                        if not any(file.startswith(mult) for mult in
                                   [
                                       '/bool_data',
                                       'bool_data',
                                       '/revival_bool_data',
                                       'revival_bool_data'
                                   ])]
    for bgdata in single_gamedatas:
        bgdata_bytes = gamedata.get_file_data(bgdata).tobytes()
        bgdata_hash = xxhash.xxh32(bgdata_bytes).hexdigest()
        if fix_slash + bgdata not in hashes or bgdata_hash != hashes[fix_slash + bgdata]:
            modded_files[fix_slash + bgdata] = {
                'mod_yml': byml.Byml(bgdata_bytes).parse()
            }
            if fix_slash + bgdata in list(ref_gdata.list_files()):
                modded_files[fix_slash + bgdata]['ref_yml'] = byml.Byml(
                    ref_gdata.get_file_data(fix_slash + bgdata).tobytes()
                ).parse()
    bool_datas = [file for file in bg_files if file.startswith(
        '/bool_data') or file.startswith('bool_data')]
    bool_data_bytes = {}
    bool_data_modded = False
    for bool_data in bool_datas:
        bgdata_bytes = gamedata.get_file_data(bool_data).tobytes()
        bool_data_bytes[bool_data] = bgdata_bytes
        if not bool_data_modded:
            bool_data_modded = (fix_slash + bool_data) not in hashes \
                or hashes[fix_slash + bool_data] != xxhash.xxh32(bgdata_bytes).hexdigest()
    if bool_data_modded:
        for bool_data in bool_datas:
            modded_files[fix_slash + bool_data] = {
                'mod_yml': byml.Byml(bool_data_bytes[bool_data]).parse()
            }
            if fix_slash + bool_data in list(ref_gdata.list_files()):
                modded_files[fix_slash + bool_data]['ref_yml'] = byml.Byml(
                    ref_gdata.get_file_data(fix_slash + bool_data).tobytes()
                ).parse()
    revival_datas = [file for file in bg_files if file.startswith('/revival_bool_data')
                     or file.startswith('revival_bool_data')]
    revival_data_bytes = {}
    revival_data_modded = False
    for revival_data in revival_datas:
        bgdata_bytes = gamedata.get_file_data(revival_data).tobytes()
        revival_data_bytes[revival_data] = bgdata_bytes
        if not revival_data_modded:
            revival_data_modded = (fix_slash + revival_data) not in hashes \
                or hashes[fix_slash + revival_data] != xxhash.xxh32(bgdata_bytes).hexdigest()
    if revival_data_modded:
        for revival_data in revival_datas:
            modded_files[fix_slash + revival_data] = {
                'mod_yml': byml.Byml(revival_data_bytes[revival_data]).parse()
            }
            if fix_slash + revival_data in list(ref_gdata.list_files()):
                modded_files[fix_slash + revival_data]['ref_yml'] = byml.Byml(
                    ref_gdata.get_file_data(fix_slash + revival_data).tobytes()
                ).parse()
    return modded_files


def is_savedata_modded(savedata: sarc.SARC) -> {}:
    """
    Detects if any .bgsvdata file has been modified.

    :param savedata: The saveformatdata.sarc to check for modification.
    :type savedata: :class:`sarc.SARC`
    :returns: Returns True if any .bgsvdata in the given savedataformat.sarc has been modified.
    :rtype: bool
    """
    hashes = get_savedata_hashes()
    sv_files = sorted(savedata.list_files())
    fix_slash = '/' if not sv_files[0].startswith('/') else ''
    modded = False
    for svdata in sv_files[0:-2]:
        svdata_bytes = savedata.get_file_data(svdata).tobytes()
        svdata_hash = xxhash.xxh32(svdata_bytes).hexdigest()
        del svdata_bytes
        if not modded:
            modded = fix_slash + \
                svdata not in hashes or svdata_hash != hashes[fix_slash + svdata]
    return modded


def get_modded_gamedata_entries(modded_bgdata: dict) -> {}:
    """
    Gets all of the modified gamedata entries in a dict of modded gamedata contents.

    :param modded_bgdata: A dict of modified .bgdata files and their contents.
    :type modded_bgdata: dict
    :returns: Returns a dictionary with each data type and the modified entries for it.
    :rtype: dict of str: dict of str: dict
    """
    ref_data = {}
    mod_data = {}
    for bgdata in modded_bgdata:
        key = bgdata.split('.')[0][1:] if 'revival' not in bgdata else 'bool_data'
        mod_yml = modded_bgdata[bgdata]['mod_yml']
        if key not in mod_yml:
            if f'/{key}' in mod_yml:
                key = f'/{key}'
            else:
                continue
        if key not in mod_data:
            mod_data[key] = {}
        for data in mod_yml[key]:
            mod_data[key][data['DataName']] = data
        if 'ref_yml' in modded_bgdata[bgdata]:
            ref_yml = modded_bgdata[bgdata]['ref_yml']
            if key not in ref_data:
                ref_data[key] = {}
            for data in ref_yml[key]:
                ref_data[key][data['DataName']] = data
    modded_entries = {}
    for data_type in mod_data:
        modded_entries[data_type] = {}
        for data in mod_data[data_type]:
            if data not in ref_data[data_type] or\
               mod_data[data_type][data] != ref_data[data_type][data]:
                modded_entries[data_type][data] = deepcopy(
                    mod_data[data_type][data])
    return modded_entries


def get_modded_savedata_entries(savedata: sarc.SARC) -> []:
    """
    Gets all of the modified savedata entries in a dict of modded savedata contents.

    :param savedata: The saveformatdata.sarc to search for modded entries.
    :type savedata: :class:`sarc.SARC`
    :return: Returns a list of modified savedata entries.
    :rtype: list
    """
    ref_savedata = get_stock_savedata()
    ref_hashes = []
    new_entries = []
    for file in sorted(ref_savedata.list_files())[0:-2]:
        for item in byml.Byml(ref_savedata.get_file_data(file).tobytes()).parse()['file_list'][1]:
            ref_hashes.append(item['HashValue'])
    for file in sorted(savedata.list_files())[0:-2]:
        for item in byml.Byml(savedata.get_file_data(file).tobytes()).parse()['file_list'][1]:
            if item['HashValue'] not in ref_hashes:
                new_entries.append(item)
    return new_entries


def get_gamedata_mods() -> List[BcmlMod]:
    """ Gets a list of all installed mods that modify gamedata """
    gdata_mods = [mod for mod in util.get_installed_mods() if (
        mod.path / 'logs' / 'gamedata.yml').exists()]
    return sorted(gdata_mods, key=lambda mod: mod.priority)


def get_savedata_mods() -> List[BcmlMod]:
    """ Gets a list of all installed mods that modify save data """
    sdata_mods = [mod for mod in util.get_installed_mods() if (
        mod.path / 'logs' / 'savedata.yml').exists()]
    return sorted(sdata_mods, key=lambda mod: mod.priority)


def merge_gamedata(verbose: bool = False):
    """ Merges installed gamedata mods and saves the new Bootup.pack, fixing the RSTB if needed """
    mods = get_gamedata_mods()
    glog_path = util.get_master_modpack_dir() / 'logs' / 'gamedata.log'
    if not mods:
        print('No gamedata merging necessary.')
        if glog_path.exists():
            glog_path.unlink()
            (util.get_master_modpack_dir() / 'logs' / 'gamedata.sarc').unlink()
        return
    if glog_path.exists():
        with glog_path.open('r') as l_file:
            if xxhash.xxh32(str(mods)).hexdigest() == l_file.read():
                print('No gamedata merging necessary.')
                return

    modded_entries = {}
    loader = yaml.CSafeLoader
    yaml_util.add_constructors(loader)
    print('Loading gamedata mods...')
    for mod in mods:
        with open(mod.path / 'logs' / 'gamedata.yml') as g_file:
            yml = yaml.load(g_file, Loader=loader)
            for data_type in yml:
                if data_type not in modded_entries:
                    modded_entries[data_type] = {}
                modded_entries[data_type].update(yml[data_type])
                if verbose:
                    print(f'  Added entries for {data_type} from {mod.name}')

    gamedata = get_stock_gamedata()
    merged_entries = {}

    print('Loading stock gamedata...')
    for yml in gamedata.list_files():
        base_yml = byml.Byml(gamedata.get_file_data(yml).tobytes()).parse()
        for data_type in base_yml:
            if data_type not in merged_entries:
                merged_entries[data_type] = []
            merged_entries[data_type].extend(base_yml[data_type])

    print('Merging changes...')
    for data_type in merged_entries:
        if data_type in modded_entries:
            for entry in [entry for entry in merged_entries[data_type]
                          if entry['DataName'] in modded_entries[data_type]]:
                i = merged_entries[data_type].index(entry)
                if verbose:
                    print(f'  {entry["DataName"]} has been modified')
                merged_entries[data_type][i] = deepcopy(
                    modded_entries[data_type][entry['DataName']])
            print(f'Merged modified {data_type} entries')

    for data_type in modded_entries:
        for entry in [entry for entry in modded_entries[data_type]
                      if entry not in [entry['DataName'] for entry in merged_entries[data_type]]]:
            if verbose:
                print(f'  {entry} has been added')
            merged_entries[data_type].append(modded_entries[data_type][entry])
        print(f'Merged new {data_type} entries')

    print('Creating and injecting new gamedata.sarc...')
    new_gamedata = sarc.SARCWriter(True)
    for data_type in merged_entries:
        num_files = ceil(len(merged_entries[data_type]) / 4096)
        for i in range(num_files):
            end_pos = (i+1) * 4096
            if end_pos > len(merged_entries[data_type]):
                end_pos = len(merged_entries[data_type])
            buf = BytesIO()
            byml.Writer(
                {data_type: merged_entries[data_type][i*4096:end_pos]}, be=True).write(buf)
            new_gamedata.add_file(f'/{data_type}_{i}.bgdata', buf.getvalue())
    bootup_rstb = inject_gamedata_into_bootup(new_gamedata)
    (util.get_master_modpack_dir() / 'logs').mkdir(parents=True, exist_ok=True)
    with (util.get_master_modpack_dir() / 'logs' / 'gamedata.sarc').open('wb') as g_file:
        new_gamedata.write(g_file)

    print('Correcting RSTB if necessary...')
    rstb_path = util.get_modpack_dir() / '9999_BCML' / 'content' / 'System' / 'Resource' /\
                                         'ResourceSizeTable.product.srsizetable'
    table = rstb.util.read_rstb(str(rstb_path), True)
    if table.is_in_table('GameData/gamedata.sarc'):
        old_size = table.get_size('GameData/gamedata.sarc')
        if bootup_rstb > old_size:
            table.set_size('GameData/gamedata.sarc', bootup_rstb)
            if verbose:
                print('  Updated RSTB entry for "GameData/gamedata.sarc"'
                      f'from {old_size} bytes to {bootup_rstb} bytes')
        rstb.util.write_rstb(table, str(rstb_path), True)

    glog_path.parent.mkdir(parents=True, exist_ok=True)
    with glog_path.open('w') as l_file:
        l_file.write(xxhash.xxh32(str(mods)).hexdigest())


def merge_savedata(verbose: bool = False):
    """ Merges install savedata mods and saves the new Bootup.pack, fixing the RSTB if needed"""
    mods = get_savedata_mods()
    slog_path = util.get_master_modpack_dir() / 'logs' / 'savedata.log'
    if not mods:
        print('No gamedata merging necessary.')
        if slog_path.exists():
            slog_path.unlink()
            (util.get_master_modpack_dir() / 'logs' / 'savedata.sarc').unlink()
        return
    if slog_path.exists():
        with slog_path.open('r') as l_file:
            if xxhash.xxh32(str(mods)).hexdigest() == l_file.read():
                print('No savedata merging necessary.')
                return

    new_entries = []
    new_hashes = []
    loader = yaml.CSafeLoader
    yaml_util.add_constructors(loader)
    print('Loading savedata mods...')
    for mod in mods:
        with open(mod.path / 'logs' / 'savedata.yml') as s_file:
            yml = yaml.load(s_file, Loader=loader)
            for entry in yml:
                if entry['HashValue'] in new_hashes:
                    continue
                else:
                    new_entries.append(entry)
                    new_hashes.append(entry['HashValue'])
                    if verbose:
                        print(f'  Added {entry["DataName"]} from {mod.name}')

    savedata = get_stock_savedata()
    merged_entries = []
    save_files = sorted(savedata.list_files())[0:-2]

    print('Loading stock savedata...')
    for file in save_files:
        merged_entries.extend(byml.Byml(savedata.get_file_data(
            file).tobytes()).parse()['file_list'][1])

    print('Merging changes...')
    merged_entries.extend(new_entries)
    merged_entries.sort(key=lambda x: x['HashValue'])

    special_bgsv = [
        savedata.get_file_data('/saveformat_6.bgsvdata').tobytes(),
        savedata.get_file_data('/saveformat_7.bgsvdata').tobytes(),
    ]

    print('Creating and injecting new savedataformat.sarc...')
    new_savedata = sarc.SARCWriter(True)
    num_files = ceil(len(merged_entries) / 8192)
    for i in range(num_files):
        end_pos = (i+1) * 8192
        if end_pos > len(merged_entries):
            end_pos = len(merged_entries)
        buf = BytesIO()
        byml.Writer({
            'file_list': [
                {
                    'IsCommon': False,
                    'IsCommonAtSameAccount': False,
                    'IsSaveSecureCode': True,
                    'file_name': 'game_data.sav'
                },
                merged_entries[i*8192:end_pos]
            ],
            'save_info': [
                {
                    'directory_num': byml.Int(8),
                    'is_build_machine': True,
                    'revision': byml.Int(18203)
                }
            ]
        }, True).write(buf)
        new_savedata.add_file(f'/saveformat_{i}.bgsvdata', buf.getvalue())
    new_savedata.add_file(f'/saveformat_{num_files}.bgsvdata', special_bgsv[0])
    new_savedata.add_file(
        f'/saveformat_{num_files + 1}.bgsvdata', special_bgsv[1])
    bootup_rstb = inject_savedata_into_bootup(new_savedata)
    (util.get_master_modpack_dir() / 'logs').mkdir(parents=True, exist_ok=True)
    with (util.get_master_modpack_dir() / 'logs' / 'savedata.sarc').open('wb') as s_file:
        new_savedata.write(s_file)

    print('Correcting RSTB if necessary...')
    rstb_path = util.get_modpack_dir() / '9999_BCML' / 'content' / 'System' / 'Resource' / \
                                         'ResourceSizeTable.product.srsizetable'
    table = rstb.util.read_rstb(str(rstb_path), True)
    if table.is_in_table('GameData/savedataformat.sarc'):
        old_size = table.get_size('GameData/savedataformat.sarc')
        if bootup_rstb > old_size:
            table.set_size('GameData/savedataformat.sarc', bootup_rstb)
            if verbose:
                print('  Updated RSTB entry for "GameData/savedataformat.sarc"'
                      f'from {old_size} bytes to {bootup_rstb} bytes')
        rstb.util.write_rstb(table, str(rstb_path), True)

    slog_path.parent.mkdir(parents=True, exist_ok=True)
    with slog_path.open('w') as l_file:
        l_file.write(xxhash.xxh32(str(mods)).hexdigest())


def get_stock_actorinfo() -> dict:
    """ Gets the unmodded contents of ActorInfo.product.sbyml """
    actorinfo = util.get_game_file('Actor/ActorInfo.product.sbyml')
    with actorinfo.open('rb') as a_file:
        return byml.Byml(wszst_yaz0.decompress(a_file.read())).parse()


def get_modded_actors(actorinfo: dict) -> dict:
    """
    Gets new or changed actors in modded ActorInfo data and their hashes

    :param actorinfo: A dict representing the contents of ActorInfo.product.sbyml
    :type actorinfo: dict
    :return: Returns a dict of actor hashes and their associated actor info
    :rtype: dict of int: dict
    """
    stock_actors = get_stock_actorinfo()
    modded_actors = {}
    for actor in actorinfo['Actors']:
        actor_hash = zlib.crc32(actor['name'].encode())
        if actor_hash not in stock_actors['Hashes']:
            modded_actors[actor_hash] = actor
        elif actor != stock_actors['Actors'][stock_actors['Hashes'].index(actor_hash)]:
            stock_actor = stock_actors['Actors'][stock_actors['Hashes'].index(
                actor_hash)]
            modded_actors[actor_hash] = {}
            for key, value in actor.items():
                if key not in stock_actor or value != stock_actor[key]:
                    modded_actors[actor_hash][key] = value
    return modded_actors


def get_actorinfo_mods() -> List[BcmlMod]:
    """ Gets a list of all installed mods that modify ActorInfo.product.sbyml """
    actor_mods = [util.get_mod_info(a_log.parent.parent / 'rules.txt')
                  for a_log in util.get_modpack_dir().rglob('logs/actorinfo.yml')]
    return sorted(actor_mods, key=lambda mod: mod.priority)


def merge_actorinfo(verbose: bool = False):
    """Merges installed changes to actor info"""
    mods = get_actorinfo_mods()
    actor_path = (util.get_master_modpack_dir() / 'content' /
                  'Actor' / 'ActorInfo.product.sbyml')
    if not mods:
        print('No actor info merging necessary.')
        if actor_path.exists():
            actor_path.unlink()
        return

    print('Loading modded actor info...')
    modded_actors = {}
    loader = yaml.CSafeLoader
    yaml_util.add_constructors(loader)
    for mod in mods:
        with (mod.path / 'logs' / 'actorinfo.yml').open('r', encoding='utf-8') as a_file:
            entries = yaml.load(a_file, Loader=loader)
            util.dict_merge(modded_actors, entries)
            if verbose:
                print(f'Loaded {len(entries)} entries from {mod.name}')
            del entries
    print('Loading unmodded actor info...')
    actorinfo = get_stock_actorinfo()

    print('Merging changes...')
    for actor_hash, actor_info in modded_actors.items():
        if actor_hash in actorinfo['Hashes']:
            idx = actorinfo['Hashes'].index(actor_hash)
            util.dict_merge(actorinfo['Actors'][idx],
                            actor_info, unique_lists=True)
            if verbose:
                print(f'  Updated entry for {actorinfo["Actors"][idx]}')
        else:
            actorinfo['Hashes'].append(actor_hash)
            actorinfo['Actors'].append(actor_info)
            if verbose:
                print(f'  Added entry for {actor_info["name"]}')

    print('Sorting new actor info...')
    actorinfo['Hashes'].sort()
    actorinfo['Hashes'] = list(map(lambda x: byml.Int(
        x) if x < 2147483648 else byml.UInt(x), actorinfo['Hashes']))
    actorinfo['Actors'].sort(
        key=lambda x: zlib.crc32(x['name'].encode('utf-8')))

    print('Saving new actor info...')
    buf = BytesIO()
    byml.Writer(actorinfo, True).write(buf)
    actor_path.parent.mkdir(parents=True, exist_ok=True)
    actor_path.write_bytes(wszst_yaz0.compress(buf.getvalue()))
    print('Actor info merged successfully')
