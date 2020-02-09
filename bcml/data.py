"""
Provides functions to diff and merge various kinds of BotW data, including gamedata, savedata, and
actorinfo.
"""
# Copyright 2019 Nicene Nerd <macadamiadaze@gmail.com>
# Licensed under GPLv3+
import zlib
from copy import deepcopy
from functools import partial
from io import BytesIO
from math import ceil
from multiprocessing import Pool, cpu_count
from pathlib import Path
from typing import List, Union

import byml
from byml import yaml_util
import rstb
import rstb.util
import sarc
import xxhash
import yaml

from bcml import util, rstable, mergers
from bcml.util import BcmlMod


def get_stock_gamedata() -> sarc.SARC:
    """ Gets the contents of the unmodded gamedata.sarc """
    if not hasattr(get_stock_gamedata, 'gamedata'):
        with util.get_game_file('Pack/Bootup.pack').open('rb') as b_file:
            bootup = sarc.read_file_and_make_sarc(b_file)
        get_stock_gamedata.gamedata = sarc.SARC(util.decompress(
            bootup.get_file_data('GameData/gamedata.ssarc')))
    return get_stock_gamedata.gamedata


def get_stock_savedata() -> sarc.SARC:
    """ Gets the contents of the unmodded savedataformat.sarc """
    if not hasattr(get_stock_savedata, 'savedata'):
        with util.get_game_file('Pack/Bootup.pack').open('rb') as b_file:
            bootup = sarc.read_file_and_make_sarc(b_file)
        get_stock_savedata.savedata = sarc.SARC(util.decompress(
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
    :type bgdata: class:`sarc.SARCWriter`
    :param bootup_path: Path to the Bootup.pack to update, defaults to a master BCML copy
    :type bootup_path: class:`pathlib.Path`, optional
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
                      util.compress(gamedata_bytes))
    (util.get_master_modpack_dir() / 'content' /
     'Pack').mkdir(parents=True, exist_ok=True)
    with (util.get_master_modpack_dir() / 'content' / 'Pack' / 'Bootup.pack').open('wb') as b_file:
        new_pack.write(b_file)
    return rstb.SizeCalculator().calculate_file_size_with_ext(gamedata_bytes, True, '.sarc')


def inject_savedata_into_bootup(bgsvdata: sarc.SARCWriter, bootup_path: Path = None) -> int:
    """
    Packs a savedata SARC into Bootup.pack and returns the RSTB size of the new savedataformat.sarc

    :param bgsvdata: A SARCWriter for the new savedata
    :type bgsvdata: class:`sarc.SARCWriter`
    :param bootup_path: Path to the Bootup.pack to update, defaults to a master BCML copy
    :type bootup_path: class:`pathlib.Path`, optional
    :returns: Returns the RSTB size of the new savedataformat.sarc
    :rtype: int
    """
    if not bootup_path:
        master_boot = util.get_master_modpack_dir() / 'content' / 'Pack' / 'Bootup.pack'
        bootup_path = master_boot if master_boot.exists() \
            else util.get_game_file('Pack/Bootup.pack')
    with bootup_path.open('rb') as b_file:
        bootup_pack = sarc.read_file_and_make_sarc(b_file)
    new_pack = sarc.make_writer_from_sarc(bootup_pack)
    new_pack.delete_file('GameData/savedataformat.ssarc')
    savedata_bytes = bgsvdata.get_bytes()
    new_pack.add_file('GameData/savedataformat.ssarc',
                      util.compress(savedata_bytes))
    (util.get_master_modpack_dir() / 'content' / 'Pack').mkdir(parents=True, exist_ok=True)
    with (util.get_master_modpack_dir() / 'content' / 'Pack' / 'Bootup.pack').open('wb') as b_file:
        new_pack.write(b_file)
    return rstb.SizeCalculator().calculate_file_size_with_ext(savedata_bytes, True, '.sarc')


def is_savedata_modded(savedata: sarc.SARC) -> {}:
    """
    Detects if any .bgsvdata file has been modified.

    :param savedata: The saveformatdata.sarc to check for modification.
    :type savedata: class:`sarc.SARC`
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


def _bgdata_from_bytes(file: str, game_dict: dict) -> {}:
    return byml.Byml(game_dict[file]).parse()


def consolidate_gamedata(gamedata: sarc.SARC, original_pool: Pool = None) -> {}:
    """
    Consolidates all game data in a game data SARC

    :return: Returns a dict of all game data entries in a SARC
    :rtype: dict of str: list
    """
    data = {}
    pool = original_pool or Pool(processes=cpu_count())
    game_dict = {}
    for file in gamedata.list_files():
        game_dict[file] = gamedata.get_file_data(file).tobytes()
    results = pool.map(
        partial(_bgdata_from_bytes, game_dict=game_dict),
        gamedata.list_files()
    )
    if not original_pool:
        pool.close()
        pool.join()
    del game_dict
    del gamedata
    for result in results:
        util.dict_merge(data, result)
    return data


def diff_gamedata_type(data_type: str, mod_data: dict, stock_data: dict) -> {}:
    """
    Logs the changes of a certain data type made to modded gamedata
    """
    stock_entries = [entry['DataName'] for entry in stock_data[data_type]]
    diffs = {}
    for entry in mod_data[data_type]:
        if entry['DataName'] not in stock_entries \
           or entry != stock_data[data_type][stock_entries.index(entry['DataName'])]:
            diffs[entry['DataName']] = deepcopy(entry)
    return {data_type: diffs}


def get_modded_gamedata_entries(gamedata: sarc.SARC, original_pool: Pool = None) -> {}:
    """
    Gets all of the modified gamedata entries in a dict of modded gamedata contents.

    :param modded_bgdata: A dict of modified .bgdata files and their contents.
    :type modded_bgdata: dict
    :returns: Returns a dictionary with each data type and the modified entries for it.
    :rtype: dict of str: dict of str: dict
    """
    stock_data = consolidate_gamedata(get_stock_gamedata(), original_pool)
    mod_data = consolidate_gamedata(gamedata, original_pool)
    diffs = {}
    pool = original_pool or Pool(cpu_count())
    results = pool.map(
        partial(diff_gamedata_type, mod_data=mod_data, stock_data=stock_data),
        list(mod_data.keys())
    )
    for result in results:
        _, entries = list(result.items())[0]
        if entries:
            diffs.update(result)
    if not original_pool:
        pool.close()
        pool.join()
    return diffs


def get_modded_savedata_entries(savedata: sarc.SARC) -> []:
    """
    Gets all of the modified savedata entries in a dict of modded savedata contents.

    :param savedata: The saveformatdata.sarc to search for modded entries.
    :type savedata: class:`sarc.SARC`
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


def merge_gamedata(verbose: bool = False, force: bool = False):
    """ Merges installed gamedata mods and saves the new Bootup.pack, fixing the RSTB if needed """
    mods = get_gamedata_mods()
    glog_path = util.get_master_modpack_dir() / 'logs' / 'gamedata.log'
    if not mods:
        print('No gamedata merging necessary.')
        if glog_path.exists():
            glog_path.unlink()
        if (util.get_master_modpack_dir() / 'logs' / 'gamedata.sarc').exists():
            (util.get_master_modpack_dir() / 'logs' / 'gamedata.sarc').unlink()
        return
    if glog_path.exists() and not force:
        with glog_path.open('r') as l_file:
            if xxhash.xxh32(str(mods)).hexdigest() == l_file.read():
                print('No gamedata merging necessary.')
                return

    modded_entries = {}
    loader = yaml.CSafeLoader
    yaml_util.add_constructors(loader)
    print('Loading gamedata mods...')
    for mod in mods:
        with (mod.path / 'logs' / 'gamedata.yml').open('r') as g_file:
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

    print('Updating RSTB...')
    rstable.set_size('GameData/gamedata.sarc', bootup_rstb)

    glog_path.parent.mkdir(parents=True, exist_ok=True)
    with glog_path.open('w', encoding='utf-8') as l_file:
        l_file.write(xxhash.xxh32(str(mods)).hexdigest())


def merge_savedata(verbose: bool = False, force: bool = False):
    """ Merges install savedata mods and saves the new Bootup.pack, fixing the RSTB if needed"""
    mods = get_savedata_mods()
    slog_path = util.get_master_modpack_dir() / 'logs' / 'savedata.log'
    if not mods:
        print('No gamedata merging necessary.')
        if slog_path.exists():
            slog_path.unlink()
        if (util.get_master_modpack_dir() / 'logs' / 'savedata.sarc').exists():
            (util.get_master_modpack_dir() / 'logs' / 'savedata.sarc').unlink()
        return
    if slog_path.exists() and not force:
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

    print('Updating RSTB...')
    rstable.set_size('GameData/savedataformat.sarc', bootup_rstb)

    slog_path.parent.mkdir(parents=True, exist_ok=True)
    with slog_path.open('w', encoding='utf-8') as l_file:
        l_file.write(xxhash.xxh32(str(mods)).hexdigest())


def get_stock_actorinfo() -> dict:
    """ Gets the unmodded contents of ActorInfo.product.sbyml """
    actorinfo = util.get_game_file('Actor/ActorInfo.product.sbyml')
    with actorinfo.open('rb') as a_file:
        return byml.Byml(util.decompress(a_file.read())).parse()


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
    actor_mods = [mod for mod in util.get_installed_mods()\
                  if (mod.path / 'logs' / 'actorinfo.yml').exists()]
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
            util.dict_merge(modded_actors, entries, overwrite_lists=True)
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
                            actor_info, overwrite_lists=True)
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
    actor_path.write_bytes(util.compress(buf.getvalue()))
    print('Actor info merged successfully')


class GameDataMerger(mergers.Merger):
    NAME: str = 'gamedata'

    def __init__(self):
        super().__init__(
            'game data merge',
            'Merges changes to gamedata.sarc',
            'gamedata.yml', options={}
        )

    def generate_diff(self, mod_dir: Path, modded_files: List[Union[Path, str]]):
        if 'content/Pack/Bootup.pack//GameData/gamedata.ssarc' in modded_files:
            with (mod_dir / 'content' / 'Pack' / 'Bootup.pack').open('rb') as bootup_file:
                bootup_sarc = sarc.read_file_and_make_sarc(bootup_file)
            return get_modded_gamedata_entries(
                sarc.SARC(
                    util.decompress(
                        bootup_sarc.get_file_data('GameData/gamedata.ssarc').tobytes()
                    )
                ),
                original_pool=self._pool
            )
        else:
            return {}

    def log_diff(self, mod_dir: Path, diff_material: Union[dict, List[Path]]):
        if isinstance(diff_material, List):
            diff_material = self.generate_diff(mod_dir, diff_material)
        if diff_material:
            with (mod_dir / 'logs' / self._log_name).open('w', encoding='utf-8') as log:
                dumper = yaml.CSafeDumper
                yaml_util.add_representers(dumper)
                yaml.dump(diff_material, log, Dumper=dumper, allow_unicode=True, encoding='utf-8',
                          default_flow_style=None)

    def get_mod_diff(self, mod: BcmlMod):
        if self.is_mod_logged(mod):
            with (mod.path / 'logs' / self._log_name).open('r', encoding='utf-8') as log:
                loader = yaml.CSafeLoader
                yaml_util.add_constructors(loader)
                return yaml.load(log, Loader=loader)
        else:
            return {}

    def get_all_diffs(self):
        diffs = []
        for mod in get_gamedata_mods():
            diffs.append(self.get_mod_diff(mod))
        return diffs

    def consolidate_diffs(self, diffs: list):
        all_diffs = {}
        for diff in diffs:
            util.dict_merge(all_diffs, diff, overwrite_lists=True)
        return all_diffs

    def perform_merge(self):
        force = False
        if 'force' in self._options:
            force = self._options['force']
        merge_gamedata(force=force)

    def get_checkbox_options(self):
        return [('force', 'Remerge game data even if no changes detected')]

    @staticmethod
    def is_bootup_injector():
        return True

    def get_bootup_injection(self):
        tmp_sarc = util.get_master_modpack_dir() / 'logs' / 'gamedata.sarc'
        if tmp_sarc.exists():
            return (
                'GameData/gamedata.ssarc',
                util.compress(tmp_sarc.read_bytes())
            )
        else:
            return


class SaveDataMerger(mergers.Merger):
    NAME: str = 'savedata'

    def __init__(self):
        super().__init__('save data merge', 'Merge changes to savedataformat.ssarc', 'savedata.yml')

    def generate_diff(self, mod_dir: Path, modded_files: List[Union[Path, str]]):
        if 'content/Pack/Bootup.pack//GameData/savedataformat.ssarc' in modded_files:
            with (mod_dir / 'content' / 'Pack' / 'Bootup.pack').open('rb') as bootup_file:
                bootup_sarc = sarc.read_file_and_make_sarc(bootup_file)
            return get_modded_savedata_entries(
                sarc.SARC(
                    util.decompress(
                        bootup_sarc.get_file_data('GameData/savedataformat.ssarc').tobytes()
                    )
                )
            )
        else:
            return []

    def log_diff(self, mod_dir: Path, diff_material):
        if isinstance(diff_material[0], Path):
            diff_material = self.generate_diff(mod_dir, diff_material)
        if diff_material:
            with (mod_dir / 'logs' / self._log_name).open('w', encoding='utf-8') as log:
                dumper = yaml.CSafeDumper
                yaml_util.add_representers(dumper)
                yaml.dump(diff_material, log, Dumper=dumper, allow_unicode=True, encoding='utf-8',
                          default_flow_style=None)

    def get_mod_diff(self, mod: BcmlMod):
        if self.is_mod_logged(mod):
            with (mod.path / 'logs' / self._log_name).open('r', encoding='utf-8') as log:
                loader = yaml.CSafeLoader
                yaml_util.add_constructors(loader)
                return yaml.load(log, Loader=loader)
        else:
            return []

    def get_all_diffs(self):
        diffs = []
        for mod in get_savedata_mods():
            diffs.append(self.get_mod_diff(mod))
        return diffs

    def consolidate_diffs(self, diffs: list):
        all_diffs = []
        hashes = []
        for diff in reversed(diffs):
            for entry in diff:
                if entry['HashValue'] not in hashes:
                    all_diffs.append(entry)
        return all_diffs

    def perform_merge(self):
        force = False
        if 'force' in self._options:
            force = self._options['force']
        merge_savedata(force=force)

    def get_checkbox_options(self):
        return [('force', 'Remerge save data even if no changes detected')]

    @staticmethod
    def is_bootup_injector():
        return True

    def get_bootup_injection(self):
        tmp_sarc = util.get_master_modpack_dir() / 'logs' / 'savedata.sarc'
        if tmp_sarc.exists():
            return (
                'GameData/savedataformat.ssarc',
                util.compress(tmp_sarc.read_bytes())
            )
        else:
            return


class ActorInfoMerger(mergers.Merger):
    NAME: str = 'actors'

    def __init__(self):
        super().__init__('actor info merge', 'Merges changes to ActorInfo.product.byml',
                         'actorinfo.yml ', {})

    def generate_diff(self, mod_dir: Path, modded_files: List[Union[Path, str]]):
        try:
            actor_file = next(iter([file for file in modded_files \
                               if Path(file).name == 'ActorInfo.product.sbyml']))
        except StopIteration:
            return {}
        actor_info = byml.Byml(util.decompress_file(str(actor_file))).parse()
        print('Detecting modified actor info entries...')
        return get_modded_actors(actor_info)

    def log_diff(self, mod_dir: Path, diff_material: Union[dict, list]):
        if isinstance(diff_material, List):
            diff_material = self.generate_diff(Path, diff_material)
        if diff_material:
            with (mod_dir / 'logs' / self._log_name).open('w', encoding='utf-8') as log:
                dumper = yaml.CSafeDumper
                yaml_util.add_representers(dumper)
                yaml.dump(diff_material, log, Dumper=dumper, allow_unicode=True, encoding='utf-8',
                          default_flow_style=None)

    def get_mod_diff(self, mod: BcmlMod):
        if self.is_mod_logged(mod):
            with (mod.path / 'logs' / self._log_name).open('r', encoding='utf-8') as log:
                loader = yaml.CSafeLoader
                yaml_util.add_constructors(loader)
                return yaml.load(log, Loader=loader)
        else:
            return {}

    def get_all_diffs(self):
        diffs = []
        for mod in get_gamedata_mods():
            diffs.append(self.get_mod_diff(mod))
        return diffs

    def consolidate_diffs(self, diffs: list):
        all_diffs = {}
        for diff in diffs:
            all_diffs.update(diff)
        return all_diffs

    def perform_merge(self):
        merge_actorinfo()

    def get_checkbox_options(self):
        return []
