"""Provides features for installing, creating, and mananging BCML mods"""
# Copyright 2019 Nicene Nerd <macadamiadaze@gmail.com>
# Licensed under GPLv3+
# pylint: disable=too-many-lines
import datetime
import os
import shutil
import subprocess
import traceback
from configparser import ConfigParser
from fnmatch import fnmatch
from functools import partial
from multiprocessing import Pool, cpu_count
from pathlib import Path
from typing import Union, List
from xml.dom import minidom

import sarc
import xxhash

from bcml import pack, texts, util, data, merge, rstable, mubin, events, mergers
from bcml.util import BcmlMod


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
        raise Exception('The mod provided was not a supported archive (BNP, ZIP, RAR, or 7z).')
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
            raise FileNotFoundError(f'No rules.txt was found in "{path.name}".')
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


def find_modded_files(tmp_dir: Path, verbose: bool = False, original_pool: Pool = None) -> List[Union[Path, str]]:
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
                if verbose:
                    print(f'Ignored unknown file {file.relative_to(tmp_dir).as_posix()}')
                continue
            if util.is_file_modded(canon, file, True):
                modded_files.append(file)
                if verbose:
                    print(f'Found modded file {canon}')
            else:
                if 'Aoc/0010/Map/MainField' in canon:
                    file.unlink()
                if verbose:
                    print(f'Ignored unmodded file {canon}')
                continue
    total = len(modded_files)
    print(f'Found {total} modified file{"s" if total > 1 else ""}')

    total = 0
    sarc_files = [file for file in modded_files if file.suffix in util.SARC_EXTS]
    if sarc_files:
        print(f'Scanning files packed in SARCs...')
        num_threads = min(len(sarc_files), cpu_count() - 1)
        pool = original_pool or Pool(processes=num_threads)
        modded_sarc_files = pool.map(
            partial(find_modded_sarc_files, tmp_dir=tmp_dir, verbose=verbose),
            sarc_files
        )
        for files in modded_sarc_files:
            total += len(files)
            modded_files.extend(files)
        if not original_pool:
            pool.close()
            pool.join()
        print(f'Found {total} modified packed file{"s" if total > 1 else ""}')
    return modded_files


def find_modded_sarc_files(mod_sarc: Union[Path, sarc.SARC], tmp_dir: Path, name: str = '',
                           aoc: bool = False, verbose: bool = False) -> List[str]:
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
            if verbose:
                print(f'Found modded file {canon} in {str(name).replace("//", "/")}')
            if util.is_file_sarc(canon) and '.ssarc' not in file:
                try:
                    nest_sarc = sarc.SARC(contents)
                except ValueError:
                    continue
                sub_mod_files = find_modded_sarc_files(
                    nest_sarc,
                    name=nest_path,
                    tmp_dir=tmp_dir,
                    aoc=aoc,
                    verbose=verbose
                )
                modded_files.extend(sub_mod_files)
        else:
            if verbose:
                print(f'Ignored unmodded file {canon} in {str(name).replace("//", "/")}')
    return modded_files


def generate_logs(tmp_dir: Path, verbose: bool = False, options: dict = None, original_pool: Pool = None) -> List[Path]:
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

    pool = original_pool or Pool(cpu_count())
    print('Scanning for modified files...')
    modded_files = find_modded_files(tmp_dir, verbose=verbose, original_pool=original_pool)
    if not modded_files:
        raise RuntimeError('No modified files were found. Very unusual.')

    (tmp_dir / 'logs').mkdir(parents=True, exist_ok=True)
    for merger_class in [merger_class for merger_class in mergers.get_mergers() \
                        if merger_class.NAME not in options['disable']]:
        merger = merger_class()
        merger.set_pool(pool)
        if options is not None and merger.NAME in options:
            merger.set_options(options[merger.NAME])
        merger.log_diff(tmp_dir, modded_files)
    if not original_pool:
        pool.close()
        pool.join()
    return modded_files


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
    # Issue #33 - check for new cemu Entry layout
    new_cemu_version = False
    for entry in gpack.getElementsByTagName('Entry'):
        if len(entry.getElementsByTagName('filename')) == 0:
            new_cemu_version = True
            break
    # Issue #33 - end Entry layout check
    for entry in gpack.getElementsByTagName('Entry'):
    # Issue #33 - handle BCML node by Cemu version
        if new_cemu_version:
            if 'BCML' in entry.getAttribute('filename'):
                gpack.removeChild(entry)
        else:
            try:
                if 'BCML' in entry.getElementsByTagName('filename')[0].childNodes[0].data:
                    gpack.removeChild(entry)
            except IndexError:
                pass
    bcmlentry = create_settings_mod_node(settings, new_cemu_version)
    # Issue #33 - end BCML node
    gpack.appendChild(bcmlentry)
    for mod in util.get_installed_mods():
        # Issue #33 - handle new mod nodes by Cemu version
        modentry = create_settings_mod_node(settings, new_cemu_version, mod)
        # Issue #33 - end handling new mod nodes
        gpack.appendChild(modentry)
    settings.writexml(setpath.open('w', encoding='utf-8'), addindent='    ', newl='\n')


# Issue #33 - break node creation out into functions for future readability
def create_settings_mod_node(settings, new_cemu: bool, mod=None) -> minidom.Element:
    if mod:
        modpath = f'graphicPacks\\BCML\\{mod.path.parts[-1]}\\rules.txt'
    else:
        modpath = f'graphicPacks\\BCML\\9999_BCML\\rules.txt'
    modentry = settings.createElement('Entry')
    if new_cemu:
        modentry.setAttribute('filename', modpath)
    else:
        entryfile = settings.createElement('filename')
        entryfile.appendChild(settings.createTextNode(modpath))
        modentry.appendChild(entryfile)
    entrypresethead = settings.createElement('Preset')
    entrypreset = settings.createElement('preset')
    entrypreset.appendChild(settings.createTextNode(''))
    entrypresethead.appendChild(entrypreset)
    modentry.appendChild(entrypresethead)
    return modentry


def install_mod(mod: Path, verbose: bool = False, options: dict = None, wait_merge: bool = False,
                insert_priority: int = 0):
    """
    Installs a graphic pack mod, merging RSTB changes and optionally packs and texts

    :param mod: Path to the mod to install. Must be a RAR, 7z, or ZIP archive or a graphicpack
    directory containing a rules.txt file.
    :type mod: class:`pathlib.Path`
    :param verbose: Whether to display more detailed output, defaults to False.
    :type verbose: bool, optional
    :param wait_merge: Install mod and log changes, but wait to run merge manually,
    defaults to False.
    :type wait_merge: bool, optional
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
            tmp_dir = util.get_work_dir() / f'tmp_{mod.name}'
            shutil.copytree(str(mod), str(tmp_dir))
        else:
            print(f'Cannot open mod at {str(mod)}, no rules.txt found')
            return
    else:
        print(f'Error: {str(mod)} is neither a valid file nor a directory')
        return

    pool: Pool
    try:
        rules = util.RulesParser()
        rules.read(tmp_dir / 'rules.txt')
        mod_name = str(rules['Definition']['name']).strip(' "\'')
        print(f'Identified mod: {mod_name}')

        logs = tmp_dir / 'logs'
        if logs.exists():
            print('This mod supports Quick Install! Loading changes...')
            for merger in [merger() for merger in mergers.get_mergers() \
                           if merger.NAME in options['disable']]:
                if merger.is_mod_logged(BcmlMod('', 0, tmp_dir)):
                    (tmp_dir / 'logs' / merger.log_name()).unlink()
        else:
            pool = Pool(cpu_count())
            generate_logs(tmp_dir=tmp_dir, verbose=verbose, options=options, original_pool=pool)
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
        print()
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

        rulepath = os.path.basename(rules['Definition']['path']).replace('"', '')
        rules['Definition']['path'] = f'{{BCML: DON\'T TOUCH}}/{rulepath}'
        rules['Definition']['fsPriority'] = str(priority)
        with Path(mod_dir / 'rules.txt').open('w', encoding='utf-8') as r_file:
            rules.write(r_file)

        output_mod = BcmlMod(mod_name, priority, mod_dir)
        try:
            util.get_mod_link_meta(rules)
            util.get_mod_preview(output_mod, rules)
        except Exception: # pylint: disable=broad-except
            pass

        print(f'Enabling {mod_name} in Cemu...')
        refresh_cemu_mods()
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
                merger.set_pool(pool)
                if merger.NAME in options:
                    merger.set_options(options[merger.NAME])
                if merger.is_mod_logged(output_mod):
                    merger.perform_merge()
            print()
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
    pool.close()
    pool.join()
    return output_mod


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


def enable_mod(mod: BcmlMod, wait_merge: bool = False):
    print(f'Enabling {mod.name}...')
    rules_path: Path = mod.path / 'rules.txt.disable'
    rules_path.rename(rules_path.with_suffix(''))
    # refresh_merges()
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
    refresh_cemu_mods()
    print(f'{mod.name} enabled')


def uninstall_mod(mod: Union[Path, BcmlMod, str], wait_merge: bool = False, verbose: bool = False):
    """
    Uninstalls the mod currently installed at the specified path and updates merges as needed

    :param mod: The mod to remove, as a path or a BcmlMod.
    :param wait_merge: Resort mods but don't remerge anything yet, defaults to False.
    :type wait_merge: bool, optional
    :param verbose: Whether to display more detailed output, defaults to False.
    :type verbose: bool, optional
    """
    path = Path(mod) if isinstance(mod, str) else mod.path if isinstance(mod, BcmlMod) else mod
    mod_name, mod_priority, _ = util.get_mod_info(path / 'rules.txt') \
                                if not isinstance(mod, BcmlMod) else mod
    print(f'Uninstalling {mod_name}...')
    remergers = set()
    partials = {}
    for merger in [merger() for merger in mergers.get_mergers()]:
        if merger.is_mod_logged(BcmlMod(mod_name, mod_priority, path)):
            remergers.add(merger)
            if merger.can_partial_remerge():
                partials[merger.NAME] = merger.get_mod_affected(mod)

    shutil.rmtree(str(path))
    next_mod = util.get_mod_by_priority(mod_priority + 1)
    if next_mod:
        print('Adjusting mod priorities...')
        change_mod_priority(next_mod, mod_priority,
                            wait_merge=True, verbose=verbose)
        print()

    if not wait_merge:
        pool = Pool(cpu_count())
        for merger in mergers.sort_mergers(remergers):
            merger.set_pool(pool)
            if merger.NAME in partials:
                merger.set_options({'only_these': partials[merger.NAME]})
            merger.perform_merge()
        pool.close()
        pool.join()
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

    all_mergers = [merger() for merger in mergers.get_mergers()]
    remergers = set()
    partials = {}
    for merger in all_mergers:
        if merger.is_mod_logged(mod):
            remergers.add(merger)
            if merger.can_partial_remerge():
                partials[merger.NAME] = set(merger.get_mod_affected(mod))

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
            for merger in all_mergers:
                if merger.is_mod_logged(mod):
                    remergers.add(merger)
                    if merger.can_partial_remerge():
                        if merger.NAME not in partials:
                            partials[merger.NAME] = set()
                        partials[merger.NAME] |= set(merger.get_mod_affected(mod))

            new_mod_id = util.get_mod_id(mod[0], mod[1])
            shutil.move(str(mod[2]), str(mod[2].parent / new_mod_id))
            rules = util.RulesParser()
            rules.read(str(mod.path.parent / new_mod_id / 'rules.txt'))
            rules['Definition']['fsPriority'] = str(mod[1])
            with (mod[2].parent / new_mod_id / 'rules.txt').open('w', encoding='utf-8') as r_file:
                rules.write(r_file)
            refresh_cemu_mods()
    if not wait_merge:
        for merger in mergers.sort_mergers(remergers):
            if merger.NAME in partials:
                merger.set_options({'only_these': partials[merger.NAME]})
            merger.perform_merge()
    if wait_merge:
        print('Mods resorted, will need to remerge later')
    print('Finished updating mod priorities.')


def refresh_merges(verbose: bool = False):
    """
    Runs RSTB, pack, and text merges together

    :param verbose: Whether to display more detailed output, defaults to False.
    :type verbose: bool, optional
    """
    print('Cleansing old merges...')
    shutil.rmtree(util.get_master_modpack_dir())
    print('Refreshing merged mods...')
    pool = Pool(cpu_count())
    for merger in mergers.sort_mergers([merger_class() for merger_class in mergers.get_mergers()]):
        merger.set_pool(pool)
        merger.perform_merge()
    pool.close()
    pool.join()


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
    new_sarc = sarc.SARCWriter(True)
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
        new_sarc = sarc.SARCWriter(be=True)
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
    pool = Pool(cpu_count())
    logged_files = generate_logs(tmp_dir, options=options, original_pool=pool)

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
                os.link(
                    str(item),
                    str(output / rel_path)
                )
