"""
Provides functions to diff and merge BOTW gamedat and savedata.
"""
# Copyright 2020 Nicene Nerd <macadamiadaze@gmail.com>
# Licensed under GPLv3+
# pylint: disable=unsupported-assignment-operation
from functools import partial, lru_cache
from math import ceil
from multiprocessing import Pool, cpu_count, set_start_method
from pathlib import Path
from typing import List, Union

import oead
import rstb
import rstb.util
import xxhash

from bcml import util, mergers
from bcml.mergers import rstable
from bcml.util import BcmlMod


@lru_cache(None)
def get_stock_gamedata() -> oead.Sarc:
    bootup = oead.Sarc(util.get_game_file('Pack/Bootup.pack').read_bytes())
    return oead.Sarc(
        util.decompress(
            bootup.get_file('GameData/gamedata.ssarc').data
        )
    )


@lru_cache(None)
def get_stock_savedata() -> oead.Sarc:
    bootup = oead.Sarc(util.get_game_file('Pack/Bootup.pack').read_bytes())
    return oead.Sarc(
        util.decompress(
            bootup.get_file('GameData/savedataformat.ssarc').data
        )
    )


@lru_cache(None)
def get_gamedata_hashes() -> {}:
    gamedata = get_stock_gamedata()
    return {
        file.name: xxhash.xxh64_intdigest(file.data) for file in gamedata.get_files()
    }


@lru_cache(None)
def get_savedata_hashes() -> {}:
    savedata = get_stock_savedata()
    return {
        file.name: xxhash.xxh64_intdigest(file.data) for file in savedata.get_files()
    }


def inject_gamedata_into_bootup(bgdata: oead.SarcWriter, bootup_path: Path = None) -> int:
    if not bootup_path:
        master_boot = (
            util.get_master_modpack_dir() / util.get_content_path() / 'Pack' / 'Bootup.pack'
        )
        bootup_path = (
            master_boot if master_boot.exists() else util.get_game_file('Pack/Bootup.pack')
        )
    bootup_pack = oead.Sarc(bootup_path.read_bytes())
    new_pack = oead.SarcWriter.from_sarc(bootup_pack)
    gamedata_bytes = bgdata.write()[1]
    new_pack.files['GameData/gamedata.ssarc'] = util.compress(gamedata_bytes)
    ((util.get_master_modpack_dir() / util.get_content_path() / 'Pack')
     .mkdir(parents=True, exist_ok=True))
    ((util.get_master_modpack_dir() / util.get_content_path() / 'Pack' / 'Bootup.pack')
     .write_bytes(new_pack.write()[1]))
    return rstb.SizeCalculator().calculate_file_size_with_ext(gamedata_bytes, True, '.sarc')


def inject_savedata_into_bootup(bgsvdata: oead.SarcWriter, bootup_path: Path = None) -> int:
    if not bootup_path:
        master_boot = (
            util.get_master_modpack_dir() / util.get_content_path() / 'Pack' / 'Bootup.pack'
        )
        bootup_path = (
            master_boot if master_boot.exists() else util.get_game_file('Pack/Bootup.pack')
        )
    bootup_pack = oead.Sarc(bootup_path.read_bytes())
    new_pack = oead.SarcWriter.from_sarc(bootup_pack)
    savedata_bytes = bgsvdata.write()[1]
    new_pack.files['GameData/savedataformat.ssarc'] = util.compress(savedata_bytes)
    ((util.get_master_modpack_dir() / util.get_content_path() / 'Pack')
     .mkdir(parents=True, exist_ok=True))
    ((util.get_master_modpack_dir() / util.get_content_path() / 'Pack' / 'Bootup.pack')
     .write_bytes(new_pack.write()[1]))
    return rstb.SizeCalculator().calculate_file_size_with_ext(savedata_bytes, True, '.sarc')


def is_savedata_modded(savedata: oead.Sarc) -> {}:
    hashes = get_savedata_hashes()
    sv_files = sorted(savedata.get_files(), key=lambda file: file.name)
    fix_slash = '/' if not sv_files[0].name.startswith('/') else ''
    modded = False
    for svdata in sv_files[0:-2]:
        svdata_hash = xxhash.xxh64_intdigest(svdata.data)
        if not modded:
            modded = fix_slash + \
                svdata.name not in hashes or svdata_hash != hashes[fix_slash + svdata.name]
    return modded


def _bgdata_from_bytes(file: str, game_dict: dict) -> {}:
    return oead.byml.to_text(oead.byml.from_binary(game_dict[file]))


def consolidate_gamedata(gamedata: oead.Sarc, pool: Pool) -> {}:
    data = {}
    set_start_method('spawn', True)
    this_pool = pool or Pool(processes=cpu_count())
    game_dict = {}
    for file in gamedata.get_files():
        game_dict[file.name] = bytes(file.data)
    results = pool.map(
        partial(_bgdata_from_bytes, game_dict=game_dict),
        [f.name for f in gamedata.get_files()]
    )
    del game_dict
    del gamedata
    for result in results:
        util.dict_merge(data, oead.byml.from_text(result))
    if not pool:
        this_pool.close()
        this_pool.join()
    util.vprint(data)
    return data


def diff_gamedata_type(data_type: str, mod_data: dict, stock_data: dict) -> {}:
    stock_entries = [entry['DataName'] for entry in stock_data[data_type]]
    mod_entries = [entry['DataName'] for entry in mod_data[data_type]]
    diffs = oead.byml.Hash({
        "add": oead.byml.Hash(),
        "del": oead.byml.Array({
            entry for entry in stock_entries if entry not in mod_entries
        })
    })
    for entry in mod_data[data_type]:
        if entry['DataName'] not in stock_entries \
           or entry != stock_data[data_type][stock_entries.index(entry['DataName'])]:
            diffs['add'][entry['DataName']] = entry
    return oead.byml.Hash({data_type: diffs})


def get_modded_gamedata_entries(gamedata: oead.Sarc, pool: Pool = None) -> {}:
    set_start_method('spawn', True)
    this_pool = pool or Pool(cpu_count())
    stock_data = consolidate_gamedata(get_stock_gamedata(), this_pool)
    mod_data = consolidate_gamedata(gamedata, this_pool)
    if not pool:
        this_pool.close()
        this_pool.join()
    diffs = {}
    for key in mod_data:
        diffs.update(
            diff_gamedata_type(key, mod_data, stock_data)
        )
    return oead.byml.Hash(diffs)


def get_modded_savedata_entries(savedata: oead.Sarc) -> {}:
    ref_savedata = get_stock_savedata().get_files()
    ref_hashes = set()
    new_entries = oead.byml.Array()
    for file in sorted(ref_savedata, key=lambda f: f.name)[0:-2]:
        ref_hashes |= {
            int(item['HashValue']) for item in oead.byml.from_binary(file.data)['file_list'][1]
        }
    mod_hashes = set()
    for file in sorted(savedata.get_files(), key=lambda f: f.name,)[0:-2]:
        entries = oead.byml.from_binary(file.data)['file_list'][1]
        mod_hashes |= {int(item['HashValue']) for item in entries}
        new_entries.extend(
            {item for item in entries if int(item['HashValue']) not in ref_hashes}
        )
    return oead.byml.Hash({
        'add': new_entries,
        'del': oead.byml.Array(
            {oead.S32(item) for item in ref_hashes if item not in mod_hashes}
        )
    })


def get_gamedata_mods() -> List[BcmlMod]:
    gdata_mods = [mod for mod in util.get_installed_mods() if (
        mod.path / 'logs' / 'gamedata.yml').exists()]
    return sorted(gdata_mods, key=lambda mod: mod.priority)


def get_savedata_mods() -> List[BcmlMod]:
    sdata_mods = [mod for mod in util.get_installed_mods() if (
        mod.path / 'logs' / 'savedata.yml').exists()]
    return sorted(sdata_mods, key=lambda mod: mod.priority)


class GameDataMerger(mergers.Merger):
    # pylint: disable=abstract-method
    NAME: str = 'gamedata'

    def __init__(self):
        super().__init__(
            'game data',
            'Merges changes to gamedata.sarc',
            'gamedata.yml', options={}
        )

    def generate_diff(self, mod_dir: Path, modded_files: List[Union[Path, str]]):
        if 'content/Pack/Bootup.pack//GameData/gamedata.ssarc' in modded_files:
            bootup_sarc = oead.Sarc(
                util.unyaz_if_needed(
                    (mod_dir / util.get_content_path() / 'Pack' / 'Bootup.pack').read_bytes()
                )
            )
            return get_modded_gamedata_entries(
                oead.Sarc(
                    util.decompress(
                        bootup_sarc.get_file('GameData/gamedata.ssarc').data
                    )
                ),
                pool=self._pool
            )
        else:
            return {}

    def log_diff(self, mod_dir: Path, diff_material):
        if isinstance(diff_material, List):
            diff_material: oead.byml.Hash = self.generate_diff(mod_dir, diff_material)
        if diff_material:
            (mod_dir / 'logs' / self._log_name).write_text(
                oead.byml.to_text(diff_material),
                encoding='utf-8'
            )

    def get_mod_diff(self, mod: BcmlMod):
        diffs = {}
        if self.is_mod_logged(mod):
            util.dict_merge(
                diffs,
                oead.byml.from_text(
                    (mod.path / 'logs' / self._log_name).read_text(encoding='utf-8')
                ),
                overwrite_lists=True
            )
        for opt in {d for d in (mod.path / 'options').glob('*') if d.is_dir()}:
            if (opt / 'logs' / self._log_name).exists():
                util.dict_merge(
                    diffs,
                    oead.byml.from_text(
                        (opt / 'logs' / self._log_name).read_text('utf-8')
                    ),
                    overwrite_lists=True
                )
        return diffs

    def get_mod_edit_info(self, mod: util.BcmlMod) -> set:
        edited = set()
        diff = self.get_mod_diff(mod)
        for items in diff.values():
            edited |= set(items.keys())
        return edited

    def get_all_diffs(self):
        diffs = []
        for mod in util.get_installed_mods():
            diffs.append(self.get_mod_diff(mod))
        return diffs

    def consolidate_diffs(self, diffs: list):
        all_diffs = {}
        for diff in diffs:
            util.dict_merge(all_diffs, diff, overwrite_lists=True)
        return all_diffs

    @util.timed
    def perform_merge(self):
        force = False
        if 'force' in self._options:
            force = self._options['force']
        glog_path = util.get_master_modpack_dir() / 'logs' / 'gamedata.log'

        modded_entries = self.consolidate_diffs(self.get_all_diffs())
        util.vprint('All gamedata diffs:')
        util.vprint(modded_entries)
        if not modded_entries:
            print('No gamedata merging necessary.')
            if glog_path.exists():
                glog_path.unlink()
            if (util.get_master_modpack_dir() / 'logs' / 'gamedata.sarc').exists():
                (util.get_master_modpack_dir() / 'logs' / 'gamedata.sarc').unlink()
            return
        if glog_path.exists() and not force:
            with glog_path.open('r') as l_file:
                if xxhash.xxh64_hexdigest(str(modded_entries)) == l_file.read():
                    print('No gamedata merging necessary.')
                    return
        merged_entries = {}

        print('Loading stock gamedata...')
        gamedata = get_stock_gamedata()
        for yml in gamedata.get_files():
            base_yml = oead.byml.from_binary(yml.data)
            for data_type in base_yml:
                if data_type not in merged_entries:
                    merged_entries[data_type] = []
                merged_entries[data_type].extend(base_yml[data_type])

        print('Merging changes...')
        for data_type in merged_entries:
            if data_type in modded_entries:
                for entry in [entry for entry in merged_entries[data_type]
                              if entry['DataName'] in modded_entries[data_type]['add']]:
                    i = merged_entries[data_type].index(entry)
                    merged_entries[data_type][i] = (
                        modded_entries[data_type]['add'][entry['DataName']]
                    )
                print(f'Merged modified {data_type} entries')

        for data_type in modded_entries:
            for entry in [entry for entry in modded_entries[data_type]['add']
                          if entry not in [entry['DataName'] for entry in merged_entries[data_type]]
                         ]:
                merged_entries[data_type].append(modded_entries[data_type]['add'][entry])
            print(f'Merged new {data_type} entries')
            for entry in merged_entries[data_type]:
                if entry['DataName'] in modded_entries[data_type]['del']:
                    merged_entries[data_type].remove(entry)
            print(f'Removed {len(modded_entries[data_type]["del"])} {data_type} entries')
        print('Creating and injecting new gamedata.sarc...')
        new_gamedata = oead.SarcWriter(
            endian=oead.Endianness.Big if util.get_settings('wiiu') else oead.Endianness.Little
        )
        for data_type in merged_entries:
            num_files = ceil(len(merged_entries[data_type]) / 4096)
            for i in range(num_files):
                end_pos = (i+1) * 4096
                if end_pos > len(merged_entries[data_type]):
                    end_pos = len(merged_entries[data_type])
                new_gamedata.files[f'/{data_type}_{i}.bgdata'] = oead.byml.to_binary(
                    oead.byml.Hash({data_type: merged_entries[data_type][i*4096:end_pos]}),
                    big_endian=util.get_settings('wiiu')
                )
        bootup_rstb = inject_gamedata_into_bootup(new_gamedata)
        (util.get_master_modpack_dir() / 'logs').mkdir(parents=True, exist_ok=True)
        (util.get_master_modpack_dir() / 'logs' / 'gamedata.sarc').write_bytes(
            new_gamedata.write()[1]
        )

        print('Updating RSTB...')
        rstable.set_size('GameData/gamedata.sarc', bootup_rstb)

        glog_path.parent.mkdir(parents=True, exist_ok=True)
        with glog_path.open('w', encoding='utf-8') as l_file:
            l_file.write(xxhash.xxh64_hexdigest(str(modded_entries)))

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
    # pylint: disable=abstract-method
    NAME: str = 'savedata'

    def __init__(self):
        super().__init__('save data', 'Merge changes to savedataformat.ssarc', 'savedata.yml')

    def generate_diff(self, mod_dir: Path, modded_files: List[Union[Path, str]]):
        if 'content/Pack/Bootup.pack//GameData/savedataformat.ssarc' in modded_files:
            bootup_sarc = oead.Sarc(
                util.unyaz_if_needed(
                    (mod_dir / util.get_content_path() / 'Pack' / 'Bootup.pack').read_bytes()
                )
            )
            return get_modded_savedata_entries(
                oead.Sarc(
                    util.decompress(
                        bootup_sarc.get_file('GameData/savedataformat.ssarc').data
                    )
                )
            )
        else:
            return {}

    def log_diff(self, mod_dir: Path, diff_material):
        if isinstance(diff_material, List):
            diff_material: oead.byml.Array = self.generate_diff(mod_dir, diff_material)
        if diff_material:
            (mod_dir / 'logs' / self._log_name).write_text(
                oead.byml.to_text(diff_material),
                encoding='utf-8'
            )

    def get_mod_diff(self, mod: BcmlMod):
        diffs = []
        if self.is_mod_logged(mod):
            diffs.append(oead.byml.from_text(
                (mod.path / 'logs' / self._log_name).read_text(encoding='utf-8')
            ))
        for opt in {d for d in (mod.path / 'options').glob('*') if d.is_dir()}:
            if (opt / 'logs' / self._log_name).exists():
                diffs.append(oead.byml.from_text(
                    (opt / 'logs' / self._log_name).read_text('utf-8')
                ))
        return diffs

    def get_all_diffs(self):
        diffs = []
        for mod in util.get_installed_mods():
            diffs.extend(self.get_mod_diff(mod))
        return diffs

    def consolidate_diffs(self, diffs: list):
        all_diffs = oead.byml.Hash({
            'add': oead.byml.Array(),
            'del': oead.byml.Array()
        })
        hashes = set()
        for diff in reversed(diffs):
            for entry in diff['add']:
                if entry['HashValue'] not in hashes:
                    all_diffs['add'].append(entry)
                hashes.add(entry['HashValue'])
            for entry in diff['del']:
                if entry not in all_diffs['del']:
                    all_diffs['del'].append(entry)
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
                if xxhash.xxh64_hexdigest(str(new_entries)) == l_file.read():
                    print('No savedata merging necessary.')
                    return

        savedata = get_stock_savedata()
        merged_entries = []
        save_files = sorted(savedata.get_files(), key=lambda f: f.name)[0:-2]

        print('Loading stock savedata...')
        for file in save_files:
            merged_entries.extend(
                oead.byml.from_binary(file.data)['file_list'][1]
            )

        print('Merging changes...')
        merged_entries.extend(new_entries['add'])
        for entry in merged_entries:
            if entry['HashValue'] in new_entries['del']:
                merged_entries.remove(entry)
        merged_entries.sort(key=lambda x: x['HashValue'])

        print('Creating and injecting new savedataformat.sarc...')
        new_savedata = oead.SarcWriter(
            endian=oead.Endianness.Big if util.get_settings('wiiu') else oead.Endianness.Little
        )
        num_files = ceil(len(merged_entries) / 8192)
        for i in range(num_files):
            end_pos = (i+1) * 8192
            if end_pos > len(merged_entries):
                end_pos = len(merged_entries)
            data = oead.byml.to_binary(
                oead.byml.Hash({
                    'file_list': oead.byml.Array([
                        {
                            'IsCommon': False,
                            'IsCommonAtSameAccount': False,
                            'IsSaveSecureCode': True,
                            'file_name': 'game_data.sav'
                        },
                        oead.byml.Array(merged_entries[i*8192:end_pos])
                    ]),
                    'save_info': oead.byml.Array([
                        {
                            'directory_num': oead.S32(8),
                            'is_build_machine': True,
                            'revision': oead.S32(18203)
                        }
                    ])
                }),
                big_endian=util.get_settings('wiiu')
            )
            new_savedata.files[f'/saveformat_{i}.bgsvdata'] = data
        new_savedata.files[f'/saveformat_{num_files}.bgsvdata'] =\
            oead.Bytes(savedata.get_file('/saveformat_6.bgsvdata').data)
        new_savedata.files[f'/saveformat_{num_files + 1}.bgsvdata'] =\
            oead.Bytes(savedata.get_file('/saveformat_7.bgsvdata').data)
        bootup_rstb = inject_savedata_into_bootup(new_savedata)
        (util.get_master_modpack_dir() / 'logs').mkdir(parents=True, exist_ok=True)
        ((util.get_master_modpack_dir() / 'logs' / 'savedata.sarc')
         .write_bytes(new_savedata.write()[1]))

        print('Updating RSTB...')
        rstable.set_size('GameData/savedataformat.sarc', bootup_rstb)

        slog_path.parent.mkdir(parents=True, exist_ok=True)
        with slog_path.open('w', encoding='utf-8') as l_file:
            l_file.write(xxhash.xxh64_hexdigest(str(new_entries)))

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
        return None

    def get_mod_edit_info(self, mod: util.BcmlMod) -> set:
        return {
            entry['DataName'] for entry in self.get_mod_diff(mod)
        }
