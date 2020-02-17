"""
Provides functions to diff and merge BOTW gamedat and savedata.
"""
# Copyright 2019 Nicene Nerd <macadamiadaze@gmail.com>
# Licensed under GPLv3+
import zlib
from copy import deepcopy
from functools import partial
from io import BytesIO
from math import ceil
from multiprocessing import Pool, cpu_count, set_start_method
from pathlib import Path
from typing import List, Union

import byml
from byml import yaml_util
import oead
import rstb
import rstb.util
import sarc
import xxhash
import yaml

from bcml import util, mergers, json_util
from bcml.mergers import rstable
from bcml.util import BcmlMod


def get_stock_gamedata() -> sarc.SARC:
    if not hasattr(get_stock_gamedata, 'gamedata'):
        with util.get_game_file('Pack/Bootup.pack').open('rb') as b_file:
            bootup = sarc.read_file_and_make_sarc(b_file)
        get_stock_gamedata.gamedata = sarc.SARC(util.decompress(
            bootup.get_file_data('GameData/gamedata.ssarc')))
    return get_stock_gamedata.gamedata


def get_stock_savedata() -> sarc.SARC:
    if not hasattr(get_stock_savedata, 'savedata'):
        with util.get_game_file('Pack/Bootup.pack').open('rb') as b_file:
            bootup = sarc.read_file_and_make_sarc(b_file)
        get_stock_savedata.savedata = sarc.SARC(util.decompress(
            bootup.get_file_data('GameData/savedataformat.ssarc')
        ))
    return get_stock_savedata.savedata


def get_gamedata_hashes() -> {}:
    if not hasattr(get_gamedata_hashes, 'gamedata_hashes'):
        get_gamedata_hashes.gamedata_hashes = {}
        gamedata = get_stock_gamedata()
        for file in gamedata.list_files():
            get_gamedata_hashes.gamedata_hashes[file] = xxhash.xxh32(
                gamedata.get_file_data(file)).hexdigest()
    return get_gamedata_hashes.gamedata_hashes


def get_savedata_hashes() -> {}:
    if not hasattr(get_savedata_hashes, 'savedata_hashes'):
        get_savedata_hashes.savedata_hashes = {}
        savedata = get_stock_savedata()
        for file in savedata.list_files():
            get_savedata_hashes.savedata_hashes[file] = xxhash.xxh32(
                savedata.get_file_data(file)).hexdigest()
    return get_savedata_hashes.savedata_hashes


def inject_gamedata_into_bootup(bgdata: sarc.SARCWriter, bootup_path: Path = None) -> int:
    if not bootup_path:
        master_boot = util.get_master_modpack_dir() / util.get_content_path() / 'Pack' / 'Bootup.pack'
        bootup_path = master_boot if master_boot.exists() \
            else util.get_game_file('Pack/Bootup.pack')
    with bootup_path.open('rb') as b_file:
        bootup_pack = sarc.read_file_and_make_sarc(b_file)
    new_pack = sarc.make_writer_from_sarc(bootup_pack)
    new_pack.delete_file('GameData/gamedata.ssarc')
    gamedata_bytes = bgdata.get_bytes()
    new_pack.add_file('GameData/gamedata.ssarc',
                      util.compress(gamedata_bytes))
    (util.get_master_modpack_dir() / util.get_content_path() /
     'Pack').mkdir(parents=True, exist_ok=True)
    with (util.get_master_modpack_dir() / util.get_content_path() / 'Pack' / 'Bootup.pack').open('wb') as b_file:
        new_pack.write(b_file)
    return rstb.SizeCalculator().calculate_file_size_with_ext(gamedata_bytes, True, '.sarc')


def inject_savedata_into_bootup(bgsvdata: sarc.SARCWriter, bootup_path: Path = None) -> int:
    if not bootup_path:
        master_boot = util.get_master_modpack_dir() / util.get_content_path() / 'Pack' / 'Bootup.pack'
        bootup_path = master_boot if master_boot.exists() \
            else util.get_game_file('Pack/Bootup.pack')
    with bootup_path.open('rb') as b_file:
        bootup_pack = sarc.read_file_and_make_sarc(b_file)
    new_pack = sarc.make_writer_from_sarc(bootup_pack)
    new_pack.delete_file('GameData/savedataformat.ssarc')
    savedata_bytes = bgsvdata.get_bytes()
    new_pack.add_file('GameData/savedataformat.ssarc',
                      util.compress(savedata_bytes))
    (util.get_master_modpack_dir() / util.get_content_path() / 'Pack').mkdir(parents=True, exist_ok=True)
    with (util.get_master_modpack_dir() / util.get_content_path() / 'Pack' / 'Bootup.pack').open('wb') as b_file:
        new_pack.write(b_file)
    return rstb.SizeCalculator().calculate_file_size_with_ext(savedata_bytes, True, '.sarc')


def is_savedata_modded(savedata: sarc.SARC) -> {}:
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


def consolidate_gamedata(gamedata: sarc.SARC, pool: Pool) -> {}:
    data = {}
    set_start_method('spawn', True)
    p = pool or Pool(processes=cpu_count())
    game_dict = {}
    for file in gamedata.list_files():
        game_dict[file] = gamedata.get_file_data(file).tobytes()
    results = pool.map(
        partial(_bgdata_from_bytes, game_dict=game_dict),
        gamedata.list_files()
    )
    del game_dict
    del gamedata
    for result in results:
        util.dict_merge(data, result)
    if not pool:
        p.close()
        p.join()
    return data


def diff_gamedata_type(data_type: str, mod_data: dict, stock_data: dict) -> {}:
    stock_entries = [entry['DataName'] for entry in stock_data[data_type]]
    diffs = {}
    for entry in mod_data[data_type]:
        if entry['DataName'] not in stock_entries \
           or entry != stock_data[data_type][stock_entries.index(entry['DataName'])]:
            diffs[entry['DataName']] = deepcopy(entry)
    return {data_type: diffs}


def get_modded_gamedata_entries(gamedata: sarc.SARC, pool: Pool = None) -> {}:
    set_start_method('spawn', True)
    p = pool or Pool(cpu_count())
    stock_data = consolidate_gamedata(get_stock_gamedata(), p)
    mod_data = consolidate_gamedata(gamedata, p)
    diffs = {}
    results = pool.map(
        partial(diff_gamedata_type, mod_data=mod_data, stock_data=stock_data),
        list(mod_data.keys())
    )
    for result in results:
        _, entries = list(result.items())[0]
        if entries:
            diffs.update(result)
    if not pool:
        p.close()
        p.join()
    return diffs


def get_modded_savedata_entries(savedata: sarc.SARC) -> []:
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
    gdata_mods = [mod for mod in util.get_installed_mods() if (
        mod.path / 'logs' / 'gamedata.yml').exists()]
    return sorted(gdata_mods, key=lambda mod: mod.priority)


def get_savedata_mods() -> List[BcmlMod]:
    sdata_mods = [mod for mod in util.get_installed_mods() if (
        mod.path / 'logs' / 'savedata.yml').exists()]
    return sorted(sdata_mods, key=lambda mod: mod.priority)


class GameDataMerger(mergers.Merger):
    NAME: str = 'gamedata'

    def __init__(self):
        super().__init__(
            'game data',
            'Merges changes to gamedata.sarc',
            'gamedata.json', options={}
        )

    def generate_diff(self, mod_dir: Path, modded_files: List[Union[Path, str]]):
        if 'content/Pack/Bootup.pack//GameData/gamedata.ssarc' in modded_files:
            with (mod_dir / util.get_content_path() / 'Pack' / 'Bootup.pack').open('rb') as bootup_file:
                bootup_sarc = sarc.read_file_and_make_sarc(bootup_file)
            return get_modded_gamedata_entries(
                sarc.SARC(
                    util.decompress(
                        bootup_sarc.get_file_data('GameData/gamedata.ssarc').tobytes()
                    )
                ),
                pool=self._pool
            )
        else:
            return {}

    def log_diff(self, mod_dir: Path, diff_material: Union[dict, List[Path]]):
        if isinstance(diff_material, List):
            diff_material = self.generate_diff(mod_dir, diff_material)
        if diff_material:
            (mod_dir / 'logs' / self._log_name).write_text(
                json_util.byml_to_json(diff_material),
                encoding='utf-8'
            )

    def get_mod_diff(self, mod: BcmlMod):
        if self.is_mod_logged(mod):
            return json_util.json_to_byml(
                (mod.path / 'logs' / self._log_name).read_text(encoding='utf-8')
            )
        else:
            return {}

    def get_all_diffs(self):
        diffs = []
        for mod in [m for m in util.get_installed_mods() if self.is_mod_logged(m)]:
            diffs.append(self.get_mod_diff(mod))
        return diffs

    def consolidate_diffs(self, diffs: list):
        all_diffs = {}
        for diff in diffs:
            util.dict_merge(all_diffs, diff, overwrite_lists=True)
        util.vprint('All gamedata diffs:')
        util.vprint(all_diffs)
        return all_diffs

    @util.timed
    def perform_merge(self):
        force = False
        if 'force' in self._options:
            force = self._options['force']
        glog_path = util.get_master_modpack_dir() / 'logs' / 'gamedata.log'

        modded_entries = self.consolidate_diffs(self.get_all_diffs())
        if not modded_entries:
            print('No gamedata merging necessary.')
            if glog_path.exists():
                glog_path.unlink()
            if (util.get_master_modpack_dir() / 'logs' / 'gamedata.sarc').exists():
                (util.get_master_modpack_dir() / 'logs' / 'gamedata.sarc').unlink()
            return
        if glog_path.exists() and not force:
            with glog_path.open('r') as l_file:
                if xxhash.xxh32(str(modded_entries)).hexdigest() == l_file.read():
                    print('No gamedata merging necessary.')
                    return
        merged_entries = {}

        print('Loading stock gamedata...')
        gamedata = get_stock_gamedata()
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
                    merged_entries[data_type][i] = deepcopy(
                        modded_entries[data_type][entry['DataName']])
                print(f'Merged modified {data_type} entries')

        for data_type in modded_entries:
            for entry in [entry for entry in modded_entries[data_type]
                        if entry not in [entry['DataName'] for entry in merged_entries[data_type]]]:
                merged_entries[data_type].append(modded_entries[data_type][entry])
            print(f'Merged new {data_type} entries')

        print('Creating and injecting new gamedata.sarc...')
        new_gamedata = sarc.SARCWriter(util.get_settings('wiiu'))
        for data_type in merged_entries:
            num_files = ceil(len(merged_entries[data_type]) / 4096)
            for i in range(num_files):
                end_pos = (i+1) * 4096
                if end_pos > len(merged_entries[data_type]):
                    end_pos = len(merged_entries[data_type])
                buf = BytesIO()
                byml.Writer(
                    {data_type: merged_entries[data_type][i*4096:end_pos]},
                    be=util.get_settings('wiiu')
                ).write(buf)
                new_gamedata.add_file(f'/{data_type}_{i}.bgdata', buf.getvalue())
        bootup_rstb = inject_gamedata_into_bootup(new_gamedata)
        (util.get_master_modpack_dir() / 'logs').mkdir(parents=True, exist_ok=True)
        with (util.get_master_modpack_dir() / 'logs' / 'gamedata.sarc').open('wb') as g_file:
            new_gamedata.write(g_file)

        print('Updating RSTB...')
        rstable.set_size('GameData/gamedata.sarc', bootup_rstb)

        glog_path.parent.mkdir(parents=True, exist_ok=True)
        with glog_path.open('w', encoding='utf-8') as l_file:
            l_file.write(xxhash.xxh32(str(modded_entries)).hexdigest())
        

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
        super().__init__('save data', 'Merge changes to savedataformat.ssarc', 'savedata.json')

    def generate_diff(self, mod_dir: Path, modded_files: List[Union[Path, str]]):
        if 'content/Pack/Bootup.pack//GameData/savedataformat.ssarc' in modded_files:
            with (mod_dir / util.get_content_path() / 'Pack' / 'Bootup.pack').open('rb') as bootup_file:
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
            (mod_dir / 'logs' / self._log_name).write_text(
                json_util.byml_to_json(diff_material),
                encoding='utf-8'
            )

    def get_mod_diff(self, mod: BcmlMod):
        if self.is_mod_logged(mod):
            return json_util.json_to_byml(
                (mod.path / 'logs' / self._log_name).read_text(encoding='utf-8')
            )
        else:
            return {}

    def get_all_diffs(self):
        diffs = []
        for mod in [m for m in util.get_installed_mods() if self.is_mod_logged(m)]:
            diffs.append(self.get_mod_diff(mod))
        return diffs

    def consolidate_diffs(self, diffs: list):
        all_diffs = []
        hashes = []
        for diff in reversed(diffs):
            for entry in diff:
                if entry['HashValue'] not in hashes:
                    all_diffs.append(entry)
                    hashes.append(entry['HashValue'])
        util.vprint('All savedata diffs:')
        util.vprint(all_diffs)
        return all_diffs

    @util.timed
    def perform_merge(self):
        force = False
        if 'force' in self._options:
            force = self._options['force']
        slog_path = util.get_master_modpack_dir() / 'logs' / 'savedata.log'

        new_entries = self.consolidate_diffs(self.get_all_diffs())
        if not new_entries:
            print('No savedata merging necessary.')
            if slog_path.exists():
                slog_path.unlink()
            if (util.get_master_modpack_dir() / 'logs' / 'savedata.sarc').exists():
                (util.get_master_modpack_dir() / 'logs' / 'savedata.sarc').unlink()
            return
        if slog_path.exists() and not force:
            with slog_path.open('r') as l_file:
                if xxhash.xxh32(str(new_entries)).hexdigest() == l_file.read():
                    print('No savedata merging necessary.')
                    return

        savedata = get_stock_savedata()
        merged_entries = []
        save_files = sorted(savedata.list_files())[0:-2]

        print('Loading stock savedata...')
        for file in save_files:
            merged_entries.extend(
                byml.Byml(savedata.get_file_data(file).tobytes()).parse()['file_list'][1]
            )

        print('Merging changes...')
        merged_entries.extend(new_entries)
        merged_entries.sort(key=lambda x: x['HashValue'])

        special_bgsv = [
            savedata.get_file_data('/saveformat_6.bgsvdata').tobytes(),
            savedata.get_file_data('/saveformat_7.bgsvdata').tobytes(),
        ]

        print('Creating and injecting new savedataformat.sarc...')
        new_savedata = sarc.SARCWriter(util.get_settings('wiiu'))
        num_files = ceil(len(merged_entries) / 8192)
        for i in range(num_files):
            end_pos = (i+1) * 8192
            if end_pos > len(merged_entries):
                end_pos = len(merged_entries)
            buf = BytesIO()
            byml.Writer(
                {
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
                },
                util.get_settings('wiiu')
            ).write(buf)
            new_savedata.add_file(f'/saveformat_{i}.bgsvdata', buf.getvalue())
        new_savedata.add_file(f'/saveformat_{num_files}.bgsvdata', special_bgsv[0])
        new_savedata.add_file(f'/saveformat_{num_files + 1}.bgsvdata', special_bgsv[1])
        bootup_rstb = inject_savedata_into_bootup(new_savedata)
        (util.get_master_modpack_dir() / 'logs').mkdir(parents=True, exist_ok=True)
        with (util.get_master_modpack_dir() / 'logs' / 'savedata.sarc').open('wb') as s_file:
            new_savedata.write(s_file)

        print('Updating RSTB...')
        rstable.set_size('GameData/savedataformat.sarc', bootup_rstb)

        slog_path.parent.mkdir(parents=True, exist_ok=True)
        with slog_path.open('w', encoding='utf-8') as l_file:
            l_file.write(xxhash.xxh32(str(new_entries)).hexdigest())

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
