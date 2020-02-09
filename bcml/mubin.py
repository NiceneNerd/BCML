"""Handles diffing and merging map files"""
# Copyright 2019 Nicene Nerd <macadamiadaze@gmail.com>
# Licensed under GPLv3+
import shutil
from collections import namedtuple
from copy import deepcopy
from functools import partial
from multiprocessing import Pool, cpu_count
from pathlib import Path
from typing import Union, List

import byml
from byml import yaml_util
import rstb
import rstb.util
import sarc
import yaml

from bcml import util, mergers

Map = namedtuple('Map', 'section type')


def consolidate_map_files(modded_maps: List[str]) -> List[Map]:
    """ Turns a list of modified .mubin files into a list of modified map sections and types """
    return list(
        dict.fromkeys(
            map(
                lambda path: Map(*(Path(path).stem.split('_'))),
                modded_maps
            )
        )
    )


def get_stock_map(map_unit: Union[Map, tuple], force_vanilla: bool = False) -> dict:
    """
    Finds the most significant available map unit from the unmodded game and returns its
    contents as a dict.

    :param map: The map section and type.
    :type map: class:`bcml.mubin.Map`
    :return: Returns a dict representation of the requested map unit.
    :rtype: dict
    """
    if isinstance(map_unit, tuple):
        map_unit = Map(*map_unit)
    try:
        aoc_dir = util.get_aoc_dir()
    except FileNotFoundError:
        force_vanilla = True
    map_bytes = None
    if force_vanilla:
        try:
            map_path = (
                util.get_update_dir() / 'Map/MainField/'
                f'{map_unit.section}/{map_unit.section}_{map_unit.type}.smubin'
            )
            if not map_path.exists():
                map_path = (
                    util.get_game_dir() / 'Map/MainField/'
                    f'{map_unit.section}/{map_unit.section}_{map_unit.type}.smubin'
                )
            map_bytes = map_path.read_bytes()
        except FileNotFoundError:
            with util.get_game_file('Pack/TitleBG.pack').open('rb') \
                  as s_file:
                title_pack = sarc.read_file_and_make_sarc(s_file)
            if title_pack:
                try:
                    map_bytes = title_pack.get_file_data(
                        f'Map/MainField/{map_unit.section}/{map_unit.section}_{map_unit.type}'
                        '.smubin'
                    ).tobytes()
                except KeyError:
                    map_bytes = None
    else:
        if (aoc_dir / 'Pack' / 'AocMainField.pack').exists():
            with (aoc_dir / 'Pack' / 'AocMainField.pack').open('rb') as s_file:
                map_pack = sarc.read_file_and_make_sarc(s_file)
            if map_pack:
                try:
                    map_bytes = map_pack.get_file_data(
                        f'Map/MainField/{map_unit.section}/{map_unit.section}_{map_unit.type}'
                        '.smubin'
                    ).tobytes()
                except KeyError:
                    map_bytes = None
        if not map_bytes:
            map_path = f'Map/MainField/{map_unit.section}/{map_unit.section}_{map_unit.type}.smubin'
            try:
                map_bytes = util.get_game_file(map_path, aoc=True).read_bytes()
            except FileNotFoundError:
                try:
                    map_bytes = util.get_game_file(map_path).read_bytes()
                except FileNotFoundError:
                    with util.get_game_file('Pack/TitleBG.pack').open('rb') \
                        as s_file:
                        title_pack = sarc.read_file_and_make_sarc(s_file)
                    if title_pack:
                        try:
                            map_bytes = title_pack.get_file_data(
                                f'Map/MainField/{map_unit.section}/'
                                f'{map_unit.section}_{map_unit.type}.smubin'
                            ).tobytes()
                        except KeyError:
                            map_bytes = None
    if not map_bytes:
        raise FileNotFoundError(
            f'The stock map file {map_unit.section}_{map_unit.type}.smubin could not be found.'
        )
    map_bytes = util.decompress(map_bytes)
    return byml.Byml(map_bytes).parse()


def get_modded_map(map_unit: Union[Map, tuple], tmp_dir: Path) -> dict:
    """
    Finds the most significant available map_unit unit in a mod for a given section and type
    and returns its contents as a dict. Checks `AocMainField.pack` first, then the unpacked
    aoc map_unit files, and then the base game map_unit files.

    :param map_unit: The map_unit section and type.
    :type map_unit: class:`bcml.mubin.Map`
    :param tmp_dir: The path to the base directory of the mod.
    :type tmp_dir: class:`pathlib.Path`
    :return: Returns a dict representation of the requested map_unit unit.
    :rtype: dict
    """
    if isinstance(map_unit, tuple):
        map_unit = Map(*map_unit)
    map_bytes = None
    aoc_dir = tmp_dir / 'aoc' / '0010' / 'content'
    if not aoc_dir.exists():
        aoc_dir = tmp_dir / 'aoc' / 'content' / '0010'
        if not aoc_dir.exists():
            aoc_dir = tmp_dir / 'aoc' / '0010'
    if (aoc_dir / 'Pack' / 'AocMainField.pack').exists():
        with (aoc_dir / 'Pack' / 'AocMainField.pack').open('rb') as s_file:
            map_pack = sarc.read_file_and_make_sarc(s_file)
        if map_pack:
            try:
                map_bytes = map_pack.get_file_data(
                    f'Map/MainField/{map_unit.section}/{map_unit.section}_{map_unit.type}.smubin'
                ).tobytes()
            except KeyError:
                pass
    if not map_bytes:
        if (aoc_dir / 'Map' / 'MainField' / map_unit.section /\
            f'{map_unit.section}_{map_unit.type}.smubin').exists():
            map_bytes = (tmp_dir / 'aoc' / '0010' / 'Map' / 'MainField' / map_unit.section /\
                         f'{map_unit.section}_{map_unit.type}.smubin').read_bytes()
        elif (tmp_dir / 'content' / 'Map' / 'MainField' / map_unit.section /\
                f'{map_unit.section}_{map_unit.type}.smubin').exists():
            map_bytes = (tmp_dir / 'content' / 'Map' / 'MainField' / map_unit.section /\
                         f'{map_unit.section}_{map_unit.type}.smubin').read_bytes()
    if not map_bytes:
        raise FileNotFoundError(
            f'Oddly, the modded map {map_unit.section}_{map_unit.type}.smubin '
            'could not be found.'
        )
    map_bytes = util.decompress(map_bytes)
    return byml.Byml(map_bytes).parse()


def get_map_diff(base_map: Union[dict, Map], mod_map: dict, no_del: bool = False, 
                 link_del: bool = False) -> dict:
    """
    Detects the changes made to a modded map unit.

    :param base_map: The contents or identity of the map unit from the base game to compare from.
    :type base_map: Union[dict, class:`bcml.mubin.Map`]
    :param mod_map: The contents of the modded map unit.
    :type mod_map: dict
    :return: Returns a dict of changes in the modded map unit, including added, modified, and
    deleted actors.
    :rtype: dict of str: list
    """
    diffs = {
        'add': [],
        'mod': {},
        'del': []
    }
    if isinstance(base_map, Map):
        stock_map = True
        for obj in mod_map['Objs']:
            str_obj = str(obj)
            if 'IsHardModeActor' in str_obj or 'AoC_HardMode_Enabled' in str_obj:
                stock_map = False
                break
        base_map = get_stock_map(base_map, force_vanilla=stock_map)
    base_hashes = [obj['HashId'] for obj in base_map['Objs']]
    base_links = set()
    if not link_del:
        for obj in base_map['Objs']:
            if 'LinksToObj' in obj:
                base_links.update({link['DestUnitHashId']
                                    for link in obj['LinksToObj']})
    mod_hashes = [obj['HashId'] for obj in mod_map['Objs']]
    for obj in mod_map['Objs']:
        if obj['HashId'] not in base_hashes:
            diffs['add'].append(obj)
        elif obj['HashId'] in base_hashes and\
             obj != base_map['Objs'][base_hashes.index(obj['HashId'])]:
            diffs['mod'][obj['HashId']] = deepcopy(obj)
    diffs['del'] = [hash_id for hash_id in base_hashes if hash_id not in mod_hashes and \
                    not no_del and not (not link_del and hash_id in base_links)]
    return diffs


def get_all_map_diffs() -> dict:
    """
    Consolidates diffs for installed map unit mods into a single set of additions, modifications,
    and deletions.

    :return: Returns a dict of modded map units with their added, modified, and deleted actors.
    :rtype: dict of str: dict
    """
    diffs = {}
    loader = yaml.CSafeLoader
    yaml_util.add_constructors(loader)
    for mod in util.get_installed_mods():
        if (mod.path / 'logs' / 'map.yml').exists():
            with (mod.path / 'logs' / 'map.yml').open('r', encoding='utf-8') as y_file:
                map_yml = yaml.load(y_file, Loader=loader)
            for file, diff in map_yml.items():
                a_map = Map(*file.split('_'))
                if a_map not in diffs:
                    diffs[a_map] = []
                diffs[a_map].append(diff)
    c_diffs = {}
    for file, mods in list(diffs.items()):
        c_diffs[file] = {
            'add': [],
            'mod': {},
            'del': list(set([hash_id for hashes in [mod['del']\
                            for mod in mods] for hash_id in hashes]))
        }
        for mod in mods:
            for hash_id, actor in mod['mod'].items():
                c_diffs[file]['mod'][hash_id] = deepcopy(actor)
        add_hashes = []
        for mod in reversed(mods):
            for actor in mod['add']:
                if actor['HashId'] not in add_hashes:
                    add_hashes.append(actor['HashId'])
                    c_diffs[file]['add'].append(actor)
    return c_diffs


def generate_modded_map_log(tmp_dir: Path, modded_mubins: List[str], no_del: bool = False, 
                            link_del: bool = False):
    """Generates a dict log of modified mainfield maps"""
    diffs = {}
    modded_maps = consolidate_map_files(modded_mubins)
    for modded_map in modded_maps:
        diffs['_'.join(modded_map)] = get_map_diff(
            modded_map,
            get_modded_map(modded_map, tmp_dir),
            no_del=no_del,
            link_del=link_del
        )
    return diffs


def log_modded_maps(tmp_dir: Path, modded_mubins: List[str], no_del: bool = False, 
                    link_del: bool = False):
    """Logs modified mainfield maps to a YAML document"""
    diffs = generate_modded_map_log(tmp_dir, modded_mubins, no_del=no_del, link_del=link_del)
    log_file: Path = tmp_dir / 'logs' / 'map.yml'
    log_file.parent.mkdir(parents=True, exist_ok=True)
    dumper = yaml.CSafeDumper
    yaml_util.add_representers(dumper)
    with log_file.open('w', encoding='utf-8') as l_file:
        yaml.dump(diffs, l_file, Dumper=dumper)


def merge_map(map_pair: tuple, rstb_calc: rstb.SizeCalculator, no_del: bool = False,
              link_del: bool = False, verbose: bool = False) -> {}:
    """
    Merges changes to a mainfield map and returns the RSTB values

    :param map_pair: A tuple containing class:`Map` to merge and the changes as a dict
    :type map_pair: tuple
    :param rstb_calc: An `rstb` library SizeCalculator object
    :type rstb_calc: class:`rstb.SizeCalculator`
    :param verbose: Whether to display verbose output, defaults to False
    :type verbose: bool, optional
    :return: Returns a dict containing the aoc and base RSTB paths for the merged map units along
    with their new size values
    :rtype: dict of str: int
    """
    map_unit, changes = map_pair
    if verbose:
        print(f'Merging {len(changes)} versions of {"_".join(map_unit)}...')
    new_map = get_stock_map(map_unit)
    stock_hashes = [obj['HashId'] for obj in new_map['Objs']]
    for hash_id, actor in changes['mod'].items():
        try:
            new_map['Objs'][stock_hashes.index(hash_id)] = deepcopy(actor)
        except ValueError:
            changes['add'].append(actor)
    if not no_del:
        for map_del in sorted(changes['del'], key=lambda change: stock_hashes.index(change) \
                              if change in stock_hashes else -1, reverse=True):
            if map_del in stock_hashes:
                try:
                    new_map['Objs'].pop(stock_hashes.index(map_del))
                except IndexError:
                    try:
                        obj_to_delete = next(
                            iter([actor for actor in new_map['Objs'] if actor['HashId'] == map_del])
                        )
                        new_map['Objs'].remove(obj_to_delete)
                    except (StopIteration, ValueError):
                        print(f'Could not delete actor with HashId {map_del}')
    new_map['Objs'].extend(
        [change for change in changes['add'] if change['HashId'] not in stock_hashes]
    )
    new_map['Objs'].sort(key=lambda actor: actor['HashId'])

    aoc_out: Path = util.get_master_modpack_dir() / 'aoc' / '0010' / 'Map' / \
        'MainField' / map_unit.section / \
        f'{map_unit.section}_{map_unit.type}.smubin'
    aoc_out.parent.mkdir(parents=True, exist_ok=True)
    aoc_bytes = byml.Writer(new_map, be=True).get_bytes()
    aoc_out.write_bytes(util.compress(aoc_bytes))
    new_map['Objs'] = [obj for obj in new_map['Objs']
                       if not obj['UnitConfigName'].startswith('DLC')]
    (util.get_master_modpack_dir() / 'content' / 'Map' /
     'MainField' / map_unit.section).mkdir(parents=True, exist_ok=True)
    base_out = util.get_master_modpack_dir() / 'content' / 'Map' / 'MainField' / \
        map_unit.section / f'{map_unit.section}_{map_unit.type}.smubin'
    base_out.parent.mkdir(parents=True, exist_ok=True)
    base_bytes = byml.Writer(new_map, be=True).get_bytes()
    base_out.write_bytes(util.compress(base_bytes))
    return {
        'aoc': (
            f'Aoc/0010/Map/MainField/{map_unit.section}/{map_unit.section}_{map_unit.type}.mubin',
            rstb_calc.calculate_file_size_with_ext(aoc_bytes, True, '.mubin')
        ),
        'main': (
            f'Map/MainField/{map_unit.section}/{map_unit.section}_{map_unit.type}.mubin',
            rstb_calc.calculate_file_size_with_ext(base_bytes, True, '.mubin')
        )
    }


def merge_maps(no_del: bool = False, link_del: bool = False, verbose: bool = False, 
               original_pool: Pool = None):
    """Merges all installed modifications to mainfield maps"""
    aoc_pack = util.get_master_modpack_dir() / 'aoc' / '0010' / \
        'Pack' / 'AocMainField.pack'
    if not aoc_pack.exists() or aoc_pack.stat().st_size > 0:
        print('Emptying AocMainField.pack...')
        aoc_pack.parent.mkdir(parents=True, exist_ok=True)
        aoc_pack.write_bytes(b'')
    shutil.rmtree(str(util.get_master_modpack_dir() /
                      'aoc' / '0010' / 'Map' / 'MainField'), ignore_errors=True)
    shutil.rmtree(str(util.get_master_modpack_dir() /
                      'content' / 'Map' / 'MainField'), ignore_errors=True)
    log_path = util.get_master_modpack_dir() / 'logs' / 'map.log'
    if log_path.exists():
        log_path.unlink()
    print('Loading map mods...')
    map_diffs = get_all_map_diffs()
    if not map_diffs:
        print('No map merge necessary')
        return

    rstb_vals = {}
    rstb_calc = rstb.SizeCalculator()
    print('Merging modded map units...')
    num_threads = min(cpu_count() - 1, len(map_diffs))
    pool = original_pool or Pool(processes=num_threads)
    rstb_results = pool.map(partial(merge_map, rstb_calc=rstb_calc, no_del=no_del,
                                    link_del=link_del, verbose=verbose), list(map_diffs.items()))
    for result in rstb_results:
        rstb_vals[result['aoc'][0]] = result['aoc'][1]
        rstb_vals[result['main'][0]] = result['main'][1]
    if not original_pool:
        pool.close()
        pool.join()

    print('Adjusting RSTB...')
    with log_path.open('w', encoding='utf-8') as l_file:
        for canon, val in rstb_vals.items():
            l_file.write(f'{canon},{val}\n')
    print('Map merge complete')


def get_dungeonstatic_diff(file: Path) -> dict:
    """Returns the changes made to the Static.smubin containing shrine entrance coordinates

    :param file: The Static.mubin file to diff
    :type file: class:`pathlib.Path`
    :return: Returns a dict of shrines and their updated entrance coordinates
    :rtype: dict of str: dict
    """
    base_file = util.get_game_file(
        'aoc/0010/Map/CDungeon/Static.smubin', aoc=True)
    base_pos = byml.Byml(
        util.decompress_file(str(base_file))
    ).parse()['StartPos']

    mod_pos = byml.Byml(
        util.decompress_file(str(file))
    ).parse()['StartPos']

    base_dungeons = [dungeon['Map'] for dungeon in base_pos]
    diffs = {}
    for dungeon in mod_pos:
        if dungeon['Map'] not in base_dungeons:
            diffs[dungeon['Map']] = dungeon
        else:
            base_dungeon = base_pos[base_dungeons.index(dungeon['Map'])]
            if dungeon['Rotate'] != base_dungeon['Rotate']:
                diffs[dungeon['Map']] = {
                    'Rotate': dungeon['Rotate']
                }
            if dungeon['Translate'] != base_dungeon['Translate']:
                if dungeon['Map'] not in diffs:
                    diffs[dungeon['Map']] = {}
                diffs[dungeon['Map']]['Translate'] = dungeon['Translate']

    return diffs


def merge_dungeonstatic(diffs: dict = None):
    """Merges all changes to the CDungeon Static.smubin"""
    if not diffs:
        diffs = {}
        loader = yaml.CSafeLoader
        yaml_util.add_constructors(loader)
        for mod in [mod for mod in util.get_installed_mods() \
                    if (mod.path / 'logs' / 'dstatic.yml').exists()]:
            diffs.update(
                yaml.load(
                    (mod.path / 'logs' / 'dstatic.yml').read_bytes(),
                    Loader=loader
                )
            )

    if not diffs:
        return

    new_static = byml.Byml(
        util.decompress_file(
            str(util.get_game_file('aoc/0010/Map/CDungeon/Static.smubin'))
        )
    ).parse()

    base_dungeons = [dungeon['Map'] for dungeon in new_static['StartPos']]
    for dungeon, diff in diffs.items():
        if dungeon not in base_dungeons:
            new_static['StartPos'].append(diff)
        else:
            for key, value in diff.items():
                new_static['StartPos'][base_dungeons.index(
                    dungeon)][key] = value

    output_static = util.get_master_modpack_dir() / 'aoc' / '0010' / 'Map' / \
        'CDungeon' / 'Static.smubin'
    output_static.parent.mkdir(parents=True, exist_ok=True)
    output_static.write_bytes(
        util.compress(byml.Writer(new_static, True).get_bytes())
    )


class MapMerger(mergers.Merger):
    NAME: str = 'maps'

    def __init__(self, no_del: bool = False, link_del: bool = False):
        super().__init__('map merge', 'Merges changes to actors in mainfield map units',
                         'map.yml', options={'no_del': no_del, 'link_del': link_del})

    def generate_diff(self, mod_dir: Path, modded_files: List[Union[Path, str]]):
        modded_mubins = [file for file in modded_files if isinstance(file, Path) and \
                         file.suffix == '.smubin' and 'MainField' in file.parts and '_' in file.name]
        if modded_mubins:
            return generate_modded_map_log(mod_dir, modded_mubins, no_del=self._options['no_del'], 
                                           link_del=self._options['link_del'])
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

    def get_mod_diff(self, mod: util.BcmlMod):
        if self.is_mod_logged(mod):
            with (mod.path / 'logs' / self._log_name).open('r', encoding='utf-8') as log:
                loader = yaml.CSafeLoader
                yaml_util.add_constructors(loader)
                return yaml.load(log, Loader=loader)
        else:
            return {}

    def get_all_diffs(self):
        diffs = []
        for mod in [mod for mod in util.get_installed_mods() if self.is_mod_logged(mod)]:
            diffs.append(self.get_mod_diff(mod))
        return diffs

    def consolidate_diffs(self, diffs: list):
        return get_all_map_diffs()

    def perform_merge(self):
        merge_maps(
            no_del=self._options['no_del'],
            link_del=self._options['link_del'],
            original_pool=self._pool
        )

    def get_checkbox_options(self):
        return [
            ('no_del', 'Never remove stock actors from merged maps'),
            ('link_del', 'Allow deleting actors with links from merged maps')
        ]


class DungeonStaticMerger(mergers.Merger):
    NAME: str = 'dungeonstatic'

    def __init__(self):
        super().__init__('shrine entry merge', 'Merges changes to shrine entrance coordinates',
                         'dstatic.yml', options={})
    
    def generate_diff(self, mod_dir: Path, modded_files: List[Union[Path, str]]):
        dstatic_path = mod_dir / 'aoc' / '0010' / 'Map' / 'CDungeon' / 'Static.smubin'
        if dstatic_path.exists():
            return get_dungeonstatic_diff(dstatic_path)
        else:
            return {}

    def log_diff(self, mod_dir: Path, diff_material: Union[dict, List[Path]]):
        if isinstance(diff_material, List):
            diff_material = self.generate_diff(mod_dir, diff_material)
        if diff_material:
            with (mod_dir / 'logs' / self._log_name).open('w', encoding='utf-8') as log:
                dumper = yaml.CSafeDumper
                yaml_util.add_representers(dumper)
                yaml.dump(diff_material, log, Dumper=dumper)

    def get_mod_diff(self, mod: util.BcmlMod):
        if self.is_mod_logged(mod):
            with (mod.path / 'logs' / self._log_name).open('r', encoding='utf-8') as log:
                loader = yaml.CSafeLoader
                yaml_util.add_constructors(loader)
                return yaml.load(log, Loader=loader)
        else:
            return {}

    def get_all_diffs(self):
        diffs = []
        for mod in [mod for mod in util.get_installed_mods() if self.is_mod_logged(mod)]:
            diffs.append(self.get_mod_diff(mod))
        return diffs

    def consolidate_diffs(self, diffs: list):
        all_diffs = {}
        for diff in diffs:
            all_diffs.update(diff)
        return all_diffs

    def perform_merge(self):
        merge_dungeonstatic(self.consolidate_diffs(self.get_all_diffs()))

    def get_checkbox_options(self):
        return []
