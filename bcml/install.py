import os
import shutil
import subprocess
import time
from configparser import ConfigParser
from fnmatch import fnmatch
from functools import partial
from pathlib import Path
from multiprocessing import Process, Queue, Pool, cpu_count
from typing import Union
from xml.dom import minidom

import byml
import rstb
import sarc
import wszst_yaz0
import xxhash
import yaml
from byml import yaml_util

from bcml import pack, texts, util, data, merge, rstable
from bcml.util import BcmlMod


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
    formats = ['.rar', '.zip', '.7z']
    if tmpdir.exists():
        shutil.rmtree(tmpdir)
    if path.suffix.lower() in formats:
        x_args = [str(util.get_exec_dir() / 'helpers' / '7z.exe'),
                  'x', str(path), f'-o{str(tmpdir)}']
        subprocess.run(x_args, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, creationflags=util.CREATE_NO_WINDOW)
    else:
        raise Exception(
            'The mod provided was not a supported archive (ZIP, RAR, or 7z).')
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


def threaded_byml_diff(queue: Queue, store_path: str, file: Union[Path, str], tmp_dir: Path):
    queue.put(('byml', store_path, merge.get_byml_diff(file, tmp_dir)))


def threaded_aamp_diff(queue: Queue, store_path: str, file: Union[Path, str], tmp_dir: Path):
    queue.put(('aamp', store_path, merge.get_aamp_diff(file, tmp_dir)))


def find_modded_files(tmp_dir: Path, deep_merge: bool = False, verbose: bool = False) -> (dict, list, dict):
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
    diffs = {
        'aamp': {},
        'byml': {}
    }
    processes = []
    queue = Queue()
    rstb_path: Path = tmp_dir / 'content' / 'System' / \
        'Resource' / 'ResourceSizeTable.product.srsizetable'
    if rstb_path.exists():
        rstb_path.unlink()
    for file in tmp_dir.rglob('**/*'):
        if file.is_file():
            canon = util.get_canon_name(file.relative_to(tmp_dir).as_posix())
            if canon is None:
                if verbose:
                    log.append(
                        f'Ignored unknown file {file.relative_to(tmp_dir).as_posix()}')
                continue
            if util.is_file_modded(canon, file, True):
                modded_files[canon] = {
                    'path': file.relative_to(tmp_dir),
                    'rstb': rstable.calculate_size(file),
                    'nested': False
                }
                if verbose:
                    log.append(f'Found modded file {canon}')
                if deep_merge and util.is_file_aamp(str(file)):
                    p = Process(target=threaded_aamp_diff, args=(queue, file.relative_to(tmp_dir).as_posix(),
                                                                 file, tmp_dir))
                    processes.append(p)
                    p.start()
                elif deep_merge and util.is_file_byml(str(file)):
                    if 'ActorInfo' not in str(file):
                        p = Process(target=threaded_byml_diff, args=(queue, file.relative_to(tmp_dir).as_posix(),
                                                                     file, tmp_dir))
                        processes.append(p)
                        p.start()
            else:
                if verbose:
                    log.append(f'Ignored unmodded file {canon}')
                continue
    if len(processes) > 0:
        for proc in processes:
            proc.join()
            file_type, file, diff = queue.get()
            diffs[file_type][file] = diff
    total = len(modded_files)
    log.append(f'Found {total} modified file{"s" if total > 1 else ""}')
    return modded_files, log, diffs


def find_modded_sarc_files(mod_sarc: sarc.SARC, name: str, tmp_dir: Path, aoc: bool = False, nest_level: int = 0,
                           deep_merge: bool = False, verbose: bool = False) -> (dict, list):
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
    diffs = {
        'aamp': {},
        'byml': {}
    }
    indent = '  ' * (nest_level + 1)
    processes = []
    queue = Queue()
    for file in mod_sarc.list_files():
        canon = file.replace('.s', '.')
        if aoc:
            canon = 'Aoc/0010/' + canon
        ext = os.path.splitext(file)[1]
        contents = mod_sarc.get_file_data(file).tobytes()
        contents = util.unyaz_if_needed(contents)
        if util.is_file_modded(canon, contents, True):
            rstbsize = rstb.SizeCalculator().calculate_file_size_with_ext(contents, True, ext)
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
                                                                                   verbose=verbose)
                modded_files.update(sub_mod_files)
                diffs['aamp'].update(sub_mod_diffs['aamp'])
                diffs['byml'].update(sub_mod_diffs['byml'])
                log.extend(sub_mod_log)
            elif deep_merge and util.is_file_aamp(str(file)):
                p = Process(target=threaded_aamp_diff, args=(queue, modded_files[canon]['path'],
                                                             tmp_dir.as_posix() + '/' +
                                                             modded_files[canon]['path'],
                                                             tmp_dir))
                processes.append(p)
                p.start()
            elif deep_merge and util.is_file_byml(str(file)):
                p = Process(target=threaded_byml_diff, args=(queue, modded_files[canon]['path'],
                                                             tmp_dir.as_posix() + '/' +
                                                             modded_files[canon]['path'],
                                                             tmp_dir))
                processes.append(p)
                p.start()
        else:
            if verbose:
                log.append(
                    f'{indent}Ignored unmodded file {canon} in {str(name).replace("//", "/")}')
    if len(processes) > 0:
        for p in processes:
            p.join()
            file_type, file, diff = queue.get()
            diffs[file_type][file] = diff
    return modded_files, log, diffs


def threaded_find_modded_sarc_files(file: str, modded_files: dict, tmp_dir: Path, deep_merge: bool, verbose: bool):
    with Path(tmp_dir / modded_files[file]['path']).open('rb') as sf:
        mod_sarc = sarc.read_file_and_make_sarc(sf)
    if not mod_sarc:
        print(f'Skipped broken pack {file}')
        return {}, [], {}
    return find_modded_sarc_files(mod_sarc, modded_files[file]['path'],
                                  tmp_dir=tmp_dir,
                                  aoc=('aoc' in file.lower()),
                                  verbose=verbose, deep_merge=deep_merge)


def add_mod_to_cemu(mod_dir):
    """
    Adds a mod to Cemu's enabled graphic packs

    :param mod_dir: The name (not path) of the mod directory.
    :type mod_dir: str
    """
    setpath = util.get_cemu_dir() / 'settings.xml'
    if not setpath.exists():
        raise FileNotFoundError('The Cemu settings file could not be found.')
    setread = ''
    with setpath.open('r') as setfile:
        for line in setfile:
            setread += line.strip()
    settings = minidom.parseString(setread)
    gpack = settings.getElementsByTagName('GraphicPack')[0]
    hasbcml = False
    for entry in gpack.getElementsByTagName('Entry'):
        if '9999_BCML' in entry.getElementsByTagName('filename')[0].childNodes[0].data:
            hasbcml = True
    if not hasbcml:
        bcmlentry = settings.createElement('Entry')
        entryfile = settings.createElement('filename')
        entryfile.appendChild(settings.createTextNode(
            f'graphicPacks\\BCML\\9999_BCML\\rules.txt'))
        entrypreset = settings.createElement('preset')
        entrypreset.appendChild(settings.createTextNode(''))
        bcmlentry.appendChild(entryfile)
        bcmlentry.appendChild(entrypreset)
        gpack.appendChild(bcmlentry)
    modentry = settings.createElement('Entry')
    entryfile = settings.createElement('filename')
    entryfile.appendChild(settings.createTextNode(
        f'graphicPacks\\BCML\\{mod_dir}\\rules.txt'))
    entrypreset = settings.createElement('preset')
    entrypreset.appendChild(settings.createTextNode(''))
    modentry.appendChild(entryfile)
    modentry.appendChild(entrypreset)
    gpack.appendChild(modentry)
    settings.writexml(setpath.open('w'), addindent='    ', newl='\n')


def install_mod(mod: Path, verbose: bool = False, no_packs: bool = False, no_texts: bool = False,
                no_gamedata: bool = False, no_savedata: bool = False, no_actorinfo: bool = False,
                leave_rstb: bool = False, shrink_rstb: bool = False, wait_merge: bool = False,
                deep_merge: bool = False):
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
    :param leave_rstb: Do not remove RSTB entries when the proper value can't be calculated, defaults to False.
    :type leave_rstb: bool, optional
    :param shrink_rstb: Shrink RSTB values where possible, defaults to False.
    :type shrink_rstb: bool, optional
    :param wait_merge: Install mod and log changes, but wait to run merge manually, defaults to False.
    :type wait_merge: bool, optional
    :param deep_merge: Attempt to merge changes within individual files, defaults to False.
    :type deep_merge: bool, optional
    """
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

    print()
    print('Scanning for modified files...')
    modded_files, rstb_changes, diffs = find_modded_files(
        tmp_dir, verbose=verbose, deep_merge=deep_merge)
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
            del modded_files[file]
            continue
    sarc_files = [file for file in modded_files if util.is_file_sarc(file)]
    if len(sarc_files) > 0:
        num_threads = min(len(sarc_files), cpu_count())
        p = Pool(processes=num_threads)
        thread_sarc_search = partial(threaded_find_modded_sarc_files, modded_files=modded_files, tmp_dir=tmp_dir,
                                     deep_merge=deep_merge, verbose=verbose)
        results = p.map(thread_sarc_search, sarc_files)
        p.close()
        p.join()
        for result in results:
            modded_sarcs, sarc_changes, nested_diffs = result
            if len(modded_sarcs) > 0:
                modded_sarc_files.update(modded_sarcs)
                if deep_merge:
                    diffs['aamp'].update(nested_diffs['aamp'])
                    diffs['byml'].update(nested_diffs['byml'])
                if len(sarc_changes) > 0:
                    print('\n'.join(sarc_changes))
        mod_sarc_count = len(modded_sarc_files)
        print(
            f'Found {mod_sarc_count} modded pack file{"s" if mod_sarc_count != 1 else ""}')

    if len(modded_files) == 0:
        print('No modified files were found. Very unusual.')
        return
    if len(modded_sarc_files) == 0:
        no_packs = True

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

    if deep_merge:
        deep_merge = len(diffs['aamp']) > 0 or len(diffs['byml']) > 0

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

    print('Saving logs...')
    (mod_dir / 'logs').mkdir(parents=True, exist_ok=True)
    with Path(mod_dir / 'logs' / 'rstb.log').open('w') as rf:
        rf.write('name,rstb\n')
        modded_files.update(modded_sarc_files)
        for file in modded_files:
            ext = os.path.splitext(file)[1]
            if ext not in ['.pack', '.bgdata', '.txt', '.bgsvdata', 'data.sarc', '.bat', '.ini', '.png'] \
                    and 'ActorInfo' not in file:
                rf.write('{},{},{}\n'
                         .format(file, modded_files[file]["rstb"], str(modded_files[file]["path"]).replace('\\', '/'))
                         )

    if not no_packs:
        with Path(mod_dir / 'logs' / 'packs.log').open('w') as pf:
            pf.write('name,path\n')
            for file in modded_files:
                if any(file.endswith(ext) for ext in ['pack', 'sarc']) and not modded_files[file]['nested']:
                    pf.write(f'{file},{modded_files[file]["path"]}\n')

    if is_text_mod:
        for lang in text_mods:
            with Path(mod_dir / 'logs' / f'texts_{lang}.yml').open('w') as tf:
                yaml.dump(text_mods[lang][0], tf)
            text_sarc = text_mods[lang][1]
            if text_sarc is not None:
                with Path(mod_dir / 'logs' / f'newtexts_{lang}.sarc').open('wb') as sf:
                    text_sarc.write(sf)

    dumper = yaml.CDumper
    yaml_util.add_representers(dumper)
    if not no_gamedata:
        with (mod_dir / 'logs' / 'gamedata.yml').open('w') as gf:
            yaml.dump(modded_bgentries, gf, Dumper=dumper, allow_unicode=True, encoding='utf-8',
                      default_flow_style=None)
    if not no_savedata:
        with (mod_dir / 'logs' / 'savedata.yml').open('w') as sf:
            yaml.dump(modded_bgsventries, sf, Dumper=dumper, allow_unicode=True, encoding='utf-8',
                      default_flow_style=None)
    if not no_actorinfo:
        with (mod_dir / 'logs' / 'actorinfo.yml').open('w') as af:
            yaml.dump(modded_actors, af, Dumper=dumper, allow_unicode=True, encoding='utf-8',
                      default_flow_style=None)
    if deep_merge:
        with(mod_dir / 'logs' / 'deepmerge.yml').open('w') as df:
            yaml.safe_dump(diffs, df, allow_unicode=True, encoding='utf-8')

    rulepath = os.path.basename(rules['Definition']['path']).replace('"', '')
    rules['Definition'][
        'path'] = f'The Legend of Zelda: Breath of the Wild/BCML Mods/{rulepath}'
    rules['Definition']['fsPriority'] = str(priority)
    with Path(mod_dir / 'rules.txt').open('w') as rf:
        rules.write(rf)

    if leave_rstb:
        Path(mod_dir / 'logs' / '.leave').open('w').close()
    if shrink_rstb:
        Path(mod_dir / 'logs' / '.shrink').open('w').close()

    print(f'Enabling {mod_name} in Cemu...')
    add_mod_to_cemu(mod_dir.stem)

    util.create_bcml_graphicpack_if_needed()

    if wait_merge:
        print('Mod installed, but not merged. Make sure to run a merge manually before playing.')
    else:
        print('Performing merges...')
        print()
        rstable.generate_master_rstb(verbose)
        if not no_packs and len(modded_sarc_files) > 1:
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
        if deep_merge:
            merge.deep_merge(verbose)
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
    pack_mod = util.is_pack_mod(path)
    text_mods = texts.get_modded_languages(path)
    gamedata_mod = util.is_gamedata_mod(path)
    savedata_mod = util.is_savedata_mod(path)
    actorinfo_mod = util.is_actorinfo_mod(path)
    deepmerge_mod = util.is_deepmerge_mod(path)

    shutil.rmtree(str(path))
    next_mod = util.get_mod_by_priority(mod_priority + 1)
    if next_mod:
        print('Adjusting mod priorities...')
        change_mod_priority(next_mod, mod_priority,
                            wait_merge=True, verbose=verbose)
        print()

    if not wait_merge:
        if pack_mod:
            pack.merge_installed_packs(verbose)
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
        if deepmerge_mod:
            merge.deep_merge(verbose)
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
    remerge_packs = util.is_pack_mod(path)
    remerge_texts = texts.get_modded_languages(path)
    remerge_gamedata = util.is_gamedata_mod(path)
    remerge_savedata = util.is_savedata_mod(path)
    remerge_actorinfo = util.is_actorinfo_mod(path)
    deepmerge = util.is_deepmerge_mod(path)
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
            remerge_packs = util.is_pack_mod(mod) or remerge_packs
            remerge_actorinfo = util.is_actorinfo_mod(mod) or remerge_actorinfo
            remerge_gamedata = util.is_gamedata_mod(mod) or remerge_gamedata
            remerge_savedata = util.is_savedata_mod(mod) or remerge_savedata
            deepmerge = util.is_deepmerge_mod(mod) or deepmerge
            for lang in texts.get_modded_languages(mod.path):
                if lang not in remerge_texts:
                    remerge_texts.append(lang)
            new_mod_id = util.get_mod_id(mod[0], mod[1])
            os.rename(mod[2], mod[2].parent / new_mod_id)
            rules = ConfigParser()
            rules.read(str(mod.path.parent / new_mod_id / 'rules.txt'))
            rules['Definition']['fsPriority'] = str(mod[1])
            with (mod[2].parent / new_mod_id / 'rules.txt').open('w') as rf:
                rules.write(rf)
            add_mod_to_cemu(new_mod_id)
    if wait_merge:
        print('Mods resorted, will need to remerge RSTB later')
    else:
        rstable.generate_master_rstb(verbose)
        print()
    if remerge_packs:
        if wait_merge:
            print('Pack merges affected, will need to remerge later')
        else:
            print('Pack merges affected, remerging packs...')
            pack.merge_installed_packs(verbose)
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
    if deepmerge:
        if wait_merge:
            print('Deep merge affected, will need to remerge later')
        else:
            print('Deep merge affected, redoing deep merging...')
            merge.deep_merge(verbose)
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
    print('Finished updating mod priorities.')


def refresh_merges(verbose: bool = False):
    """
    Runs RSTB, pack, and text merges together

    :param verbose: Whether to display more detailed output, defaults to False.
    :type verbose: bool, optional
    """
    print('Refreshing merged mods...')
    rstable.generate_master_rstb(verbose)
    pack.merge_installed_packs(verbose)
    for bootup in util.get_master_modpack_dir().rglob('content/Pack/Bootup_*'):
        lang = util.get_file_language(bootup)
        texts.merge_texts(lang, verbose=verbose)
    data.merge_gamedata(verbose)
    data.merge_savedata(verbose)
    data.merge_actorinfo(verbose)
    merge.deep_merge(verbose)
