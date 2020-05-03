"""Provides features for installing, creating, and mananging BCML mods"""
# Copyright 2020 Nicene Nerd <macadamiadaze@gmail.com>
# Licensed under GPLv3+
# pylint: disable=too-many-lines
import datetime
import json
import os
import re
import shutil
import subprocess
import traceback
from base64 import b64decode
from functools import partial
from multiprocessing import Pool, cpu_count, set_start_method
from pathlib import Path
from platform import system
from shutil import rmtree
from tempfile import TemporaryDirectory
from typing import List, Union, Callable
from xml.dom import minidom

import oead
import xxhash

from bcml import util, mergers, dev, upgrade
from bcml.util import BcmlMod, ZPATH, InstallError


def extract_mod_meta(mod: Path) -> {}:
    process = subprocess.Popen(
        f'"{ZPATH}" e "{str(mod.resolve())}" -r -so info.json',
        stdout=subprocess.PIPE,
        shell=True
    )
    out, _ = process.communicate()
    process.wait()
    return json.loads(out.decode('utf-8')) if out else {}


def open_mod(path: Path) -> Path:
    if isinstance(path, str):
        path = Path(path)
    tmpdir = Path(TemporaryDirectory().name)
    archive_formats = {'.rar', '.zip', '.7z', '.bnp'}
    meta_formats = {'.json', '.txt'}
    if tmpdir.exists():
        shutil.rmtree(tmpdir, ignore_errors=True)
    if path.suffix.lower() in archive_formats:
        x_args = [ZPATH, 'x', str(path), f'-o{str(tmpdir)}']
        if system() == 'Windows':
            subprocess.run(
                x_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=util.CREATE_NO_WINDOW,
                check=False
            )
        else:
            subprocess.run(x_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    elif path.suffix.lower() in meta_formats:
        shutil.copytree(path.parent, tmpdir)
    else:
        err = ValueError()
        err.error_text = (
            'The mod provided was not a supported archive (BNP, ZIP, RAR, or 7z) '
            'or meta file (rules.txt or info.json).'
        )
        raise err
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
            err = FileNotFoundError(f'No meta file was found in "{path.name}".')
            err.error_text = (
                'No <code>info.json</code> or <code>rules.txt</code> file was found in '
                f'"{path.stem}". This could mean the mod is in an old or unsupported format. For '
                'information on converting mods, see <a href="https://gamebanana.com/tuts/12493">'
                'this tutorial</a>.'
            )
            raise err
    print('Looks like an older mod, let\'s upgrade it...')
    upgrade.convert_old_mod(rulesdir, delete_old=True)
    return rulesdir


def get_next_priority() -> int:
    i = 100
    while list(util.get_modpack_dir().glob(f'{i:04}_*')):
        i += 1
    return i


def find_modded_files(tmp_dir: Path) -> List[Union[Path, str]]:
    modded_files = []
    if isinstance(tmp_dir, str):
        tmp_dir = Path(tmp_dir)
    rstb_path = tmp_dir / util.get_content_path() / 'System' / 'Resource' /\
        'ResourceSizeTable.product.srsizetable'
    if rstb_path.exists():
        rstb_path.unlink()

    if (tmp_dir / util.get_dlc_path()).exists:
        try:
            util.get_aoc_dir()
        except FileNotFoundError as err:
            err.error_text = ('This mod uses DLC files, but BCML cannot locate the DLC folder in '
                              'your game dump.')
            raise err

    aoc_field = tmp_dir / util.get_dlc_path() / '0010' / 'Pack' / 'AocMainField.pack'
    if aoc_field.exists() and aoc_field.stat().st_size > 0:
        aoc_pack = oead.Sarc(aoc_field.read_bytes())
        for file in aoc_pack.get_files():
            ex_out = tmp_dir / util.get_dlc_path() / '0010' / file.name
            ex_out.parent.mkdir(parents=True, exist_ok=True)
            ex_out.write_bytes(file.data)
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


def find_modded_sarc_files(mod_sarc: Union[Path, oead.Sarc], tmp_dir: Path, name: str = '',
                           aoc: bool = False) -> List[str]:
    if isinstance(mod_sarc, Path):
        if any(mod_sarc.name.startswith(exclude) for exclude in ['Bootup_']):
            return []
        name = str(mod_sarc.relative_to(tmp_dir))
        aoc = util.get_dlc_path() in mod_sarc.parts or 'Aoc' in mod_sarc.parts
        try:
            mod_sarc = oead.Sarc(
                util.unyaz_if_needed(mod_sarc.read_bytes())
            )
        except (RuntimeError, ValueError, oead.InvalidDataError):
            return []
    modded_files = []
    for file, contents in [(f.name, bytes(f.data)) for f in mod_sarc.get_files()]:
        canon = file.replace('.s', '.')
        if aoc:
            canon = 'Aoc/0010/' + canon
        contents = util.unyaz_if_needed(contents)
        nest_path = str(name).replace('\\', '/') + '//' + file
        if util.is_file_modded(canon, contents, True):
            modded_files.append(
                nest_path
            )
            util.vprint(f'Found modded file {canon} in {str(name).replace("//", "/")}')
            if util.is_file_sarc(canon) and '.ssarc' not in file:
                try:
                    nest_sarc = oead.Sarc(contents)
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


def generate_logs(tmp_dir: Path, options: dict = None, pool: Pool = None) -> List[Path]:
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
        err = RuntimeError('No modified files were found.')
        err.error_text = (
            'No modified files were found. This probably means this mod is not in a supported '
            'format.'
        )
        raise err
    util.vprint(modded_files)

    this_pool = pool or Pool(cpu_count())
    (tmp_dir / 'logs').mkdir(parents=True, exist_ok=True)
    for merger_class in [merger_class for merger_class in mergers.get_mergers() \
                        if merger_class.NAME not in options['disable']]:
        merger = merger_class()
        if options is not None and merger.NAME in options:
            merger.set_options(options[merger.NAME])
        merger.set_pool(this_pool)
        merger.log_diff(tmp_dir, modded_files)
    if not pool:
        this_pool.close()
        this_pool.join()
    return modded_files


def refresher(func: Callable) -> Callable:
    def do_and_refresh(*args, **kwargs):
        res = func(*args, **kwargs)
        refresh_master_export()
        return res
    return do_and_refresh


def refresh_master_export():
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
        new_cemu = True
        entry: minidom.Element
        for entry in gpack.getElementsByTagName('Entry'):
            if new_cemu and entry.getElementsByTagName('filename'):
                new_cemu = False
            try:
                if 'BCML' in entry.getElementsByTagName('filename')[0].childNodes[0].data:
                    break
            except IndexError:
                if 'BCML' in entry.getAttribute('filename'):
                    break
        else:
            bcmlentry = settings.createElement('Entry')
            if new_cemu:
                bcmlentry.setAttribute('filename', f'graphicPacks\\BreathOfTheWild_BCML\\rules.txt')
            else:
                entryfile = settings.createElement('filename')
                entryfile.appendChild(
                    settings.createTextNode(f'graphicPacks\\BreathOfTheWild_BCML\\rules.txt')
                )
                bcmlentry.appendChild(entryfile)
            entrypreset = settings.createElement('preset')
            entrypreset.appendChild(settings.createTextNode(''))
            bcmlentry.appendChild(entrypreset)
            gpack.appendChild(bcmlentry)
            settings.writexml(setpath.open('w', encoding='utf-8'), addindent='    ', newl='\n')


def install_mod(mod: Path, options: dict = None, selects: dict = None, pool: Pool = None, insert_priority: int = 0, merge_now: bool = False):
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
        if (mod / 'rules.txt').exists() and not (mod / 'info.json').exists():
            print('Upgrading old mod format...')
            upgrade.convert_old_mod(mod, delete_old=True)
    else:
        print(f'Error: {str(mod)} is neither a valid file nor a directory')
        return

    this_pool: Pool = None
    try:
        rules = json.loads(
            (tmp_dir / 'info.json').read_text('utf-8')
        )
        mod_name = rules['name'].strip(' \'"').replace('_', '')
        print(f'Identified mod: {mod_name}')
        if rules['depends']:
            installed_ids = {m.id for m in util.get_installed_mods()}
            for depend in rules['depends']:
                if not depend in installed_ids:
                    depend_name = b64decode(depend).decode('utf8')
                    err = InstallError(f'Missing dependency {depend_name}')
                    err.error_text = (
                        f'This mod requires {depend_name}, but it is not installed. Please '
                        f'install {depend_name} and try again.'
                    )
                    raise err

        logs = tmp_dir / 'logs'
        if logs.exists():
            print('Loading mod logs...')
            for merger in [merger() for merger in mergers.get_mergers() \
                           if merger.NAME in options['disable']]:
                if merger.is_mod_logged(BcmlMod(tmp_dir)):
                    (tmp_dir / 'logs' / merger.log_name).unlink()
        else:
            this_pool = pool or Pool(cpu_count())
            generate_logs(tmp_dir=tmp_dir, options=options, pool=pool)
    except Exception as err: # pylint: disable=broad-except
        if hasattr(err, 'error_text'):
            raise err
        clean_error = RuntimeError()
        try:
            name = mod_name
        except NameError:
            name = 'your mod, the name of which could not be detected'
        clean_error.error_text = (f'<p>There was an error while processing {name}. '
                                  'This could indicate there is a problem with the mod itself, '
                                  'but it could also reflect a new or unusual edge case BCML does '
                                  'not anticipate. Here is the error:</p>'
                                  '<textarea class="scroller" disabled id="error-msg">'
                                  f'{traceback.format_exc(limit=-4)}</textarea>')
        raise clean_error

    if selects:
        for opt_dir in {d for d in (tmp_dir / 'options').glob('*') if d.is_dir()}:
            if opt_dir.name not in selects:
                shutil.rmtree(opt_dir, ignore_errors=True)
            else:
                file: Path
                for file in {f for f in opt_dir.rglob('**/*') if (
                        'logs' not in f.parts and f.is_file()
                    )}:
                    out = tmp_dir / file.relative_to(opt_dir)
                    try:
                        os.link(file, out)
                    except FileExistsError:
                        if file.suffix in util.SARC_EXTS:
                            try:
                                old_sarc = oead.Sarc(util.unyaz_if_needed(out.read_bytes()))
                            except (ValueError, oead.InvalidDataError, RuntimeError):
                                out.unlink()
                                os.link(file, out)
                            try:
                                link_sarc = oead.Sarc(util.unyaz_if_needed(file.read_bytes()))
                            except (ValueError, oead.InvalidDataError, RuntimeError):
                                continue
                            new_sarc = oead.SarcWriter.from_sarc(link_sarc)
                            for sarc_file in old_sarc.get_files():
                                if not link_sarc.get_file(sarc_file.name):
                                    new_sarc.files[sarc_file.name] = oead.Bytes(sarc_file.data)
                            del old_sarc
                            del link_sarc
                            out.write_bytes(
                                new_sarc.write()[1]
                            )
                            del new_sarc
                        else:
                            out.unlink()
                            os.link(file, out)

    priority = insert_priority
    print(f'Assigned mod priority of {priority}')
    mod_id = util.get_mod_id(mod_name, priority)
    mod_dir = util.get_modpack_dir() / mod_id

    try:
        for existing_mod in util.get_installed_mods():
            if existing_mod.priority >= priority:
                existing_mod.change_priority(existing_mod.priority + 1)

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
                    err = OSError()
                    err.error_text = (
                        'BCML could not transfer your mod from the temp directory to the BCML'
                        ' directory.'
                    )
                    raise err
        elif mod.is_dir():
            shutil.copytree(str(tmp_dir), str(mod_dir))
        shutil.rmtree(tmp_dir, ignore_errors=True)

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

    if merge_now:
        all_mergers = set()
        partials = {}
        for merger in {m() for m in mergers.get_mergers()}:
            if merger.is_mod_logged(output_mod):
                all_mergers.add(merger)
                if merger.can_partial_remerge():
                    partials[merger.NAME] = set(merger.get_mod_affected(output_mod))
        for merger in mergers.sort_mergers(all_mergers):
            if merger.NAME in partials:
                merger.set_options({'only_these': partials[merger.NAME]})
            merger.set_pool(this_pool)
            merger.perform_merge()

    if this_pool and not pool:
        this_pool.close()
        this_pool.join()
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

    if not util.get_installed_mods():
        shutil.rmtree(util.get_master_modpack_dir())
        util.create_bcml_graphicpack_if_needed()
    else:
        if not wait_merge:
            for merger in mergers.sort_mergers(remergers):
                if merger.NAME in partials:
                    merger.set_options({'only_these': partials[merger.NAME]})
                merger.perform_merge()

    print(f'{mod.name} has been uninstalled.')


@refresher
def refresh_merges():
    print('Cleansing old merges...')
    shutil.rmtree(util.get_master_modpack_dir(), True)
    print('Refreshing merged mods...')
    set_start_method('spawn', True)
    with Pool(cpu_count()) as pool:
        for merger in mergers.sort_mergers(
                [merger_class() for merger_class in mergers.get_mergers()]
            ):
            merger.set_pool(pool)
            merger.perform_merge()


def create_backup(name: str = ''):
    if not name:
        name = f'BCML_Backup_{datetime.datetime.now().strftime("%Y-%m-%d")}'
    else:
        name = re.sub(r'(?u)[^-\w.]', '', name.strip().replace(' ', '_'))
    num_mods = len([d for d in util.get_modpack_dir().glob('*') if d.is_dir()])
    output = util.get_data_dir() / 'backups' / f'{name}---{num_mods - 1}.7z'
    output.parent.mkdir(parents=True, exist_ok=True)
    print(f'Saving backup {name}...')
    x_args = [ZPATH, 'a', str(output), f'{str(util.get_modpack_dir() / "*")}']
    if system() == 'Windows':
        subprocess.run(
            x_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=util.CREATE_NO_WINDOW,
            check=True
        )
    else:
        subprocess.run(x_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    print(f'Backup "{name}" created')


def get_backups() -> List[Path]:
    return list((util.get_data_dir() / 'backups').glob('*.7z'))


def restore_backup(backup: Union[str, Path]):
    if isinstance(backup, str):
        backup = Path(backup)
    if not backup.exists():
        raise FileNotFoundError(f'The backup "{backup.name}" does not exist.')
    print('Clearing installed mods...')
    for folder in [item for item in util.get_modpack_dir().glob('*') if item.is_dir()]:
        shutil.rmtree(str(folder))
    print('Extracting backup...')
    x_args = [ZPATH, 'x', str(backup), f'-o{str(util.get_modpack_dir())}']
    if system() == 'Windows':
        subprocess.run(
            x_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=util.CREATE_NO_WINDOW,
            check=True
        )
    else:
        subprocess.run(x_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    print('Re-enabling mods in Cemu...')
    refresh_master_export()
    print(f'Backup "{backup.name}" restored')


def link_master_mod(output: Path = None):
    util.create_bcml_graphicpack_if_needed()
    if not output:
        if util.get_settings('no_cemu'):
            return
        output = util.get_cemu_dir() / 'graphicPacks' / 'BreathOfTheWild_BCML'
    if output.exists():
        shutil.rmtree(str(output), ignore_errors=True)
    output.mkdir(parents=True, exist_ok=True)
    mod_folders: List[Path] = sorted(
        [item for item in util.get_modpack_dir().glob('*') if item.is_dir()],
        reverse=True
    )
    util.vprint(mod_folders)
    shutil.copy(
        str(util.get_master_modpack_dir() / 'rules.txt'),
        str(output / 'rules.txt')
    )
    link_or_copy = os.link
    for mod_folder in mod_folders:
        for item in mod_folder.rglob('**/*'):
            rel_path = item.relative_to(mod_folder)
            exists = (output / rel_path).exists()
            is_log = str(rel_path).startswith('logs')
            is_extra = len(rel_path.parts) == 1 and rel_path.suffix != '.txt' and not item.is_dir()
            if exists or is_log or is_extra:
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
                    from shutil import copyfile as link_or_copy # pylint: disable=import-outside-toplevel
                    link_or_copy(
                        str(item),
                        str(output / rel_path)
                    )


def export(output: Path):
    print('Loading files...')
    tmp_dir = util.get_work_dir() / 'tmp_export'
    if tmp_dir.drive != util.get_modpack_dir().drive:
        tmp_dir = Path(util.get_modpack_dir().drive) / 'tmp_bcml_export'
    link_master_mod(tmp_dir)
    print('Adding rules.txt...')
    rules_path = tmp_dir / 'rules.txt'
    mods = util.get_installed_mods()
    with rules_path.open('w', encoding='utf-8') as rules:
        rules.writelines([
            '[Definition]\n',
            'titleIds = 00050000101C9300,00050000101C9400,00050000101C9500\n',
            'name = Exported BCML Mod\n',
            'path = The Legend of Zelda: Breath of the Wild/Mods/Exported BCML\n',
            f'description = Exported merge of {", ".join([mod.name for mod in mods])}\n',
            'version = 4\n'
        ])
    if output.suffix == '.bnp' or output.name.endswith('.bnp.7z'):
        print('Exporting BNP...')
        dev.create_bnp_mod(
            mod=tmp_dir,
            meta={},
            output=output,
            options={'rstb':{'guess':True}}
        )
    else:
        print('Exporting as graphic pack mod...')
        x_args = [
            ZPATH,
            'a',
            str(output),
            f'{str(tmp_dir / "*")}'
        ]
        if os.name == 'nt':
            subprocess.run(
                x_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=util.CREATE_NO_WINDOW,
                check=True
            )
        else:
            subprocess.run(
                x_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True
            )
    rmtree(str(tmp_dir), True)
