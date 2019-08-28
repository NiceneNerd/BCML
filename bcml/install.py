"""Provides features for installing, creating, and mananging BCML mods"""
# Copyright 2019 Nicene Nerd <macadamiadaze@gmail.com>
# Licensed under GPLv3+
# pylint: disable=too-many-lines
import datetime
import os
import shutil
import subprocess
from configparser import ConfigParser
from fnmatch import fnmatch
from functools import partial
from multiprocessing import Pool, cpu_count
from pathlib import Path
from typing import Union, List
from xml.dom import minidom

import aamp.yaml_util
import byml
from byml import yaml_util
import rstb
import sarc
import wszst_yaz0
import xxhash
import yaml

from bcml import pack, texts, util, data, merge, rstable, mubin
from bcml.util import BcmlMod

RSTB_EXCLUDE = ['.pack', '.bgdata', '.txt', '.bgsvdata', '.yml',
                '.bat', '.ini', '.png', '.bfstm', '.py', '.sh']


def open_mod(path: Path) -> Path:
    """
    Extracts a provided mod and returns the root path of the graphicpack inside

    :param path: The path to the mod archive.
    :type path: class:`pathlib.Path`
    :returns: The path to the extracted root of the mod where the rules.txt file is found.
    :rtype: class:`pathlib.Path`
    """
    if isinstance(path, str):
        path = Path(path)
    tmpdir = util.get_work_dir() / f'tmp_{xxhash.xxh32(str(path)).hexdigest()}'
    formats = ['.rar', '.zip', '.7z', '.bnp']
    if tmpdir.exists():
        shutil.rmtree(tmpdir, ignore_errors=True)
    if path.suffix.lower() in formats:
        x_args = [str(util.get_exec_dir() / 'helpers' / '7z.exe'),
                  'x', str(path), f'-o{str(tmpdir)}']
        subprocess.run(x_args, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, creationflags=util.CREATE_NO_WINDOW)
    else:
        raise Exception(
            'The mod provided was not a supported archive (BNP, ZIP, RAR, or 7z).')
    if not tmpdir.exists():
        raise Exception('No files were extracted.')
    rulesdir = tmpdir
    found_rules = (rulesdir / 'rules.txt').exists()
    if not found_rules:
        for subdir in tmpdir.rglob('*'):
            if (subdir / 'rules.txt').exists():
                rulesdir = subdir
                found_rules = True
                break
        if not found_rules:
            raise Exception('No rules.txt was found in this mod.')
    return rulesdir


def get_next_priority() -> int:
    """ Gets the next available mod priority """
    i = 100
    while list(util.get_modpack_dir().glob(f'{i:04}_*')):
        i += 1
    return i


def threaded_aamp_diffs(file_info: tuple, tmp_dir: Path):
    """An interface for using a multiprocessing pool with `get_aamp_diff()`"""
    try:
        return (file_info[0], merge.get_aamp_diff(file_info[1], tmp_dir))
    except FileNotFoundError:
        return (file_info[0], None)


def find_modded_files(tmp_dir: Path, deep_merge: bool = False, verbose: bool = False,
                      guess: bool = False) -> (dict, list, dict):
    """
    Detects all of the modified files in an extracted mod

    :param tmp_dir: The path to the base directory of the mod.
    :type tmp_dir: class:`pathlib.Path`
    :param deep_merge: Whether to log diffs for individual AAMP and BYML files, defaults to False
    :type deep_merge: bool, optional
    :param verbose: Specifies whether to return more detailed output
    :type verbose: bool, optional
    :returns: Returns a tuple with a dict of modified files and the RSTB entries, a list of changes,
    and (if deep merge) diffs of modded BYML and AAMP files
    :rtype: (dict of class:`pathlib.Path`: int, list of str, dict of str: str)
    """
    modded_files = {}
    log = []
    aamp_diffs = {}
    aamps_to_diff = []
    rstb_path: Path = tmp_dir / 'content' / 'System' / \
        'Resource' / 'ResourceSizeTable.product.srsizetable'
    if rstb_path.exists():
        rstb_path.unlink()
    aoc_field = tmp_dir / 'aoc' / '0010' / 'Pack' / 'AocMainField.pack'
    if aoc_field.exists() and aoc_field.stat().st_size > 0:
        with aoc_field.open('rb') as a_file:
            sarc.read_file_and_make_sarc(a_file).extract_to_dir(str(tmp_dir / 'aoc' / '0010'))
        aoc_field.write_bytes(b'')
    for file in tmp_dir.rglob('**/*'):
        if file.is_file():
            canon = util.get_canon_name(file.relative_to(tmp_dir).as_posix())
            if canon is None:
                if verbose:
                    log.append(
                        f'Ignored unknown file {file.relative_to(tmp_dir).as_posix()}')
                continue
            if util.is_file_modded(canon, file, True):
                size = rstable.calculate_size(file)
                if size == 0 and guess:
                    if file.suffix in util.AAMP_EXTS:
                        size = rstable.guess_aamp_size(file)
                    elif file.suffix in ['.bfres', '.sbfres']:
                        size = rstable.guess_bfres_size(file)
                modded_files[canon] = {
                    'path': file.relative_to(tmp_dir),
                    'rstb': size,
                    'nested': False
                }
                if verbose:
                    log.append(f'Found modded file {canon}')
                if canon in util.get_hash_table() and deep_merge and util.is_file_aamp(str(file)):
                    try:
                        aamps_to_diff.append(
                            (file.relative_to(tmp_dir).as_posix(),
                             file)
                        )
                    except FileNotFoundError:
                        pass
            else:
                if 'Aoc/0010/Map/MainField' in canon:
                    file.unlink()
                if verbose:
                    log.append(f'Ignored unmodded file {canon}')
                continue
    if aamps_to_diff:
        pool = Pool()
        aamp_thread_partial = partial(threaded_aamp_diffs, tmp_dir=tmp_dir)
        aamp_results = pool.map(aamp_thread_partial, aamps_to_diff)
        pool.close()
        pool.join()
        for file, diff in aamp_results:
            if diff:
                aamp_diffs[file] = diff
    total = len(modded_files)
    log.append(f'Found {total} modified file{"s" if total > 1 else ""}')
    return modded_files, log, aamp_diffs


def find_modded_sarc_files(mod_sarc: sarc.SARC, name: str, tmp_dir: Path, aoc: bool = False,
                           nest_level: int = 0, deep_merge: bool = False, guess: bool = False,
                           verbose: bool = False) -> (dict, list):
    """
    Detects all of the modified files in a SARC

    :param mod_sarc: The SARC to scan for modded files.
    :type mod_sarc: class:`sarc.SARC`
    :param tmp_dir: The path to the base directory of the mod.
    :type tmp_dir: class:`pathlib.Path`
    :param name: The name of the SARC which contains the current SARC.
    :type name: str
    :param aoc: Specifies whether the SARC is DLC content, defaults to False.
    :type aoc: bool, optional
    :param nest_level: The depth to which the current SARC is nested in more SARCs, defaults to 0
    :type nest_level: int, optional
    :param deep_merge: Whether to log diffs for individual AAMP and BYML files, defaults to False
    :type deep_merge: bool, optional
    :param verbose: Specifies whether to return more detailed output
    :type verbose: bool, optional
    """
    modded_files = {}
    log = []
    aamp_diffs = {}
    indent = '  ' * (nest_level + 1)
    for file in mod_sarc.list_files():
        canon = file.replace('.s', '.')
        if aoc:
            canon = 'Aoc/0010/' + canon
        ext = os.path.splitext(file)[1]
        contents = mod_sarc.get_file_data(file).tobytes()
        contents = util.unyaz_if_needed(contents)
        if util.is_file_modded(canon, contents, True):
            rstbsize = rstb.SizeCalculator().calculate_file_size_with_ext(contents, True, ext)
            if rstbsize == 0 and guess:
                if ext in util.AAMP_EXTS:
                    rstbsize = rstable.guess_aamp_size(contents, ext)
                elif ext in ['.bfres', '.sbfres']:
                    rstbsize = rstable.guess_bfres_size(
                        contents, Path(canon).name)
            modded_files[canon] = {
                'path': str(name).replace('\\', '/') + '//' + file,
                'rstb': rstbsize,
                'nested': True
            }
            if verbose:
                log.append(
                    f'{indent}Found modded file {canon} in {str(name).replace("//", "/")}')
            if util.is_file_sarc(canon):
                try:
                    nest_sarc = sarc.SARC(contents)
                except ValueError:
                    continue
                sub_mod_files,\
                sub_mod_log,\
                sub_mod_diffs = find_modded_sarc_files(nest_sarc,
                                                       modded_files[canon]['path'],
                                                       tmp_dir=tmp_dir,
                                                       nest_level=nest_level + 1, aoc=aoc,
                                                       verbose=verbose, guess=guess,
                                                       deep_merge=deep_merge)
                modded_files.update(sub_mod_files)
                aamp_diffs.update(sub_mod_diffs)
                log.extend(sub_mod_log)
            elif canon in util.get_hash_table() and deep_merge and util.is_file_aamp(str(file)):
                path = tmp_dir.as_posix() + '/' + modded_files[canon]['path']
                try:
                    aamp_diffs[modded_files[canon]['path']
                               ] = merge.get_aamp_diff(path, tmp_dir)
                except (FileNotFoundError, KeyError, ValueError):
                    pass
        else:
            if verbose:
                log.append(
                    f'{indent}Ignored unmodded file {canon} in {str(name).replace("//", "/")}')
    return modded_files, log, aamp_diffs


def generate_logs(tmp_dir: Path, verbose: bool = False, leave_rstb: bool = False,
                  shrink_rstb: bool = False, guess: bool = False, no_packs=True,
                  no_texts: bool = False, no_gamedata: bool = False, no_savedata: bool = False,
                  no_actorinfo: bool = False, no_map: bool = False, deep_merge: bool = True):
    """Analyzes a mod and generates BCML log files containing its changes"""
    print('Scanning for modified files...')
    modded_files, rstb_changes, aamp_diffs = find_modded_files(
        tmp_dir, verbose=verbose, deep_merge=deep_merge, guess=guess)
    if rstb_changes:
        print('\n'.join(rstb_changes))

    modded_sarc_files = {}
    is_text_mod = False
    bootup_paths = []
    print('Scanning modified pack files...')
    for file in modded_files:
        if fnmatch(file, '*Bootup_????.pack') and not no_texts:
            is_text_mod = True
            bootup_paths.append(modded_files[file]['path'])
            continue
    sarc_files = [file for file in modded_files if util.is_file_sarc(file) and not fnmatch(
        file, '*Bootup_????.pack')]
    if sarc_files:
        num_threads = min(len(sarc_files), cpu_count())
        pool = Pool(processes=num_threads)
        thread_sarc_search = partial(threaded_find_modded_sarc_files, modded_files=modded_files,
                                     tmp_dir=tmp_dir, deep_merge=deep_merge, verbose=verbose,
                                     guess=guess)
        results = pool.map(thread_sarc_search, sarc_files)
        pool.close()
        pool.join()
        for result in results:
            modded_sarcs, sarc_changes, nested_diffs = result
            if modded_sarcs:
                modded_sarc_files.update(modded_sarcs)
                if deep_merge:
                    aamp_diffs.update(nested_diffs)
                if sarc_changes:
                    print('\n'.join(sarc_changes))
        mod_sarc_count = len(sarc_files)
        print(
            f'Found {len(sarc_files)} modded pack file{"s" if mod_sarc_count != 1 else ""}')

    if not modded_files:
        raise Exception('No modified files were found. Very unusual.')
    no_packs = no_packs or len(sarc_files) == 0

    text_mods = {}
    if is_text_mod:
        print('Text modifications detected, analyzing...')
        for bootup_path in bootup_paths:
            try:
                util.get_game_file(
                    bootup_path.relative_to('content').as_posix())
            except FileNotFoundError:
                continue
            tmp_text = util.get_work_dir() / 'tmp_text'
            modded_texts, added_text_store, lang = texts.get_text_mods_from_bootup(
                str(tmp_dir / bootup_path), tmp_text, verbose)
            text_mods[lang] = (modded_texts, added_text_store)

    modded_actors = {}
    if 'Actor/ActorInfo.product.byml' in modded_files and not no_actorinfo:
        print('Actor info modified, analyzing...')
        with (tmp_dir / 'content/Actor/ActorInfo.product.sbyml').open('rb') as a_file:
            actorinfo = byml.Byml(wszst_yaz0.decompress(a_file.read())).parse()
        modded_actors = data.get_modded_actors(actorinfo)
    else:
        no_actorinfo = True

    modded_bgentries = {}
    if 'GameData/gamedata.sarc' in modded_sarc_files and not no_gamedata:
        print('Game data modified, analyzing...')
        with (tmp_dir / modded_files['Pack/Bootup.pack']['path']).open('rb') as b_file:
            bootup = sarc.read_file_and_make_sarc(b_file)
        gamedata = sarc.SARC(wszst_yaz0.decompress(
            bootup.get_file_data('GameData/gamedata.ssarc')))
        del bootup
        modded_bgdata = data.get_modded_bgdata(gamedata)
        modded_bgentries = data.get_modded_gamedata_entries(modded_bgdata)
    else:
        no_gamedata = True

    modded_bgsventries = []
    if 'GameData/savedataformat.sarc' in modded_sarc_files and not no_savedata:
        print('Save data modified, analyzing...')
        with (tmp_dir / modded_files['Pack/Bootup.pack']['path']).open('rb') as b_file:
            bootup = sarc.read_file_and_make_sarc(b_file)
        savedata = sarc.SARC(wszst_yaz0.decompress(
            bootup.get_file_data('GameData/savedataformat.ssarc')))
        del bootup
        if data.is_savedata_modded(savedata):
            modded_bgsventries.extend(
                data.get_modded_savedata_entries(savedata))
    else:
        no_savedata = True

    modded_mubins = [str(file['path']) for canon, file in modded_files.items(
    ) if fnmatch(Path(canon).name, '[A-Z]-[0-9]_*.mubin')]
    no_map = no_map or len(modded_mubins) == 0
    if not no_map:
        mubin.log_modded_maps(tmp_dir, modded_mubins)

    dstatic_diff = None
    if (tmp_dir / 'aoc' / '0010' / 'Map' / 'CDungeon' / 'Static.smubin').exists():
        dstatic_diff = mubin.get_dungeonstatic_diff(
            tmp_dir / 'aoc' / '0010' / 'Map' / 'CDungeon' / 'Static.smubin')

    if deep_merge:
        deep_merge = bool(aamp_diffs)

    print('Saving logs...')
    (tmp_dir / 'logs').mkdir(parents=True, exist_ok=True)
    with Path(tmp_dir / 'logs' / 'rstb.log').open('w', encoding='utf-8') as r_file:
        r_file.write('name,rstb,path\n')
        modded_files.update(modded_sarc_files)
        for file in modded_files:
            ext = os.path.splitext(file)[1]
            if ext not in RSTB_EXCLUDE and 'ActorInfo' not in file:
                r_file.write('{},{},{}\n'.format(file, modded_files[file]["rstb"], str(
                    modded_files[file]["path"]).replace('\\', '/')))
    if not no_packs:
        with Path(tmp_dir / 'logs' / 'packs.log').open('w', encoding='utf-8') as p_file:
            p_file.write('name,path\n')
            for file in modded_files:
                name, ext = os.path.splitext(file)
                if ext in util.SARC_EXTS and not modded_files[file]['nested'] \
                   and not name.startswith('Dungeon'):
                    p_file.write(f'{file},{modded_files[file]["path"]}\n')
    if is_text_mod:
        for lang in text_mods:
            with Path(tmp_dir / 'logs' / f'texts_{lang}.yml').open('w', encoding='utf-8') as t_file:
                yaml.dump(text_mods[lang][0], t_file)
            text_sarc = text_mods[lang][1]
            if text_sarc is not None:
                with Path(tmp_dir / 'logs' / f'newtexts_{lang}.sarc').open('wb') as s_file:
                    text_sarc.write(s_file)
    dumper = yaml.CDumper
    yaml_util.add_representers(dumper)
    aamp.yaml_util.register_representers(dumper)
    dumper.__aamp_reader = None # pylint: disable=protected-access
    aamp.yaml_util._get_pstruct_name = lambda reader, idx, k, parent_crc32: k # pylint: disable=protected-access
    if not no_gamedata:
        with (tmp_dir / 'logs' / 'gamedata.yml').open('w', encoding='utf-8') as g_file:
            yaml.dump(modded_bgentries, g_file, Dumper=dumper, allow_unicode=True, encoding='utf-8',
                      default_flow_style=None)
    if not no_savedata:
        with (tmp_dir / 'logs' / 'savedata.yml').open('w', encoding='utf-8') as s_file:
            yaml.dump(modded_bgsventries, s_file, Dumper=dumper, allow_unicode=True,
                      encoding='utf-8', default_flow_style=None)
    if not no_actorinfo:
        with (tmp_dir / 'logs' / 'actorinfo.yml').open('w', encoding='utf-8') as a_file:
            yaml.dump(modded_actors, a_file, Dumper=dumper, allow_unicode=True, encoding='utf-8',
                      default_flow_style=None)
    if deep_merge:
        with (tmp_dir / 'logs' / 'deepmerge.yml').open('w', encoding='utf-8') as d_file:
            yaml.dump(aamp_diffs, d_file, Dumper=dumper, allow_unicode=True,
                      encoding='utf-8', default_flow_style=None)
    if dstatic_diff:
        with (tmp_dir / 'logs' / 'dstatic.yml').open('w', encoding='utf-8') as a_file:
            yaml.dump(dstatic_diff, a_file, Dumper=dumper, allow_unicode=True, encoding='utf-8',
                      default_flow_style=None)
    if leave_rstb:
        Path(tmp_dir / 'logs' / '.leave').open('w', encoding='utf-8').close()
    if shrink_rstb:
        Path(tmp_dir / 'logs' / '.shrink').open('w', encoding='utf-8').close()

    return is_text_mod, no_texts, no_packs, no_gamedata, no_savedata, no_actorinfo, deep_merge, \
           no_map, modded_files


def threaded_find_modded_sarc_files(file: str, modded_files: dict, tmp_dir: Path, deep_merge: bool,
                                    verbose: bool, guess: bool = False):
    """Interface for multiprocessing `find_modded_sarc_files()`"""
    with Path(tmp_dir / modded_files[file]['path']).open('rb') as s_file:
        mod_sarc = sarc.read_file_and_make_sarc(s_file)
    if not mod_sarc:
        print(f'Skipped broken pack {file}')
        return {}, [], {}
    return find_modded_sarc_files(mod_sarc, modded_files[file]['path'],
                                  tmp_dir=tmp_dir,
                                  aoc=('aoc' in file.lower()),
                                  verbose=verbose, deep_merge=deep_merge, guess=guess)


def refresh_cemu_mods():
    """ Updates Cemu's enabled graphic packs """
    setpath = util.get_cemu_dir() / 'settings.xml'
    if not setpath.exists():
        raise FileNotFoundError('The Cemu settings file could not be found.')
    setread = ''
    with setpath.open('r') as setfile:
        for line in setfile:
            setread += line.strip()
    settings = minidom.parseString(setread)
    try:
        gpack = settings.getElementsByTagName('GraphicPack')[0]
    except IndexError:
        gpack = settings.createElement('GraphicPack')
        settings.appendChild(gpack)
    for entry in gpack.getElementsByTagName('Entry'):
        if 'BCML' in entry.getElementsByTagName('filename')[0].childNodes[0].data:
            gpack.removeChild(entry)
    bcmlentry = settings.createElement('Entry')
    entryfile = settings.createElement('filename')
    entryfile.appendChild(settings.createTextNode(
        f'graphicPacks\\BCML\\9999_BCML\\rules.txt'))
    entrypreset = settings.createElement('preset')
    entrypreset.appendChild(settings.createTextNode(''))
    bcmlentry.appendChild(entryfile)
    bcmlentry.appendChild(entrypreset)
    gpack.appendChild(bcmlentry)
    for mod in util.get_installed_mods():
        modentry = settings.createElement('Entry')
        entryfile = settings.createElement('filename')
        entryfile.appendChild(settings.createTextNode(
            f'graphicPacks\\BCML\\{mod.path.parts[-1]}\\rules.txt'))
        entrypreset = settings.createElement('preset')
        entrypreset.appendChild(settings.createTextNode(''))
        modentry.appendChild(entryfile)
        modentry.appendChild(entrypreset)
        gpack.appendChild(modentry)
    settings.writexml(setpath.open('w', encoding='utf-8'), addindent='    ', newl='\n')


def install_mod(mod: Path, verbose: bool = False, no_packs: bool = False, no_texts: bool = False,
                no_gamedata: bool = False, no_savedata: bool = False, no_actorinfo: bool = False,
                no_map: bool = False, leave_rstb: bool = False, shrink_rstb: bool = False,
                guess: bool = False, wait_merge: bool = False, deep_merge: bool = False,
                insert_priority: int = 0):
    """
    Installs a graphic pack mod, merging RSTB changes and optionally packs and texts

    :param mod: Path to the mod to install. Must be a RAR, 7z, or ZIP archive or a graphicpack
    directory containing a rules.txt file.
    :type mod: class:`pathlib.Path`
    :param verbose: Whether to display more detailed output, defaults to False.
    :type verbose: bool, optional
    :param no_packs: Do not attempt to merge pack files, defaults to False.
    :type no_packs: bool, optional
    :param no_texts: Do not attempt to merge text files, defaults to False.
    :type no_texts: bool, optional
    :param no_gamedata: Do not attempt to merge game data, defaults to False.
    :type no_gamedata: bool, optional
    :param no_savedata: Do not attempt to merge save data, defaults to False.
    :type no_savedata: bool, optional
    :param no_actorinfo: Do not attempt to merge actor info, defaults to False.
    :type no_actorinfo: bool, optional
    :param no_map: Do not attempt to merge map units, defaults to False.
    :type no_map: bool, optional
    :param leave_rstb: Do not remove RSTB entries when the proper value can't be calculated,
    defaults to False.
    :type leave_rstb: bool, optional
    :param shrink_rstb: Shrink RSTB values where possible, defaults to False.
    :type shrink_rstb: bool, optional
    :param guess: Estimate RSTB values for AAMP and BFRES files, defaults to False.
    :type guess: bool, optional
    :param wait_merge: Install mod and log changes, but wait to run merge manually,
    defaults to False.
    :type wait_merge: bool, optional
    :param deep_merge: Attempt to merge changes within individual AAMP files, defaults to False.
    :type deep_merge: bool, optional
    :param insert_priority: Insert mod(s) at priority specified, defaults to get_next_priority().
    :type insert_priority: int
    """
    if insert_priority == 0:
        insert_priority = get_next_priority()
    util.create_bcml_graphicpack_if_needed()
    if isinstance(mod, str):
        mod = Path(mod)
    if mod.is_file():
        print('Extracting mod...')
        tmp_dir = open_mod(mod)
    elif mod.is_dir():
        if (mod / 'rules.txt').exists():
            print(f'Loading mod from {str(mod)}...')
            tmp_dir = mod
        else:
            print(f'Cannot open mod at {str(mod)}, no rules.txt found')
            return
    else:
        print(f'Error: {str(mod)} is neither a valid file nor a directory')
        return

    rules = ConfigParser()
    rules.read(tmp_dir / 'rules.txt')
    mod_name = str(rules['Definition']['name']).strip(' "\'')
    print(f'Identified mod: {mod_name}')

    logs = tmp_dir / 'logs'
    if logs.exists():
        print('This mod supports Quick Install! Loading changes...')
        no_packs = no_packs or (not (logs / 'packs.log').exists())
        no_gamedata = no_gamedata or (not (logs / 'gamedata.yml').exists())
        no_savedata = no_savedata or (not (logs / 'savedata.yml').exists())
        no_actorinfo = no_actorinfo or (not (logs / 'actorinfo.yml').exists())
        no_map = no_map or (not (logs / 'map.yml').exists())
        deep_merge = (logs / 'deepmerge.yml').exists()
        if not no_texts:
            text_mods = texts.get_modded_languages(tmp_dir)
            is_text_mod = len(text_mods) > 0 # pylint: disable=len-as-condition
    else:
        is_text_mod, no_texts, no_packs, no_gamedata, no_savedata, no_actorinfo, deep_merge, \
            no_map, _ = \
                generate_logs(
                    tmp_dir=tmp_dir,
                    verbose=verbose,
                    leave_rstb=leave_rstb,
                    shrink_rstb=shrink_rstb,
                    guess=guess,
                    no_packs=no_packs,
                    no_texts=no_texts,
                    no_gamedata=no_gamedata,
                    no_savedata=no_savedata,
                    no_actorinfo=no_actorinfo,
                    no_map=no_map,
                    deep_merge=deep_merge
                )

    priority = insert_priority
    print(f'Assigned mod priority of {priority}')
    mod_id = util.get_mod_id(mod_name, priority)
    mod_dir = util.get_modpack_dir() / mod_id

    for existing_mod in util.get_installed_mods():
        if existing_mod.priority >= priority:
            priority_shifted = existing_mod.priority + 1
            new_id = util.get_mod_id(existing_mod.name, priority_shifted)
            new_path = util.get_modpack_dir() / new_id
            shutil.move(str(existing_mod.path), str(new_path))
            existing_mod_rules = ConfigParser()
            existing_mod_rules.read(str(new_path / 'rules.txt'))
            existing_mod_rules['Definition']['fsPriority'] = str(priority_shifted)
            with (new_path / 'rules.txt').open('w', encoding='utf-8') as r_file:
                existing_mod_rules.write(r_file)

    mod_dir.parent.mkdir(parents=True, exist_ok=True)
    print()
    print(f'Moving mod to {str(mod_dir)}...')
    if mod.is_file():
        shutil.move(str(tmp_dir), str(mod_dir))
    elif mod.is_dir():
        shutil.copytree(str(tmp_dir), str(mod_dir))

    rulepath = os.path.basename(rules['Definition']['path']).replace('"', '')
    rules['Definition']['path'] = f'ι BCML: DON\'T TOUCH/{rulepath}'
    rules['Definition']['fsPriority'] = str(priority)
    with Path(mod_dir / 'rules.txt').open('w', encoding='utf-8') as r_file:
        rules.write(r_file)

    output_mod = BcmlMod(mod_name, priority, mod_dir)
    try:
        util.get_mod_link_meta(rules)
        util.get_mod_preview(output_mod, rules)
    except (FileNotFoundError, KeyError, IndexError, UnboundLocalError):
        pass

    print(f'Enabling {mod_name} in Cemu...')
    refresh_cemu_mods()

    if wait_merge:
        print('Mod installed, merge still pending...')
    else:
        print('Performing merges...')
        print()
        if not no_packs:
            pack.merge_installed_packs(False, verbose=verbose)
        if is_text_mod:
            for lang in text_mods:
                texts.merge_texts(lang, verbose=verbose)
        if not no_gamedata:
            data.merge_gamedata(verbose)
        if not no_savedata:
            data.merge_savedata(verbose)
        if not no_actorinfo:
            data.merge_actorinfo(verbose)
        if not no_map:
            mubin.merge_maps()
        if deep_merge:
            merge.deep_merge(verbose)
        mubin.merge_dungeonstatic()
        if not deep_merge:
            rstable.generate_master_rstb(verbose)
        print()
        print(f'{mod_name} installed successfully!')
    return output_mod


def uninstall_mod(mod: Union[Path, BcmlMod, str], wait_merge: bool = False, verbose: bool = False):
    """
    Uninstalls the mod currently installed at the specified path and updates merges as needed

    :param mod: The mod to remove, as a path or a BcmlMod.
    :param wait_merge: Resort mods but don't remerge anything yet, defaults to False.
    :type wait_merge: bool, optional
    :param verbose: Whether to display more detailed output, defaults to False.
    :type verbose: bool, optional
    """
    path = Path(mod) if isinstance(
        mod, str) else mod.path if isinstance(mod, BcmlMod) else mod
    mod_name, mod_priority, _ = util.get_mod_info(
        path / 'rules.txt') if not isinstance(mod, BcmlMod) else mod
    print(f'Uninstalling {mod_name}...')
    pack_mods = pack.get_modded_packs_in_mod(mod)
    text_mods = texts.get_modded_languages(path)
    gamedata_mod = util.is_gamedata_mod(
        path) or 'content\\Pack\\Bootup.pack' in pack_mods
    savedata_mod = util.is_savedata_mod(
        path) or 'content\\Pack\\Bootup.pack' in pack_mods
    actorinfo_mod = util.is_actorinfo_mod(path)
    map_mod = util.is_map_mod(path)
    deepmerge_mods = merge.get_mod_deepmerge_files(mod)

    shutil.rmtree(str(path))
    next_mod = util.get_mod_by_priority(mod_priority + 1)
    if next_mod:
        print('Adjusting mod priorities...')
        change_mod_priority(next_mod, mod_priority,
                            wait_merge=True, verbose=verbose)
        print()

    if not wait_merge:
        if pack_mods:
            pack.merge_installed_packs(verbose, only_these=pack_mods)
        if text_mods:
            for lang in text_mods:
                (util.get_master_modpack_dir() / 'content' /
                 'Pack' / f'Bootup_{lang}.pack').unlink()
                texts.merge_texts(lang, verbose=verbose)
        if gamedata_mod:
            (util.get_master_modpack_dir() / 'logs' / 'gamedata.log').unlink()
            (util.get_master_modpack_dir() / 'logs' / 'gamedata.sarc').unlink()
            data.merge_gamedata(verbose)
        if savedata_mod:
            (util.get_master_modpack_dir() / 'logs' / 'savedata.log').unlink()
            (util.get_master_modpack_dir() / 'logs' / 'savedata.sarc').unlink()
            data.merge_savedata(verbose)
        if actorinfo_mod:
            data.merge_actorinfo(verbose)
        if map_mod:
            mubin.merge_maps()
        mubin.merge_dungeonstatic()
        if deepmerge_mods:
            merge.deep_merge(only_these=list(deepmerge_mods))
    print(f'{mod_name} has been uninstalled.')


def change_mod_priority(path: Path, new_priority: int, wait_merge: bool = False,
                        verbose: bool = False):
    """
    Changes the priority of a mod

    :param path: The path to the mod.
    :type path: class:`pathlib.Path`
    :param new_priority: The new priority of the mod.
    :type new_priority: int
    :param wait_merge: Resort priorities but don't remerge anything yet, defaults to False.
    :type wait_merge: bool, optional
    :param verbose: Whether to display more detailed output, defaults to False.
    :type verbose: bool, optional
    """
    mod = util.get_mod_info(path / 'rules.txt')
    print(
        f'Changing priority of {mod.name} from {mod.priority} to {new_priority}...')
    mods = util.get_installed_mods()
    if new_priority > mods[len(mods) - 1][1]:
        new_priority = len(mods) - 1
    mods.remove(mod)
    mods.insert(new_priority - 100, util.BcmlMod(mod.name, new_priority, path))
    remerge_packs = set()
    remerge_texts = texts.get_modded_languages(path)
    remerge_gamedata = util.is_gamedata_mod(
        path) or 'content\\Pack\\Bootup.pack' in remerge_packs
    remerge_savedata = util.is_savedata_mod(
        path) or 'content\\Pack\\Bootup.pack' in remerge_packs
    remerge_actorinfo = util.is_actorinfo_mod(path)
    remerge_map = util.is_map_mod(path)
    deepmerge = set()
    print('Resorting other affected mods...')
    for mod in mods:
        if mod.priority != (mods.index(mod) + 100):
            adjusted_priority = mods.index(mod) + 100
            mods.remove(mod)
            mods.insert(adjusted_priority - 100,
                        BcmlMod(mod.name, adjusted_priority, mod.path))
            if verbose:
                print(
                    f'Changing priority of {mod.name} from'
                    f'{mod.priority} to {adjusted_priority}...'
                )
    for mod in mods:
        if not mod.path.stem.startswith(f'{mod.priority:04}'):
            for mpack in pack.get_modded_packs_in_mod(mod):
                remerge_packs.add(mpack)
            remerge_actorinfo = util.is_actorinfo_mod(mod) or remerge_actorinfo
            remerge_gamedata = util.is_gamedata_mod(
                mod) or remerge_gamedata or 'content\\Pack\\Bootup.pack' in remerge_packs
            remerge_savedata = util.is_savedata_mod(
                mod) or remerge_savedata or 'content\\Pack\\Bootup.pack' in remerge_packs
            remerge_map = util.is_map_mod(mod) or remerge_map
            for mfile in merge.get_mod_deepmerge_files(mod):
                deepmerge.add(mfile)
            for lang in texts.get_modded_languages(mod.path):
                if lang not in remerge_texts:
                    remerge_texts.append(lang)
            new_mod_id = util.get_mod_id(mod[0], mod[1])
            shutil.move(str(mod[2]), str(mod[2].parent / new_mod_id))
            rules = ConfigParser()
            rules.read(str(mod.path.parent / new_mod_id / 'rules.txt'))
            rules['Definition']['fsPriority'] = str(mod[1])
            with (mod[2].parent / new_mod_id / 'rules.txt').open('w', encoding='utf-8') as r_file:
                rules.write(r_file)
            refresh_cemu_mods()
    if remerge_packs:
        if wait_merge:
            print('Pack merges affected, will need to remerge later')
        else:
            print('Pack merges affected, remerging packs...')
            pack.merge_installed_packs(verbose, only_these=list(remerge_packs))
            print()
    if remerge_texts:
        if wait_merge:
            print('Text merges affected, will need to remerge later')
        else:
            for lang in remerge_texts:
                print(
                    f'Text merges for {lang} affected, remerging texts for {lang}...')
                texts.merge_texts(lang, verbose=verbose)
                print()
    if remerge_gamedata:
        if wait_merge:
            print('Gamedata merges affected, will need to remerge later')
        else:
            print('Gamedata merges affected, remerging gamedata...')
            data.merge_gamedata(verbose)
            print()
    if remerge_savedata:
        if wait_merge:
            print('Savedata merges affected, will need to remerge later')
        else:
            print('Savedata merges affected, remerging savedata...')
            data.merge_savedata(verbose)
            print()
    if remerge_actorinfo:
        if wait_merge:
            print('Actor info merges affected, will need to remerge later')
        else:
            print('Actor info merges affected, remerging actor info...')
            data.merge_actorinfo(verbose)
            print()
    if remerge_map:
        if wait_merge:
            print('Map merges affected, will need to remerge later')
        else:
            print('Map merges affected, remerging map units...')
            mubin.merge_maps()
            print()
    if deepmerge:
        if wait_merge:
            print('Deep merge affected, will need to remerge later')
        else:
            print('Deep merge affected, remerging...')
            merge.deep_merge(verbose, only_these=list(deepmerge))
            print()
    if not wait_merge:
        mubin.merge_dungeonstatic()
    if wait_merge:
        print('Mods resorted, will need to remerge RSTB later')
    else:
        if not deepmerge:
            rstable.generate_master_rstb(verbose)
            print()
    print('Finished updating mod priorities.')


def refresh_merges(verbose: bool = False):
    """
    Runs RSTB, pack, and text merges together

    :param verbose: Whether to display more detailed output, defaults to False.
    :type verbose: bool, optional
    """
    print('Refreshing merged mods...')
    if not (util.get_master_modpack_dir() / 'content' / 'System' / 'Resource' /\
           'ResourceSizeTable.product.srsizetable').exists():
        (util.get_master_modpack_dir() / 'content' / 'System' /
         'Resource').mkdir(parents=True, exist_ok=True)
        shutil.copy(
            str(util.get_game_file('System/Resource/ResourceSizeTable.product.srsizetable')),
            str(util.get_master_modpack_dir() / 'content' / 'System' / 'Resource' /\
                'ResourceSizeTable.product.srsizetable')
        )
    pack.merge_installed_packs(verbose=False, even_one=True)
    for bootup in util.get_master_modpack_dir().rglob('content/Pack/Bootup_*'):
        lang = util.get_file_language(bootup)
        texts.merge_texts(lang, verbose=verbose)
    data.merge_gamedata(verbose)
    data.merge_savedata(verbose)
    data.merge_actorinfo(verbose)
    mubin.merge_maps(verbose)
    merge.deep_merge(verbose, wait_rstb=True)
    mubin.merge_dungeonstatic()
    rstable.generate_master_rstb(verbose)


def _clean_sarc(file: Path, hashes: dict, tmp_dir: Path):
    canon = util.get_canon_name(file.relative_to(tmp_dir))
    if canon not in hashes:
        return
    with file.open('rb') as s_file:
        base_sarc = sarc.read_file_and_make_sarc(s_file)
    if not base_sarc:
        return
    new_sarc = sarc.SARCWriter(True)
    can_delete = True
    for nest_file in base_sarc.list_files():
        canon = nest_file.replace('.s', '.')
        ext = Path(canon).suffix
        file_data = base_sarc.get_file_data(nest_file).tobytes()
        xhash = xxhash.xxh32(util.unyaz_if_needed(file_data)).hexdigest()
        if ext in ['.yml', '.bak']:
            continue
        if canon not in hashes or (xhash != hashes[canon] and ext not in util.AAMP_EXTS):
            can_delete = False
            new_sarc.add_file(nest_file, file_data)
    if can_delete:
        del new_sarc
        file.unlink()
    else:
        with file.open('wb') as s_file:
            if file.suffix.startswith('.s') and file.suffix != '.ssarc':
                s_file.write(wszst_yaz0.compress(new_sarc.get_bytes()))
            else:
                new_sarc.write(s_file)


def create_bnp_mod(mod: Path, output: Path, no_packs: bool = False, no_texts: bool = False,
                   no_gamedata: bool = False, no_savedata: bool = False,
                   no_actorinfo: bool = False, no_map: bool = False, leave_rstb: bool = False,
                   shrink_rstb: bool = False, guess: bool = False, deep_merge: bool = True):
    """
    Converts a graphic pack mod to BotW Nano Patch format

    :param mod: [description]
    :type mod: Path
    :param output: [description]
    :type output: Path
    :param no_packs: [description], defaults to False
    :type no_packs: bool, optional
    :param no_texts: [description], defaults to False
    :type no_texts: bool, optional
    :param no_gamedata: [description], defaults to False
    :type no_gamedata: bool, optional
    :param no_savedata: [description], defaults to False
    :type no_savedata: bool, optional
    :param no_actorinfo: [description], defaults to False
    :type no_actorinfo: bool, optional
    :param no_map: [description], defaults to False
    :type no_map: bool, optional
    :param leave_rstb: [description], defaults to False
    :type leave_rstb: bool, optional
    :param shrink_rstb: [description], defaults to False
    :type shrink_rstb: bool, optional
    :param guess: [description], defaults to False
    :type guess: bool, optional
    :param deep_merge: [description], defaults to True
    :type deep_merge: bool, optional
    """
    if isinstance(mod, str):
        mod = Path(mod)
    if mod.is_file():
        print('Extracting mod...')
        tmp_dir: Path = open_mod(mod)
    elif mod.is_dir():
        print(f'Loading mod from {str(mod)}...')
        tmp_dir: Path = util.get_work_dir() / \
            f'tmp_{xxhash.xxh32(str(mod)).hexdigest()}'
        shutil.copytree(str(mod), str(tmp_dir))
    else:
        print(f'Error: {str(mod)} is neither a valid file nor a directory')
        return

    logged_files = generate_logs(tmp_dir, leave_rstb=leave_rstb, shrink_rstb=shrink_rstb,
                                 guess=guess, no_packs=no_packs, no_texts=no_texts,
                                 no_gamedata=no_gamedata, no_savedata=no_savedata,
                                 no_actorinfo=no_actorinfo, no_map=no_map, deep_merge=deep_merge)[8]

    print('Removing unnecessary files...')
    if not no_map:
        print('  Removing map units...')
        for mubin_file in [file['path'] for canon, file in logged_files.items()
                           if fnmatch(Path(canon).name, '[A-Z]-[0-9]_*.mubin')]:
            try:
                (tmp_dir / mubin_file).unlink()
            except FileNotFoundError:
                pass
    if not no_texts and (tmp_dir / 'content' / 'Pack').exists():
        print('  Removing language bootup packs...')
        for bootup_lang in (tmp_dir / 'content' / 'Pack').glob('Bootup_*.pack'):
            bootup_lang.unlink()
    if not no_actorinfo and (tmp_dir / 'content' / 'Actor' / 'ActorInfo.product.sbyml').exists():
        print('  Removing ActorInfo.product.sbyml...')
        (tmp_dir / 'content' / 'Actor' / 'ActorInfo.product.sbyml').unlink()
    if not no_gamedata and (tmp_dir / 'content' / 'Pack' / 'Bootup.pack').exists():
        print('  Removing gamedata sarcs...')
        with (tmp_dir / 'content' / 'Pack' / 'Bootup.pack').open('rb') as b_file:
            bsarc = sarc.read_file_and_make_sarc(b_file)
        csarc = sarc.make_writer_from_sarc(bsarc)
        bsarc_files = list(bsarc.list_files())
        if 'GameData/gamedata.ssarc' in bsarc_files:
            csarc.delete_file('GameData/gamedata.ssarc')
        if 'GameData/savedataformat.ssarc' in bsarc_files:
            csarc.delete_file('GameData/savedataformat.ssarc')
        with (tmp_dir / 'content' / 'Pack' / 'Bootup.pack').open('wb') as b_file:
            csarc.write(b_file)

    hashes = util.get_hash_table()
    print('  Creating partial packs...')
    sarc_files = [file for file in list(
        tmp_dir.rglob('**/*')) if file.suffix in util.SARC_EXTS]
    if sarc_files:
        num_threads = min(len(sarc_files), cpu_count())
        pool = Pool(processes=num_threads)
        pool.map(partial(_clean_sarc, hashes=hashes, tmp_dir=tmp_dir), sarc_files)
        pool.close()
        pool.join()

        with (tmp_dir / 'logs' / 'packs.log').open('w', encoding='utf-8') as p_file:
            final_packs = [file for file in list(
                tmp_dir.rglob('**/*')) if file.suffix in util.SARC_EXTS]
            if final_packs:
                p_file.write('name,path\n')
                for file in final_packs:
                    p_file.write(
                        f'{util.get_canon_name(file.relative_to(tmp_dir))},'
                        f'{file.relative_to(tmp_dir)}\n'
                    )
    else:
        if (tmp_dir / 'logs' / 'packs.log').exists():
            (tmp_dir / 'logs' / 'packs.log').unlink()

    print('  Cleaning any junk files...')
    for file in tmp_dir.rglob('**/*'):
        if file.parent.stem == 'logs':
            continue
        if file.suffix in ['.yml', '.bak', '.tmp', '.old']:
            file.unlink()

    print('  Removing blank folders...')
    for folder in reversed(list(tmp_dir.rglob('**/*'))):
        if folder.is_dir() and not list(folder.glob('*')):
            shutil.rmtree(folder)

    print(f'Saving output file to {str(output)}...')
    x_args = [str(util.get_exec_dir() / 'helpers' / '7z.exe'),
              'a', str(output), f'{str(tmp_dir / "*")}']
    subprocess.run(x_args, stdout=subprocess.PIPE,
                   stderr=subprocess.PIPE, creationflags=util.CREATE_NO_WINDOW)
    print('Conversion complete.')


def create_backup(name: str = ''):
    """
    Creates a backup of the current mod installations. Saves it as a 7z file in
    `CEMU_DIR/bcml_backups`.

    :param name: The name to give the backup, defaults to "BCML_Backup_YYYY-MM-DD"
    :type name: str, optional
    """
    import re
    if not name:
        name = f'BCML_Backup_{datetime.datetime.now().strftime("%Y-%m-%d")}'
    else:
        name = re.sub(r'(?u)[^-\w.]', '', name.strip().replace(' ', '_'))
    output = util.get_cemu_dir() / 'bcml_backups' / f'{name}.7z'
    output.parent.mkdir(parents=True, exist_ok=True)
    print(f'Saving backup {name}...')
    x_args = [str(util.get_exec_dir() / 'helpers' / '7z.exe'),
              'a', str(output), f'{str(util.get_modpack_dir() / "*")}']
    subprocess.run(x_args, stdout=subprocess.PIPE,
                   stderr=subprocess.PIPE, creationflags=util.CREATE_NO_WINDOW)
    print(f'Backup "{name}" created')


def get_backups() -> List[Path]:
    """ Gets a list of BCML mod configuration backups """
    return list((util.get_cemu_dir() / 'bcml_backups').glob('*.7z'))


def restore_backup(backup: Union[str, Path]):
    """
    Restores a BCML mod configuration backup

    :param backup: The backup to restore, either by name or by path
    :type backup: Union[str, Path]
    """
    if isinstance(backup, str):
        backup = util.get_cemu_dir() / 'bcml_backups' / f'{backup}.7z'
    if not backup.exists():
        raise FileNotFoundError(f'The backup "{backup.name}" does not exist.')
    print('Clearing installed mods...')
    for folder in [item for item in util.get_modpack_dir().glob('*') if item.is_dir()]:
        shutil.rmtree(str(folder))
    print('Extracting backup...')
    x_args = [str(util.get_exec_dir() / 'helpers' / '7z.exe'),
              'x', str(backup), f'-o{str(util.get_modpack_dir())}']
    subprocess.run(x_args, stdout=subprocess.PIPE,
                   stderr=subprocess.PIPE, creationflags=util.CREATE_NO_WINDOW)
    print('Re-enabling mods in Cemu...')
    refresh_cemu_mods()
    print(f'Backup "{backup.name}" restored')
