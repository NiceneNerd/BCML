# Copyright 2019 Nicene Nerd <macadamiadaze@gmail.com>
# Licensed under GPLv3+
import os
import shutil
import subprocess
from configparser import ConfigParser
from copy import deepcopy
from fnmatch import fnmatch
from functools import partial, reduce
from multiprocessing import Pool, cpu_count
from pathlib import Path
from typing import Union
from xml.dom import minidom

import aamp.yaml_util
import byml
import rstb
import sarc
import wszst_yaz0
import xxhash
import yaml
from byml import yaml_util

from bcml import pack, texts, util, data, merge, rstable, mubin
from bcml.util import BcmlMod

RSTB_EXCLUDE = ['.pack', '.bgdata', '.txt', '.bgsvdata', '.yml',
                '.bat', '.ini', '.png', '.bfstm', '.py', '.sh']


def open_mod(path: Path) -> Path:
    """
    Extracts a provided mod and returns the root path of the graphicpack inside

    :param path: The path to the mod archive.
    :type path: :class:`pathlib.Path`
    :returns: The path to the extracted root of the mod where the rules.txt file is found.
    :rtype: :class:`pathlib.Path`
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
    while len([*util.get_modpack_dir().glob(f'{i:04}_*')]) > 0:
        i += 1
    return i


def threaded_aamp_diffs(file_info: tuple, tmp_dir: Path):
    return (file_info[0], merge.get_aamp_diff(file_info[1], tmp_dir))


def find_modded_files(tmp_dir: Path, deep_merge: bool = False, verbose: bool = False, guess: bool = False) -> (dict, list, dict):
    """
    Detects all of the modified files in an extracted mod

    :param tmp_dir: The path to the base directory of the mod.
    :type tmp_dir: :class:`pathlib.Path`
    :param deep_merge: Whether to log diffs for individual AAMP and BYML files, defaults to False
    :type deep_merge: bool, optional
    :param verbose: Specifies whether to return more detailed output
    :type verbose: bool, optional
    :returns: Returns a tuple with a dict of modified files and the RSTB entries, a list of changes, and (if deep merge)
    diffs of modded BYML and AAMP files
    :rtype: (dict of :class:`pathlib.Path`: int, list of str, dict of str: str)
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
        with aoc_field.open('rb') as af:
            sarc.read_file_and_make_sarc(af).extract_to_dir(
                str(tmp_dir / 'aoc' / '0010'))
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
                    aamps_to_diff.append(
                        (file.relative_to(tmp_dir).as_posix(), file))
            else:
                if 'Aoc/0010/Map/MainField' in canon:
                    file.unlink()
                if verbose:
                    log.append(f'Ignored unmodded file {canon}')
                continue
    if len(aamps_to_diff) > 0:
        p = Pool()
        aamp_thread_partial = partial(threaded_aamp_diffs, tmp_dir=tmp_dir)
        aamp_results = p.map(aamp_thread_partial, aamps_to_diff)
        p.close()
        p.join()
        for file, diff in aamp_results:
            aamp_diffs[file] = diff
    total = len(modded_files)
    log.append(f'Found {total} modified file{"s" if total > 1 else ""}')
    return modded_files, log, aamp_diffs


def find_modded_sarc_files(mod_sarc: sarc.SARC, name: str, tmp_dir: Path, aoc: bool = False, nest_level: int = 0,
                           deep_merge: bool = False, guess: bool = False, verbose: bool = False) -> (dict, list):
    """
    Detects all of the modified files in a SARC

    :param mod_sarc: The SARC to scan for modded files.
    :type mod_sarc: :class:`sarc.SARC`
    :param tmp_dir: The path to the base directory of the mod.
    :type tmp_dir: :class:`pathlib.Path`
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
                sub_mod_files, sub_mod_log, sub_mod_diffs = find_modded_sarc_files(nest_sarc,
                                                                                   modded_files[canon]['path'],
                                                                                   tmp_dir=tmp_dir,
                                                                                   nest_level=nest_level + 1, aoc=aoc,
                                                                                   verbose=verbose, guess=guess, deep_merge=deep_merge)
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
                  no_actorinfo: bool = False, no_map: bool = False, deep_merge: bool = False):
    print('Scanning for modified files...')
    modded_files, rstb_changes, aamp_diffs = find_modded_files(
        tmp_dir, verbose=verbose, deep_merge=deep_merge, guess=guess)
    if len(rstb_changes) > 0:
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
    if len(sarc_files) > 0:
        num_threads = min(len(sarc_files), cpu_count())
        p = Pool(processes=num_threads)
        thread_sarc_search = partial(threaded_find_modded_sarc_files, modded_files=modded_files, tmp_dir=tmp_dir,
                                     deep_merge=deep_merge, verbose=verbose, guess=guess)
        results = p.map(thread_sarc_search, sarc_files)
        p.close()
        p.join()
        for result in results:
            modded_sarcs, sarc_changes, nested_diffs = result
            if len(modded_sarcs) > 0:
                modded_sarc_files.update(modded_sarcs)
                if deep_merge:
                    aamp_diffs.update(nested_diffs)
                if len(sarc_changes) > 0:
                    print('\n'.join(sarc_changes))
        mod_sarc_count = len(sarc_files)
        print(
            f'Found {len(sarc_files)} modded pack file{"s" if mod_sarc_count != 1 else ""}')

    if len(modded_files) == 0:
        print('No modified files were found. Very unusual.')
        return
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
        with (tmp_dir / 'content/Actor/ActorInfo.product.sbyml').open('rb') as af:
            actorinfo = byml.Byml(wszst_yaz0.decompress(af.read())).parse()
        modded_actors = data.get_modded_actors(actorinfo)
    else:
        no_actorinfo = True

    modded_bgentries = {}
    if 'GameData/gamedata.sarc' in modded_sarc_files and not no_gamedata:
        print('Game data modified, analyzing...')
        with (tmp_dir / modded_files['Pack/Bootup.pack']['path']).open('rb') as bf:
            bootup = sarc.read_file_and_make_sarc(bf)
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
        with (tmp_dir / modded_files['Pack/Bootup.pack']['path']).open('rb') as bf:
            bootup = sarc.read_file_and_make_sarc(bf)
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
        mubin.log_modded_texts(tmp_dir, modded_mubins)

    if deep_merge:
        deep_merge = len(aamp_diffs) > 0

    print('Saving logs...')
    (tmp_dir / 'logs').mkdir(parents=True, exist_ok=True)
    with Path(tmp_dir / 'logs' / 'rstb.log').open('w') as rf:
        rf.write('name,rstb,path\n')
        modded_files.update(modded_sarc_files)
        for file in modded_files:
            ext = os.path.splitext(file)[1]
            if ext not in RSTB_EXCLUDE and 'ActorInfo' not in file:
                rf.write('{},{},{}\n'.format(file, modded_files[file]["rstb"], str(
                    modded_files[file]["path"]).replace('\\', '/')))
    if not no_packs:
        with Path(tmp_dir / 'logs' / 'packs.log').open('w') as pf:
            pf.write('name,path\n')
            for file in modded_files:
                name, ext = os.path.splitext(file)
                if ext in util.SARC_EXTS and not modded_files[file]['nested'] and not name.startswith('Dungeon'):
                    pf.write(f'{file},{modded_files[file]["path"]}\n')
    if is_text_mod:
        for lang in text_mods:
            with Path(tmp_dir / 'logs' / f'texts_{lang}.yml').open('w') as tf:
                yaml.dump(text_mods[lang][0], tf)
            text_sarc = text_mods[lang][1]
            if text_sarc is not None:
                with Path(tmp_dir / 'logs' / f'newtexts_{lang}.sarc').open('wb') as sf:
                    text_sarc.write(sf)
    dumper = yaml.CDumper
    yaml_util.add_representers(dumper)
    aamp.yaml_util.register_representers(dumper)
    dumper.__aamp_reader = None
    aamp.yaml_util._get_pstruct_name = lambda reader, idx, k, parent_crc32: k
    if not no_gamedata:
        with (tmp_dir / 'logs' / 'gamedata.yml').open('w', encoding='utf-8') as gf:
            yaml.dump(modded_bgentries, gf, Dumper=dumper, allow_unicode=True, encoding='utf-8',
                      default_flow_style=None)
    if not no_savedata:
        with (tmp_dir / 'logs' / 'savedata.yml').open('w', encoding='utf-8') as sf:
            yaml.dump(modded_bgsventries, sf, Dumper=dumper, allow_unicode=True, encoding='utf-8',
                      default_flow_style=None)
    if not no_actorinfo:
        with (tmp_dir / 'logs' / 'actorinfo.yml').open('w', encoding='utf-8') as af:
            yaml.dump(modded_actors, af, Dumper=dumper, allow_unicode=True, encoding='utf-8',
                      default_flow_style=None)
    if deep_merge:
        with (tmp_dir / 'logs' / 'deepmerge.yml').open('w', encoding='utf-8') as df:
            yaml.dump(aamp_diffs, df, Dumper=dumper, allow_unicode=True,
                      encoding='utf-8', default_flow_style=None)
    if leave_rstb:
        Path(tmp_dir / 'logs' / '.leave').open('w').close()
    if shrink_rstb:
        Path(tmp_dir / 'logs' / '.shrink').open('w').close()

    return is_text_mod, no_texts, no_packs, no_gamedata, no_savedata, no_actorinfo, deep_merge, no_map, modded_files


def threaded_find_modded_sarc_files(file: str, modded_files: dict, tmp_dir: Path, deep_merge: bool, verbose: bool, guess: bool = False):
    with Path(tmp_dir / modded_files[file]['path']).open('rb') as sf:
        mod_sarc = sarc.read_file_and_make_sarc(sf)
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
    hasbcml = False
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
    settings.writexml(setpath.open('w'), addindent='    ', newl='\n')


def install_mod(mod: Path, verbose: bool = False, no_packs: bool = False, no_texts: bool = False,
                no_gamedata: bool = False, no_savedata: bool = False, no_actorinfo: bool = False,
                no_map: bool = False, leave_rstb: bool = False, shrink_rstb: bool = False,
                guess: bool = False, wait_merge: bool = False, deep_merge: bool = False):
    """
    Installs a graphic pack mod, merging RSTB changes and optionally packs and texts

    :param mod: Path to the mod to install. Must be a RAR, 7z, or ZIP archive or a graphicpack directory
    containing a rules.txt file.
    :type mod: :class:`pathlib.Path`
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
    :param leave_rstb: Do not remove RSTB entries when the proper value can't be calculated, defaults to False.
    :type leave_rstb: bool, optional
    :param shrink_rstb: Shrink RSTB values where possible, defaults to False.
    :type shrink_rstb: bool, optional
    :param guess: Estimate RSTB values for AAMP and BFRES files, defaults to False.
    :type guess: bool, optional
    :param wait_merge: Install mod and log changes, but wait to run merge manually, defaults to False.
    :type wait_merge: bool, optional
    :param deep_merge: Attempt to merge changes within individual AAMP files, defaults to False.
    :type deep_merge: bool, optional
    """
    util.create_bcml_graphicpack_if_needed()
    if type(mod) is str:
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
            is_text_mod = len(text_mods) > 0
    else:
        is_text_mod, no_texts, no_packs, no_gamedata, no_savedata, no_actorinfo, deep_merge, no_map, _ = generate_logs(
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

    priority = get_next_priority()
    mod_id = util.get_mod_id(mod_name, priority)
    mod_dir = util.get_modpack_dir() / mod_id
    mod_dir.parent.mkdir(parents=True, exist_ok=True)
    print()
    print(f'Moving mod to {str(mod_dir)}...')
    if mod.is_file():
        shutil.move(str(tmp_dir), str(mod_dir))
    elif mod.is_dir():
        shutil.copytree(str(tmp_dir), str(mod_dir))

    rulepath = os.path.basename(rules['Definition']['path']).replace('"', '')
    rules['Definition'][
        'path'] = f'The Legend of Zelda: Breath of the Wild/BCML Mods/{rulepath}'
    rules['Definition']['fsPriority'] = str(priority)
    with Path(mod_dir / 'rules.txt').open('w') as rf:
        rules.write(rf)

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
        if not deep_merge:
            rstable.generate_master_rstb(verbose)
        print()
        print(f'{mod_name} installed successfully!')
    return BcmlMod(mod_name, priority, mod_dir)


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
        if len(pack_mods):
            pack.merge_installed_packs(verbose, only_these=pack_mods)
        if len(text_mods) > 0:
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
        if len(deepmerge_mods) > 0:
            merge.deep_merge(only_these=list(deepmerge_mods))
    print(f'{mod_name} has been uninstalled.')


def change_mod_priority(path: Path, new_priority: int, wait_merge: bool = False, verbose: bool = False):
    """
    Changes the priority of a mod

    :param path: The path to the mod.
    :type path: :class:`pathlib.Path`
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
                    f'Changing priority of {mod.name} from {mod.priority} to {adjusted_priority}...')
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
            with (mod[2].parent / new_mod_id / 'rules.txt').open('w') as rf:
                rules.write(rf)
            refresh_cemu_mods()
    if len(remerge_packs) > 0:
        if wait_merge:
            print('Pack merges affected, will need to remerge later')
        else:
            print('Pack merges affected, remerging packs...')
            pack.merge_installed_packs(verbose, only_these=list(remerge_packs))
            print()
    if len(remerge_texts) > 0:
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
    if len(deepmerge) > 0:
        if wait_merge:
            print('Deep merge affected, will need to remerge later')
        else:
            print('Deep merge affected, remerging...')
            merge.deep_merge(verbose, only_these=list(deepmerge))
            print()
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
    if not (util.get_master_modpack_dir() / 'content' / 'System' / 'Resource' / 'ResourceSizeTable.product.srsizetable').exists():
        (util.get_master_modpack_dir() / 'content' / 'System' /
         'Resource').mkdir(parents=True, exist_ok=True)
        shutil.copy(str(util.get_game_file('System/Resource/ResourceSizeTable.product.srsizetable')), str(
            (util.get_master_modpack_dir() / 'content' / 'System' / 'Resource' / 'ResourceSizeTable.product.srsizetable')))
    pack.merge_installed_packs(verbose=False, even_one=True)
    for bootup in util.get_master_modpack_dir().rglob('content/Pack/Bootup_*'):
        lang = util.get_file_language(bootup)
        texts.merge_texts(lang, verbose=verbose)
    data.merge_gamedata(verbose)
    data.merge_savedata(verbose)
    data.merge_actorinfo(verbose)
    mubin.merge_maps(verbose)
    merge.deep_merge(verbose, wait_rstb=True)
    rstable.generate_master_rstb(verbose)


def create_minimal_mod(mod: Path, output: Path = None, no_packs: bool = False, no_texts: bool = False,
                       no_gamedata: bool = False, no_savedata: bool = False, no_actorinfo: bool = False,
                       no_map: bool = False, leave_rstb: bool = False, shrink_rstb: bool = False,
                       guess: bool = False, deep_merge: bool = True):
    if isinstance(mod, str):
        mod = Path(mod)
    if mod.is_file():
        print('Extracting mod...')
        tmp_dir: Path = open_mod(mod)
    elif mod.is_dir():
        if (mod / 'rules.txt').exists():
            print(f'Loading mod from {str(mod)}...')
            tmp_dir: Path = util.get_work_dir() / \
                f'tmp_{xxhash.xxh32(str(mod.path)).hexdigest()}'
            shutil.copytree(str(mod), str(tmp_dir))
        else:
            print(f'Cannot open mod at {str(mod)}, no rules.txt found')
            return
    else:
        print(f'Error: {str(mod)} is neither a valid file nor a directory')
        return

    logged_files = generate_logs(tmp_dir, leave_rstb=leave_rstb, shrink_rstb=shrink_rstb,
                                 guess=guess, no_packs=no_packs, no_texts=no_texts, no_gamedata=no_gamedata,
                                 no_savedata=no_savedata, no_actorinfo=no_actorinfo, no_map=no_map,
                                 deep_merge=deep_merge)[8]

    print('Removing unnecessary files...')
    if not no_map:
        print('  Removing map units...')
        for mubin in [file['path'] for canon, file in logged_files.items()
                      if fnmatch(Path(canon).name, '[A-Z]-[0-9]_*.mubin')]:
            try:
                (tmp_dir / mubin).unlink()
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
        with (tmp_dir / 'content' / 'Pack' / 'Bootup.pack').open('rb') as bf:
            bsarc = sarc.read_file_and_make_sarc(bf)
        csarc = sarc.make_writer_from_sarc(bsarc)
        csarc.delete_file('GameData/gamedata.ssarc')
        csarc.delete_file('GameData/savedataformat.ssarc')
        with (tmp_dir / 'content' / 'Pack' / 'Bootup.pack').open('wb') as bf:
            csarc.write(bf)

    print('  Removing unnecessary packs...')

    def should_delete(file, value, hashes) -> bool:
        if util.get_canon_name(file, allow_no_source=True) not in hashes:
            return False
        if isinstance(value, dict):
            delete = True
            for key, value in value.items():
                delete = False if not should_delete(
                    key, value, hashes) else delete
            return delete
        elif isinstance(value, str):
            return Path(value).suffix in util.AAMP_EXTS \
                and value in hashes

    hashes = util.get_hash_table()
    modded_files = [str(meta['path'])
                    for file, meta in logged_files.items()]
    del_files = {}
    for file in modded_files:
        parts = file.split('//')
        top_file = Path(parts[0])
        if top_file.suffix not in util.SARC_EXTS:
            continue
        parts[0] = top_file.as_posix()
        nest = reduce(lambda res, cur: {
            cur: res}, reversed(parts))
        if isinstance(nest, str):
            nest = {nest: {}}
        util.dict_merge(del_files, nest)
    save_files = deepcopy(del_files)
    for file, value in save_files.items():
        if not should_delete(file, value, hashes):
            del del_files[file]
    for file in del_files:
        if (tmp_dir / file).exists():
            (tmp_dir / file).unlink()

    print('  Creating partial packs...')
    for file in [file for file in list(tmp_dir.rglob('**/*')) if file.suffix in util.SARC_EXTS]:
        canon = util.get_canon_name(file.relative_to(tmp_dir))
        if canon not in hashes:
            continue
        with file.open('rb') as sf:
            base_sarc = sarc.read_file_and_make_sarc(sf)
        new_sarc = sarc.SARCWriter(True)
        for nest_file in base_sarc.list_files():
            canon = nest_file.replace('.s', '.')
            file_data = base_sarc.get_file_data(nest_file).tobytes()
            xhash = xxhash.xxh32(util.unyaz_if_needed(file_data)).hexdigest()
            if canon not in hashes or xhash != hashes[canon]:
                new_sarc.add_file(nest_file, file_data)
        with file.open('wb') as sf:
            if file.suffix.startswith('.s') and file.suffix != '.ssarc':
                sf.write(wszst_yaz0.compress(new_sarc.get_bytes()))
            else:
                new_sarc.write(sf)

    print('  Removing blank folders...')
    for folder in reversed(list(tmp_dir.rglob('**/*'))):
        if folder.is_dir() and len(list(folder.glob('*'))) == 0:
            shutil.rmtree(folder)
    print('Conversion complete.')
