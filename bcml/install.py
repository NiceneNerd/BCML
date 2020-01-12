"""Provides features for installing, creating, and mananging BCML mods"""
# Copyright 2019 Nicene Nerd <macadamiadaze@gmail.com>
# Licensed under GPLv3+
# pylint: disable=too-many-lines
import datetime
import json
import os
import shutil
import subprocess
import traceback
from configparser import ConfigParser
from dataclasses import astuple
from fnmatch import fnmatch
from functools import partial
from multiprocessing import Pool, cpu_count, set_start_method
from pathlib import Path
from platform import system
from shutil import copy
from typing import List, Union, Callable
from xml.dom import minidom

import sarc
import xxhash

from bcml import util, mergers
from bcml.mergers import data, events, merge, mubin, pack, rstable, texts
from bcml.util import BcmlMod

if system() == 'Windows':
    ZPATH = str(util.get_exec_dir() / 'helpers' / '7z.exe')
else:
    ZPATH = str(util.get_exec_dir() / 'helpers' / '7z')


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
        x_args = [ZPATH, 'x', str(path), f'-o{str(tmpdir)}']
        if system() == 'Windows':
            subprocess.run(x_args, stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE, creationflags=util.CREATE_NO_WINDOW)
        else:
            subprocess.run(x_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    else:
        raise Exception('The mod provided was not a supported archive (BNP, ZIP, RAR, or 7z).')
    if not tmpdir.exists():
        raise Exception('No files were extracted.')

    rulesdir = tmpdir
    if (rulesdir / 'info.json').exists():
        return rulesdir
    if not (rulesdir / 'rules.txt').exists():
        for subdir in tmpdir.rglob('*'):
            if (subdir / 'rules.txt').exists():
                rulesdir = subdir
                break
        else:
            raise FileNotFoundError(f'No rules.txt was found in "{path.name}".')
    print('Looks like an older mod, let\'s upgrade it...')
    from bcml import upgrade
    upgrade.convert_old_mod(rulesdir, delete_old=True)
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


def find_modded_files(tmp_dir: Path) -> List[Union[Path, str]]:
    """
    Detects all of the modified files in an extracted mod

    :param tmp_dir: The path to the base directory of the mod.
    :type tmp_dir: class:`pathlib.Path`
    :param deep_merge: Whether to log diffs for individual AAMP and BYML files, defaults to False
    :type deep_merge: bool, optional
    :returns: Returns a tuple with a dict of modified files and the RSTB entries, a list of changes,
    and (if deep merge) diffs of modded BYML and AAMP files
    :rtype: (dict of class:`pathlib.Path`: int, list of str, dict of str: str)
    """
    modded_files = []
    if isinstance(tmp_dir, str):
        tmp_dir = Path(tmp_dir)
    rstb_path = tmp_dir / 'content' / 'System' / 'Resource' /\
                'ResourceSizeTable.product.srsizetable'
    if rstb_path.exists():
        rstb_path.unlink()

    if (tmp_dir / 'aoc').exists:
        try:
            util.get_aoc_dir()
        except FileNotFoundError as err:
            err.error_text = ('This mod uses DLC files, but you do not appear to have the DLC '
                              'installed. If you still want to use this mod, unpack it and '
                              'remove the "aoc" folder.')
            raise err

    aoc_field = tmp_dir / 'aoc' / '0010' / 'Pack' / 'AocMainField.pack'
    if aoc_field.exists() and aoc_field.stat().st_size > 0:
        with aoc_field.open('rb') as a_file:
            sarc.read_file_and_make_sarc(a_file).extract_to_dir(str(tmp_dir / 'aoc' / '0010'))
        aoc_field.write_bytes(b'')

    for file in tmp_dir.rglob('**/*'):
        if file.is_file():
            canon = util.get_canon_name(file.relative_to(tmp_dir).as_posix())
            if canon is None:
                util.vprint(f'Ignored unknown file {file.relative_to(tmp_dir).as_posix()}')
                continue
            if util.is_file_modded(canon, file, True):
                modded_files.append(file)
                util.vprint(f'Found modded file {canon}')
            else:
                if 'Aoc/0010/Map/MainField' in canon:
                    file.unlink()
                util.vprint(f'Ignored unmodded file {canon}')
                continue
    total = len(modded_files)
    print(f'Found {total} modified file{"s" if total > 1 else ""}')

    total = 0
    sarc_files = [file for file in modded_files if file.suffix in util.SARC_EXTS]
    if sarc_files:
        print(f'Scanning files packed in SARCs...')
        set_start_method('spawn', True)
        num_threads = min(len(sarc_files), cpu_count() - 1)
        pool = Pool(processes=num_threads)
        modded_sarc_files = pool.map(
            partial(find_modded_sarc_files, tmp_dir=tmp_dir),
            sarc_files
        )
        pool.close()
        pool.join()
        for files in modded_sarc_files:
            total += len(files)
            modded_files.extend(files)
        print(f'Found {total} modified packed file{"s" if total > 1 else ""}')
    return modded_files


def find_modded_sarc_files(mod_sarc: Union[Path, sarc.SARC], tmp_dir: Path, name: str = '',
                           aoc: bool = False) -> List[str]:
    if isinstance(mod_sarc, Path):
        if any(mod_sarc.name.startswith(exclude) for exclude in ['Bootup_']):
            return []
        name = str(mod_sarc.relative_to(tmp_dir))
        aoc = 'aoc' in mod_sarc.parts or 'Aoc' in mod_sarc.parts
        with mod_sarc.open('rb') as s_file:
            mod_sarc = sarc.read_file_and_make_sarc(s_file)
        if not mod_sarc:
            return []
    modded_files = []
    for file in mod_sarc.list_files():
        canon = file.replace('.s', '.')
        if aoc:
            canon = 'Aoc/0010/' + canon
        contents = mod_sarc.get_file_data(file).tobytes()
        contents = util.unyaz_if_needed(contents)
        nest_path = str(name).replace('\\', '/') + '//' + file
        if util.is_file_modded(canon, contents, True):
            modded_files.append(
                nest_path
            )
            util.vprint(f'Found modded file {canon} in {str(name).replace("//", "/")}')
            if util.is_file_sarc(canon) and '.ssarc' not in file:
                try:
                    nest_sarc = sarc.SARC(contents)
                except ValueError:
                    continue
                sub_mod_files = find_modded_sarc_files(
                    nest_sarc,
                    name=nest_path,
                    tmp_dir=tmp_dir,
                    aoc=aoc
                )
                modded_files.extend(sub_mod_files)
        else:
            util.vprint(f'Ignored unmodded file {canon} in {str(name).replace("//", "/")}')
    return modded_files


def generate_logs(tmp_dir: Path, options: dict = None) -> List[Path]:
    """Analyzes a mod and generates BCML log files containing its changes"""
    if isinstance(tmp_dir, str):
        tmp_dir = Path(tmp_dir)
    if not options:
        options = {
            'disable': [],
            'options': {}
        }
    if 'disable' not in options:
        options['disable'] = []
    util.vprint(options)

    print('Scanning for modified files...')
    modded_files = find_modded_files(tmp_dir)
    if not modded_files:
        raise RuntimeError(
            'No modified files were found. Perhaps the mod has an incorrect folder layout.'
        )
    util.vprint(modded_files)

    (tmp_dir / 'logs').mkdir(parents=True, exist_ok=True)
    for merger_class in [merger_class for merger_class in mergers.get_mergers() \
                        if merger_class.NAME not in options['disable']]:
        merger = merger_class()
        if options is not None and merger.NAME in options:
            merger.set_options(options[merger.NAME])
        merger.log_diff(tmp_dir, modded_files)

    return modded_files


def refresher(func: Callable) -> Callable:
    def do_and_refresh(*args, **kwargs):
        res = func(*args, **kwargs)
        refresh_master_export()
        return res
    return do_and_refresh


def refresh_master_export():
    """ Updates the master BCML exported graphic pack in Cemu """
    print('Exporting merged mod pack...')
    link_master_mod()
    if not util.get_settings('no_cemu'):
        setpath = util.get_cemu_dir() / 'settings.xml'
        if not setpath.exists():
            raise FileNotFoundError('The Cemu settings file could not be found.')
        setread = ''
        with setpath.open('r', encoding='utf-8') as setfile:
            for line in setfile:
                setread += line.strip()
        settings = minidom.parseString(setread)
        try:
            gpack = settings.getElementsByTagName('GraphicPack')[0]
        except IndexError:
            gpack = settings.createElement('GraphicPack')
            settings.appendChild(gpack)
        has_bcml = False
        for entry in gpack.getElementsByTagName('Entry'):
            if 'BCML' in entry.getElementsByTagName('filename')[0].childNodes[0].data:
                break
        else:
            bcmlentry = settings.createElement('Entry')
            entryfile = settings.createElement('filename')
            entryfile.appendChild(settings.createTextNode(
                f'graphicPacks\\BreathOfTheWild_BCML\\rules.txt'))
            entrypreset = settings.createElement('preset')
            entrypreset.appendChild(settings.createTextNode(''))
            bcmlentry.appendChild(entryfile)
            bcmlentry.appendChild(entrypreset)
            gpack.appendChild(bcmlentry)
            settings.writexml(setpath.open('w', encoding='utf-8'), addindent='    ', newl='\n')


@refresher
def install_mod(mod: Path, options: dict = None, wait_merge: bool = False,
                insert_priority: int = 0):
    if insert_priority == 0:
        insert_priority = get_next_priority()
    util.create_bcml_graphicpack_if_needed()
    if isinstance(mod, str):
        mod = Path(mod)
    if mod.is_file():
        print('Extracting mod...')
        tmp_dir = open_mod(mod)
    elif mod.is_dir():
        if not ((mod / 'rules.txt').exists() or (mod / 'info.json').exists()):
            print(f'Cannot open mod at {str(mod)}, no rules.txt found')
            return
        print(f'Loading mod from {str(mod)}...')
        tmp_dir = util.get_work_dir() / f'tmp_{mod.name}'
        shutil.copytree(str(mod), str(tmp_dir))
        if (mod / 'rules.txt').exists():
            print('Upgrading old mod format...')
            from . import upgrade
            upgrade.convert_old_mod(mod, delete_old=True)
            
    else:
        print(f'Error: {str(mod)} is neither a valid file nor a directory')
        return

    try:
        rules = json.loads(
            (tmp_dir / 'info.json').read_text('utf-8')
        )
        mod_name = rules['name'].strip(' \'"').replace('_', '')
        print(f'Identified mod: {mod_name}')

        logs = tmp_dir / 'logs'
        if logs.exists():
            print('This mod supports Quick Install! Loading changes...')
            for merger in [merger() for merger in mergers.get_mergers() \
                           if merger.NAME in options['disable']]:
                if merger.is_mod_logged(BcmlMod(tmp_dir)):
                    (tmp_dir / 'logs' / merger.log_name).unlink()
        else:
            generate_logs(tmp_dir=tmp_dir, options=options)
    except Exception as e: # pylint: disable=broad-except
        if hasattr(e, 'error_text'):
            raise e
        clean_error = RuntimeError()
        try:
            name = mod_name
        except NameError:
            name = 'your mod, the name of which could not be detected'
        clean_error.error_text = (f'There was an error while processing {name}. '
                                  'This could indicate there is a problem with the mod itself, '
                                  'but it could also reflect a new or unusual edge case BCML does '
                                  'not anticipate. Here is the error:\n\n'
                                  f'{traceback.format_exc(limit=-4)}')
        raise clean_error

    priority = insert_priority
    print(f'Assigned mod priority of {priority}')
    mod_id = util.get_mod_id(mod_name, priority)
    mod_dir = util.get_modpack_dir() / mod_id

    try:
        for existing_mod in util.get_installed_mods():
            if existing_mod.priority >= priority:
                priority_shifted = existing_mod.priority + 1
                new_id = util.get_mod_id(existing_mod.name, priority_shifted)
                new_path = util.get_modpack_dir() / new_id
                shutil.move(str(existing_mod.path), str(new_path))
                existing_mod_rules = util.RulesParser()
                existing_mod_rules.read(str(new_path / 'rules.txt'))
                existing_mod_rules['Definition']['fsPriority'] = str(priority_shifted)
                with (new_path / 'rules.txt').open('w', encoding='utf-8') as r_file:
                    existing_mod_rules.write(r_file)

        mod_dir.parent.mkdir(parents=True, exist_ok=True)
        print(f'Moving mod to {str(mod_dir)}...')
        if mod.is_file():
            try:
                shutil.move(str(tmp_dir), str(mod_dir))
            except Exception: # pylint: disable=broad-except
                try:
                    shutil.copytree(str(tmp_dir), str(mod_dir))
                    try:
                        shutil.rmtree(str(tmp_dir))
                    except Exception: # pylint: disable=broad-except
                        pass
                except Exception: # pylint: disable=broad-except
                    raise OSError('BCML could not transfer your mod from the temp directory '
                                       'to the BCML directory.')
        elif mod.is_dir():
            shutil.copytree(str(tmp_dir), str(mod_dir))

        rules['priority'] = priority
        (mod_dir / 'info.json').write_text(
            json.dumps(rules, ensure_ascii=False),
            encoding='utf-8'
        )
        (mod_dir / 'options.json').write_text(
            json.dumps(options, ensure_ascii=False),
            encoding='utf-8'
        )

        output_mod = BcmlMod(mod_dir)
        try:
            util.get_mod_link_meta(rules)
            util.get_mod_preview(output_mod, rules)
        except Exception: # pylint: disable=broad-except
            pass

        print(f'Enabling {mod_name} in Cemu...')
    except Exception: # pylint: disable=broad-except
        clean_error = RuntimeError()
        clean_error.error_text = (f'There was an error installing {mod_name}. '
                                  'It processed successfully, but could not be added to your BCML '
                                  'mods. This may indicate a problem with your BCML installation. '
                                  'Here is the error:\n\n'
                                  f'{traceback.format_exc(limit=-4)}\n\n'
                                  f'{mod_name} is being removed and no changes will be made.')
        if mod_dir.exists():
            try:
                uninstall_mod(mod_dir, wait_merge=True)
            except Exception: # pylint: disable=broad-except
                shutil.rmtree(str(mod_dir))
        raise clean_error


    if wait_merge:
        print('Mod installed, merge still pending...')
    else:
        try:
            print('Performing merges...')
            if not options:
                options = {}
            if 'disable' not in options:
                options['disable'] = []
            for merger in mergers.sort_mergers([cls() for cls in mergers.get_mergers() \
                                                if cls.NAME not in options['disable']]):
                if merger.NAME in options:
                    merger.set_options(options[merger.NAME])
                if merger.is_mod_logged(output_mod):
                    merger.perform_merge()
            print(f'{mod_name} installed successfully!')
        except Exception: # pylint: disable=broad-except
            clean_error = RuntimeError()
            clean_error.error_text = (f'There was an error merging {mod_name}. '
                                      'It processed and installed without error, but it has not '
                                      'successfully merged with your other mods. '
                                      'Here is the error:\n\n'
                                      f'{traceback.format_exc(limit=-4)}\n\n'
                                      f'To protect your mod setup, BCML will remove {mod_name} '
                                      'and remerge.')
            try:
                uninstall_mod(mod_dir)
            except FileNotFoundError:
                pass
            raise clean_error
    return output_mod

@refresher
def disable_mod(mod: BcmlMod, wait_merge: bool = False):
    remergers = []
    partials = {}
    print(f'Disabling {mod.name}...')
    for merger in [merger() for merger in mergers.get_mergers()]:
        if merger.is_mod_logged(mod):
            remergers.append(merger)
            if merger.can_partial_remerge():
                partials[merger.NAME] = merger.get_mod_affected(mod)
    rules_path: Path = mod.path / 'rules.txt'
    rules_path.rename(rules_path.with_suffix('.txt.disable'))
    if not wait_merge:
        print(f'Remerging affected files...')
        for merger in remergers:
            if merger.NAME in partials:
                merger.set_options({'only_these': partials[merger.NAME]})
            merger.perform_merge()
    print(f'{mod.name} disabled')


@refresher
def enable_mod(mod: BcmlMod, wait_merge: bool = False):
    print(f'Enabling {mod.name}...')
    rules_path: Path = mod.path / 'rules.txt.disable'
    rules_path.rename(rules_path.with_suffix(''))
    if not wait_merge:
        print(f'Remerging affected files...')
        remergers = []
        partials = {}
        for merger in [merger() for merger in mergers.get_mergers()]:
            if merger.is_mod_logged(mod):
                remergers.append(merger)
                if merger.can_partial_remerge():
                    partials[merger.NAME] = merger.get_mod_affected(mod)
        for merger in remergers:
            if merger.NAME in partials:
                merger.set_options({'only_these': partials[merger.NAME]})
            merger.perform_merge()
    print(f'{mod.name} enabled')


@refresher
def uninstall_mod(mod: BcmlMod, wait_merge: bool = False):
    print(f'Uninstalling {mod.name}...')
    partials = mod.get_partials()
    remergers = set(mod.mergers)
    shutil.rmtree(str(mod.path))

    for fall_mod in [m for m in util.get_installed_mods() if m.priority > mod.priority]:
        remergers |= set(fall_mod.mergers)
        partials.update(fall_mod.get_partials())
        fall_mod.change_priority(fall_mod.priority - 1)

    if not wait_merge:
        for merger in mergers.sort_mergers(remergers):
            if merger.NAME in partials:
                merger.set_options({'only_these': partials[merger.NAME]})
            merger.perform_merge()

    print(f'{mod.name} has been uninstalled.')


@refresher
def refresh_merges():
    print('Cleansing old merges...')
    shutil.rmtree(util.get_master_modpack_dir())
    print('Refreshing merged mods...')
    for merger in mergers.sort_mergers(
        [merger_class() for merger_class in mergers.get_mergers()]
    ):
        merger.perform_merge()


def _clean_sarc(file: Path, hashes: dict, tmp_dir: Path):
    canon = util.get_canon_name(file.relative_to(tmp_dir))
    try:
        stock_file = util.get_game_file(file.relative_to(tmp_dir))
    except FileNotFoundError:
        return
    with stock_file.open('rb') as old_file:
        old_sarc = sarc.read_file_and_make_sarc(old_file)
        if not old_sarc:
            return
        old_files = set(old_sarc.list_files())
    if canon not in hashes:
        return
    with file.open('rb') as s_file:
        base_sarc = sarc.read_file_and_make_sarc(s_file)
    if not base_sarc:
        return
    new_sarc = sarc.SARCWriter(util.get_settings('wiiu'))
    can_delete = True
    for nest_file in base_sarc.list_files():
        canon = nest_file.replace('.s', '.')
        ext = Path(canon).suffix
        if ext in {'.yml', '.bak'}:
            continue
        file_data = base_sarc.get_file_data(nest_file).tobytes()
        xhash = xxhash.xxh32(util.unyaz_if_needed(file_data)).hexdigest()
        if nest_file in old_files:
            old_hash = xxhash.xxh32(
                util.unyaz_if_needed(old_sarc.get_file_data(nest_file).tobytes())
            ).hexdigest()
        if nest_file not in old_files or (xhash != old_hash and ext not in util.AAMP_EXTS):
            can_delete = False
            new_sarc.add_file(nest_file, file_data)
    del old_sarc
    if can_delete:
        del new_sarc
        file.unlink()
    else:
        with file.open('wb') as s_file:
            if file.suffix.startswith('.s') and file.suffix != '.ssarc':
                s_file.write(util.compress(new_sarc.get_bytes()))
            else:
                new_sarc.write(s_file)


def create_bnp_mod(mod: Path, output: Path, options: dict = None):
    """[summary]
    
    :param mod: [description]
    :type mod: Path
    :param output: [description]
    :type output: Path
    :param options: [description], defaults to {}
    :type options: dict, optional
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

    print('Packing loose files...')
    pack_folders = sorted(
        {d for d in tmp_dir.rglob('**/*') if d.is_dir() and d.suffix in util.SARC_EXTS},
        key=lambda d: len(d.parts), reverse=True
    )
    for folder in pack_folders:
        new_tmp: Path = folder.with_suffix(folder.suffix + '.tmp')
        shutil.move(folder, new_tmp)
        new_sarc = sarc.SARCWriter(be=util.get_settings('wiiu'))
        for file in {f for f in new_tmp.rglob('**/*') if f.is_file()}:
            new_sarc.add_file(file.relative_to(new_tmp).as_posix(), file.read_bytes())
        sarc_bytes = new_sarc.get_bytes()
        if str(folder.suffix).startswith('.s') and folder.suffix != '.sarc':
            sarc_bytes = util.compress(sarc_bytes)
        folder.write_bytes(sarc_bytes)
        shutil.rmtree(new_tmp)

    if not options:
        options = {}
    options['texts'] = {'user_only': False}
    logged_files = generate_logs(tmp_dir, options=options)

    print('Removing unnecessary files...')
    if (tmp_dir / 'logs' / 'map.yml').exists():
        print('Removing map units...')
        for file in [file for file in logged_files if isinstance(file, Path) and \
                           fnmatch(file.name, '[A-Z]-[0-9]_*.smubin')]:
            file.unlink()
    if [file for file in (tmp_dir / 'logs').glob('*texts*')]:
        print('Removing language bootup packs...')
        for bootup_lang in (tmp_dir / 'content' / 'Pack').glob('Bootup_*.pack'):
            bootup_lang.unlink()
    if (tmp_dir / 'logs' / 'actorinfo.yml').exists() and \
       (tmp_dir / 'content' / 'Actor' / 'ActorInfo.product.sbyml').exists():
        print('Removing ActorInfo.product.sbyml...')
        (tmp_dir / 'content' / 'Actor' / 'ActorInfo.product.sbyml').unlink()
    if (tmp_dir / 'logs' / 'gamedata.yml').exists() or (tmp_dir / 'logs' / 'savedata.yml').exists():
        print('Removing gamedata sarcs...')
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
    print('Creating partial packs...')
    sarc_files = {file for file in tmp_dir.rglob('**/*') if file.suffix in util.SARC_EXTS}
    if sarc_files:
        num_threads = min(len(sarc_files), cpu_count())
        set_start_method('spawn', True)
        pool = Pool(processes=num_threads)
        pool.map(partial(_clean_sarc, hashes=hashes, tmp_dir=tmp_dir), sarc_files)
        pool.close()
        pool.join()

        sarc_files = {file for file in tmp_dir.rglob('**/*') if file.suffix in util.SARC_EXTS}
        if sarc_files:
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

    print('Cleaning any junk files...')
    for file in tmp_dir.rglob('**/*'):
        if file.parent.stem == 'logs':
            continue
        if file.suffix in ['.yml', '.bak', '.tmp', '.old']:
            file.unlink()

    print('Removing blank folders...')
    for folder in reversed(list(tmp_dir.rglob('**/*'))):
        if folder.is_dir() and not list(folder.glob('*')):
            shutil.rmtree(folder)

    print(f'Saving output file to {str(output)}...')
    x_args = [ZPATH, 'a', str(output), f'{str(tmp_dir / "*")}']
    if system() == 'Windows':
        subprocess.run(x_args, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, creationflags=util.CREATE_NO_WINDOW)
    else:
        subprocess.run(x_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
    num_mods = len([d for d in util.get_modpack_dir().glob('*') if d.is_dir()])
    output = util.get_cemu_dir() / 'bcml_backups' / f'{name}---{num_mods - 1}.7z'
    output.parent.mkdir(parents=True, exist_ok=True)
    print(f'Saving backup {name}...')
    x_args = [ZPATH, 'a', str(output), f'{str(util.get_modpack_dir() / "*")}']
    if system() == 'Windows':
        subprocess.run(x_args, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, creationflags=util.CREATE_NO_WINDOW)
    else:
        subprocess.run(x_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
        backup = Path(backup)
    if not backup.exists():
        raise FileNotFoundError(f'The backup "{backup.name}" does not exist.')
    print('Clearing installed mods...')
    for folder in [item for item in util.get_modpack_dir().glob('*') if item.is_dir()]:
        shutil.rmtree(str(folder))
    print('Extracting backup...')
    x_args = [ZPATH,
              'x', str(backup), f'-o{str(util.get_modpack_dir())}']
    if system() == 'Windows':
        subprocess.run(x_args, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, creationflags=util.CREATE_NO_WINDOW)
    else:
        subprocess.run(x_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print('Re-enabling mods in Cemu...')
    refresh_master_export()
    print(f'Backup "{backup.name}" restored')


def link_master_mod(output: Path = None):
    if not output:
        output = util.get_cemu_dir() / 'graphicPacks' / 'BreathOfTheWild_BCML'
    if output.exists():
        shutil.rmtree(str(output), ignore_errors=True)
    output.mkdir(parents=True, exist_ok=True)
    mod_folders: List[Path] = sorted(
        [item for item in util.get_modpack_dir().glob('*') if item.is_dir()],
        reverse=True
    )
    shutil.copy(
        str(util.get_master_modpack_dir() / 'rules.txt'),
        str(output / 'rules.txt')
    )
    link_or_copy = os.link
    for mod_folder in mod_folders:
        for item in mod_folder.rglob('**/*'):
            rel_path = item.relative_to(mod_folder)
            if (output / rel_path).exists()\
               or (str(rel_path).startswith('logs'))\
               or (len(rel_path.parts) == 1 and rel_path.suffix != '.txt'):
                continue
            if item.is_dir():
                (output / rel_path).mkdir(parents=True, exist_ok=True)
            elif item.is_file():
                try:
                    link_or_copy(
                        str(item),
                        str(output / rel_path)
                    )
                except OSError:
                    from shutil import copyfile as link_or_copy
