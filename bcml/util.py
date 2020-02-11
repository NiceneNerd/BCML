"""Provides various utility functions for BCML operations"""
# Copyright 2019 Nicene Nerd <macadamiadaze@gmail.com>
# Licensed under GPLv3+
#import csv
import json
import os
import re
import shutil
import subprocess
import sys
import traceback
import unicodedata
import urllib.error
import urllib.request
from collections import namedtuple, OrderedDict
from collections.abc import Mapping
from configparser import ConfigParser
from pathlib import Path
from typing import Union
from PySide2.QtGui import QIcon, QPixmap

import byml
from byml import yaml_util
import sarc
import syaz0
import xxhash
import yaml

BcmlMod = namedtuple('BcmlMod', 'name priority path')
CREATE_NO_WINDOW = 0x08000000
SARC_EXTS = {'.sarc', '.pack', '.bactorpack', '.bmodelsh', '.beventpack', '.stera', '.stats',
             '.ssarc', '.spack', '.sbactorpack', '.sbmodelsh', '.sbeventpack', '.sstera', '.sstats'}
AAMP_EXTS = {'.bxml', '.sbxml', '.bas', '.sbas', '.baglblm', '.sbaglblm', '.baglccr', '.sbaglccr',
             '.baglclwd', '.sbaglclwd', '.baglcube', '.sbaglcube', '.bagldof', '.sbagldof',
             '.baglenv', '.sbaglenv', '.baglenvset', '.sbaglenvset', '.baglfila', '.sbaglfila',
             '.bagllmap', '.sbagllmap', '.bagllref', '.sbagllref', '.baglmf', '.sbaglmf',
             '.baglshpp', '.sbaglshpp', '.baiprog', '.sbaiprog', '.baslist', '.sbaslist',
             '.bassetting', '.sbassetting', '.batcl', '.sbatcl', '.batcllist', '.sbatcllist',
             '.bawareness', '.sbawareness', '.bawntable', '.sbawntable', '.bbonectrl',
             '.sbbonectrl', '.bchemical', '.sbchemical', '.bchmres', '.sbchmres', '.bdemo',
             '.sbdemo', '.bdgnenv', '.sbdgnenv', '.bdmgparam', '.sbdmgparam', '.bdrop', '.sbdrop',
             '.bgapkginfo', '.sbgapkginfo', '.bgapkglist', '.sbgapkglist', '.bgenv', '.sbgenv',
             '.bglght', '.sbglght', '.bgmsconf', '.sbgmsconf', '.bgparamlist', '.sbgparamlist',
             '.bgsdw', '.sbgsdw', '.bksky', '.sbksky', '.blifecondition', '.sblifecondition',
             '.blod', '.sblod', '.bmodellist', '.sbmodellist', '.bmscdef', '.sbmscdef', '.bmscinfo',
             '.sbmscinfo', '.bnetfp', '.sbnetfp', '.bphyscharcon', '.sbphyscharcon',
             '.bphyscontact', '.sbphyscontact', '.bphysics', '.sbphysics', '.bphyslayer',
             '.sbphyslayer', '.bphysmaterial', '.sbphysmaterial', '.bphyssb', '.sbphyssb',
             '.bphyssubmat', '.sbphyssubmat', '.bptclconf', '.sbptclconf', '.brecipe', '.sbrecipe',
             '.brgbw', '.sbrgbw', '.brgcon', '.sbrgcon', '.brgconfig', '.sbrgconfig',
             '.brgconfiglist', '.sbrgconfiglist', '.bsfbt', '.sbsfbt', '.bsft', '.sbsft', '.bshop',
             '.sbshop', '.bumii', '.sbumii', '.bvege', '.sbvege', '.bactcapt', '.sbactcapt'}
BYML_EXTS = {'.bgdata', '.sbgdata', '.bquestpack', '.sbquestpack', '.byml', '.sbyml', '.mubin',
             '.smubin', '.baischedule', '.sbaischedule', '.baniminfo', '.sbaniminfo', '.bgsvdata',
             '.sbgsvdata'}


decompress = syaz0.decompress
compress = syaz0.compress


def get_exec_dir() -> Path:
    """ Gets the root BCML directory """
    return Path(os.path.dirname(os.path.realpath(__file__)))


def get_data_dir() -> Path:
    """ Gets BCML's local app data directory """
    data_dir = Path(os.path.expandvars('%LOCALAPPDATA%')) / 'bcml'
    if not data_dir.exists():
        data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_work_dir() -> Path:
    """ Gets the BCML internal working directory """
    work_dir = get_data_dir() / 'work_dir'
    if not work_dir.exists():
        work_dir.mkdir(parents=True, exist_ok=True)
    return work_dir


def clear_temp_dir():
    """Empties BCML's temp directories"""
    for path in get_work_dir().glob('tmp*'):
        try:
            if path.is_dir():
                shutil.rmtree(str(path))
            elif path.is_file():
                path.unlink()
        except OSError:
            pass


def get_icon(name: str) -> QIcon:
    """ Gets the specified BCML tool icon """
    icon = QIcon()
    icon.addPixmap(QPixmap(str(get_exec_dir() / 'data' / f'{name}')))
    return icon


def get_settings() -> {}:
    """ Gets the BCML settings as a dict """
    if not hasattr(get_settings, 'settings_file'):
        settings = ConfigParser()
        settings_path = get_data_dir() / 'settings.ini'
        if not settings_path.exists():
            settings['Settings'] = {
                'cemu_dir': '',
                'game_dir': '',
                'load_reverse': False,
                'mlc_dir': '',
                'site_meta': '',
                'dark_theme': False,
                'guess_merge': True,
                'lang': ''
            }
            with settings_path.open('w', encoding='utf-8') as s_file:
                settings.write(s_file)
        else:
            settings.read(str(settings_path))
        get_settings.settings_file = settings
    return get_settings.settings_file['Settings']


def get_settings_bool(setting: str) -> bool:
    """Gets the value of a boolean setting"""
    if not setting in get_settings():
        return False
    return get_settings()[setting] == 'True'


def set_settings_bool(setting: str, value: bool):
    """Sets the value of a boolean setting"""
    get_settings.settings_file['Settings'][setting] = str(value)
    save_settings()


def save_settings():
    """Saves changes made to settings"""
    with (get_data_dir() / 'settings.ini').open('w', encoding='utf-8') as s_file:
        get_settings.settings_file.write(s_file)


def get_cemu_dir() -> Path:
    """ Gets the saved Cemu installation directory """
    cemu_dir = str(get_settings()['cemu_dir'])
    if not cemu_dir or not Path(cemu_dir).is_dir():
        err = FileNotFoundError('The Cemu directory has moved or not been saved yet.')
        err.error_text = 'The Cemu directory has moved or not been saved yet.'
        raise err
    return Path(cemu_dir)


def set_cemu_dir(path: Path):
    """ Sets the saved Cemu installation directory """
    settings = get_settings()
    settings['cemu_dir'] = str(path.resolve())
    save_settings()


def get_game_dir() -> Path:
    """ Gets the saved Breath of the Wild game directory """
    game_dir = str(get_settings()['game_dir'])
    if not game_dir or not Path(game_dir).is_dir():
        err = FileNotFoundError('The BotW game directory has has moved or not been saved yet.')
        err.error_text = 'The BotW game directory has has moved or not been saved yet.'
        raise err
    else:
        return Path(game_dir)


def set_game_dir(path: Path):
    """ Sets the saved Breath of the Wild game directory """
    settings = get_settings()
    settings['game_dir'] = str(path.resolve())
    save_settings()
    try:
        get_mlc_dir()
    except FileNotFoundError:
        try:
            from xml.dom import minidom
            set_path = get_cemu_dir() / 'settings.xml'
            if not set_path.exists():
                err = FileNotFoundError('The Cemu settings file could not be found.')
                err.error_text = 'The Cemu settings file could not be found. This usually means your Cemu directory '\
                                 'is set incorrectly.'
                raise err
            set_read = ''
            with set_path.open('r') as setfile:
                for line in setfile:
                    set_read += line.strip()
            settings = minidom.parseString(set_read)
            mlc_path = Path(settings.getElementsByTagName('mlc_path')[0].firstChild.nodeValue)
        except (FileNotFoundError, IndexError, ValueError, AttributeError):
            mlc_path = get_cemu_dir() / 'mlc01'
        if mlc_path.exists():
            set_mlc_dir(mlc_path)
        else:
            raise FileNotFoundError('The MLC directory could not be automatically located.')


def get_mlc_dir() -> Path:
    """ Gets the saved Cemu mlc directory """
    mlc_dir = str(get_settings()['mlc_dir'])
    if not mlc_dir or not Path(mlc_dir).is_dir():
        err = FileNotFoundError('The Cemu MLC directory has moved or not been saved yet.')
        err.error_text = 'The Cemu MLC directory has moved or not been saved yet.'
        raise err
    return Path(mlc_dir)


def set_mlc_dir(path: Path):
    """ Sets the saved Cemu mlc directory """
    settings = get_settings()
    settings['mlc_dir'] = str(path.resolve())
    save_settings()
    if hasattr(get_update_dir, 'update_dir'):
        del get_update_dir.update_dir
    if hasattr(get_aoc_dir, 'aoc_dir'):
        del get_aoc_dir.aoc_dir


def set_site_meta(site_meta):
    """ Caches site meta from url's specified in mods rules.txt """
    settings = get_settings()
    if not 'site_meta' in settings:
        settings['site_meta'] = ''
    else:
        settings['site_meta'] = str(settings['site_meta'] + f'{site_meta};')
    save_settings()


def get_title_id() -> (str, str):
    """Gets the title ID of the BotW game dump"""
    if not hasattr(get_title_id, 'title_id'):
        title_id = '00050000101C9400'
        with (get_game_dir().parent / 'code' / 'app.xml').open('r') as a_file:
            for line in a_file:
                title_match = re.search(
                    r'<title_id type=\"hexBinary\" length=\"8\">([0-9A-F]{16})</title_id>', line)
                if title_match:
                    title_id = title_match.group(1)
                    break
        get_title_id.title_id = (title_id[0:7] + '0', title_id[8:])
    return get_title_id.title_id


def get_update_dir() -> Path:
    """ Gets the path to the game's update files in the Cemu mlc directory """
    if not hasattr(get_update_dir, 'update_dir'):
        title_id = get_title_id()
        # First try the 1.15.11c mlc layout
        if (get_mlc_dir() / 'usr' / 'title' / f'{title_id[0][0:7]}E' / title_id[1] / 'content')\
            .exists():
            get_update_dir.update_dir = get_mlc_dir() / 'usr' / 'title' / \
                f'{title_id[0][0:7]}E' / title_id[1] / 'content'
        # Then try the legacy layout
        elif (get_mlc_dir() / 'usr' / 'title' / title_id[0] / title_id[1] / 'content').exists():
            get_update_dir.update_dir = get_mlc_dir() / 'usr' / 'title' / \
                title_id[0] / title_id[1] / 'content'
        else:
            err = FileNotFoundError('The Cemu update directory could not be found.')
            err.error_text = ('The Cemu update directory could not be found. Usually, the correct location is somewhere '
                              'in Cemu\'s MLC folder. This probably means that the MLC folder has not been correctly '
                              'located, or that you have not installed the update files in Cemu.')
            raise err
    return get_update_dir.update_dir


def get_aoc_dir() -> Path:
    """ Gets the path to the game's aoc files in the Cemu mlc direcroy """
    if not hasattr(get_aoc_dir, 'aoc_dir'):
        title_id = get_title_id()
        mlc_title = get_mlc_dir() / 'usr' / 'title'
        # First try the 1.15.11c mlc layout
        if (mlc_title / f'{title_id[0][0:7]}C' / title_id[1] / 'content' / '0010').exists():
            get_aoc_dir.aoc_dir = get_mlc_dir() / 'usr' / 'title' / \
                f'{title_id[0][0:7]}C' / title_id[1] / 'content' / '0010'
        # Then try the legacy layout
        elif (mlc_title / title_id[0] / title_id[1] / 'aoc' / 'content' / '0010').exists():
            get_aoc_dir.aoc_dir = get_mlc_dir() / 'usr' / 'title' / \
                title_id[0] / title_id[1] / 'aoc' / 'content' / '0010'
        else:
            err = FileNotFoundError('The Cemu aoc directory could not be found.')
            err.error_text = ('The Cemu aoc directory could not be found. Usually, the correct location is somewhere '
                              'in Cemu\'s MLC folder. This probably means that the MLC folder has not been correctly '
                              'located, or that you have not installed the DLC files in Cemu.')
            raise err
    return get_aoc_dir.aoc_dir


def get_modpack_dir() -> Path:
    """ Gets the Cemu graphic pack directory for mods """
    if 'Beta' not in get_bcml_version():
        return get_cemu_dir() / 'graphicPacks' / 'BCML'
    else:
        return get_cemu_dir() / 'graphicPacks' / 'BCML_beta'


def get_util_dirs() -> tuple:
    """
    Gets the primary directories BCML uses

    :returns: A tuple containing the root BCML directory, the BCML working
    directory, the Cemu installation directory, and the Cemu graphicPacks
    directory.
    :rtype: (class:`pathlib.Path`, class:`pathlib.Path`, class:`pathlib.Path`,
            class:`pathlib.Path`)
    """
    return get_exec_dir(), get_work_dir(), get_cemu_dir(), get_modpack_dir()


def get_botw_dirs() -> tuple:
    """
    Gets the directories the BotW game files

    :returns: A tuple containing the main BotW directory, the update directoy,
    and the aoc directory.
    :rtype: (class:`pathlib.Path`, class:`pathlib.Path`, class:`pathlib.Path`)
    """
    return get_game_dir(), get_update_dir(), get_aoc_dir()


def get_bcml_version() -> str:
    """Gets the version string for the installed copy of BCML"""
    from .__version__ import VERSION
    return VERSION + (' Beta' if 'b' in VERSION else '')


def get_game_file(path: Union[Path, str], aoc: bool = False) -> Path:
    """
    Gets the path to an original copy of a modded file from the game dump.

    :param path: The relative path to the modded file.
    :type path: Union[class:`pathlib.Path`, str]
    :param aoc: Whether the file is part of add-on content (DLC)
    :type aoc: bool, optional
    """
    if str(path).startswith('content/') or str(path).startswith('content\\'):
        path = Path(str(path).replace('content/', '').replace('content\\', ''))
    if isinstance(path, str):
        path = Path(path)
    game_dir = get_game_dir()
    update_dir = get_update_dir()
    try:
        aoc_dir = get_aoc_dir()
    except FileNotFoundError:
        aoc_dir = None
    if 'aoc' in str(path) or aoc:
        if aoc_dir:
            path = Path(
                path.as_posix().replace('aoc/content/0010/', '').replace('aoc/0010/content/', '')
                .replace('aoc/content/', '').replace('aoc/0010/', '')
            )
            if (aoc_dir / path).exists():
                return aoc_dir / path
            raise FileNotFoundError(f'{path} not found in DLC files.')
        else:
            raise FileNotFoundError(f'{path} is a DLC file, but the DLC directory is missing.')
    if (update_dir / path).exists():
        return update_dir / path
    if (game_dir / path).exists():
        return game_dir / path
    elif aoc_dir and (aoc_dir / path).exists():
        return aoc_dir / path
    else:
        raise FileNotFoundError(f'File {str(path)} was not found in game dump.')


def get_nested_file_bytes(file: str, unyaz: bool = True) -> bytes:
    """
    Get the contents of a file nested inside one or more SARCs

    :param file: A string containing the nested SARC path to the file
    :type file: str
    :param unyaz: Whether to decompress the file if yaz0 compressed, defaults to True
    :type unyaz: bool, optional
    :return: Returns the bytes to the file
    :rtype: bytes
    """
    nests = file.split('//')
    sarcs = []
    with open(nests[0], 'rb') as s_file:
        sarcs.append(sarc.read_file_and_make_sarc(s_file))
    i = 1
    while i < len(nests) - 1:
        sarc_bytes = unyaz_if_needed(
            sarcs[i - 1].get_file_data(nests[i]).tobytes())
        sarcs.append(sarc.SARC(sarc_bytes))
        i += 1
    file_bytes = sarcs[-1].get_file_data(nests[-1]).tobytes()
    if file_bytes[0:4] == b'Yaz0' and unyaz:
        file_bytes = decompress(file_bytes)
    del sarcs
    return file_bytes


def get_master_modpack_dir() -> Path:
    """ Gets the directory for the BCML master graphicpack """
    master = get_modpack_dir() / '9999_BCML'
    if not (master / 'rules.txt').exists():
        create_bcml_graphicpack_if_needed()
    return master


def get_hash_table() -> {}:
    """ Returns a dict containing an xxHash table for BotW game files """
    if not hasattr(get_hash_table, 'table'):
        with (get_exec_dir() / 'data' / 'hashtable.json').open('r') as h_file:
            get_hash_table.table = json.load(h_file)
    return get_hash_table.table


def get_canon_name(file: str, allow_no_source: bool = False) -> str:
    """ Gets the canonical path of a game file taken from an extracted graphic pack """
    name = str(file).replace("\\", "/").replace('.s', '.')\
        .replace('Content', 'content').replace('Aoc', 'aoc')
    if 'aoc/' in name:
        return name.replace('aoc/content', 'aoc').replace('aoc', 'Aoc')
    elif 'content/' in name and '/aoc' not in name:
        return name.replace('content/', '')
    elif allow_no_source:
        return name


def get_mod_id(mod_name: str, priority: int) -> str:
    """ Gets the ID for a mod from its name and priority """
    return f'{priority:04}_' + re.sub(r'(?u)[^-\w.]', '', mod_name.strip().replace(' ', ''))


def get_mod_by_priority(priority: int) -> Union[Path, bool]:
    """ Gets the path to the modpack installed with a given priority, or False if there is none """
    try:
        return list(get_modpack_dir().glob(f'{priority:04}*'))[0]
    except IndexError:
        return False


def is_pack_mod(mod: Union[Path, BcmlMod, str]) -> bool:
    """ Checks whether a mod affects pack merging """
    path = mod.path if isinstance(mod, BcmlMod) else Path(
        mod) if isinstance(mod, str) else mod
    return (path / 'logs' / 'packs.log').exists()


def is_gamedata_mod(mod: Union[Path, BcmlMod, str]) -> bool:
    """ Checks whether a mod affects game data merging """
    path = mod.path if isinstance(mod, BcmlMod) else Path(
        mod) if isinstance(mod, str) else mod
    return (path / 'logs' / 'gamedata.yml').exists()


def is_savedata_mod(mod: Union[Path, BcmlMod, str]) -> bool:
    """ Checks whether a mod affects save data merging """
    path = mod.path if isinstance(mod, BcmlMod) else Path(
        mod) if isinstance(mod, str) else mod
    return (path / 'logs' / 'savedata.yml').exists()


def is_actorinfo_mod(mod: Union[Path, BcmlMod, str]) -> bool:
    """ Checks whether a mod affects actor info merging """
    path = mod.path if isinstance(mod, BcmlMod) else Path(
        mod) if isinstance(mod, str) else mod
    return (path / 'logs' / 'actorinfo.yml').exists()


def is_eventinfo_mod(mod: Union[Path, BcmlMod, str]) -> bool:
    """ Checks whether a mod affects event info merging """
    path = mod.path if isinstance(mod, BcmlMod) else Path(
        mod) if isinstance(mod, str) else mod
    return (path / 'logs' / 'eventinfo.yml').exists()


def is_map_mod(mod: Union[Path, BcmlMod, str]) -> bool:
    """ Checks whether a mod affects map merging """
    path = mod.path if isinstance(mod, BcmlMod) else Path(
        mod) if isinstance(mod, str) else mod
    return (path / 'logs' / 'map.yml').exists()


def is_deepmerge_mod(mod: Union[Path, BcmlMod, str]) -> bool:
    """ Checks whether a mod affects deep merging """
    path = mod.path if isinstance(mod, BcmlMod) else Path(
        mod) if isinstance(mod, str) else mod
    return (path / 'logs' / 'deepmerge.yml').exists()


def get_file_language(file: Union[Path, str]) -> str:
    """ Extracts the game language of a file from its name """
    if isinstance(file, Path):
        file = str(file)
    lang_match = re.search(r'_([A-Z]{2}[a-z]{2})', file)
    return lang_match.group(1)


def is_file_modded(name: str, file: Union[bytes, Path], count_new: bool = True) -> bool:
    """
    Determines if a game file has been modified by checking the hash

    :param name: Canonical path to the file being checked.
    :type name: str
    :param file: Bytes representing the file contents.
    :type file: Union[bytes, Path]
    :param count_new: Whether to count new files as modded, defaults to False
    :type count_new: bool, optional
    :returns: True if the file hash differs from the entry in the table or
    if the entry does not exist, false if it matches the table entry.
    :rtype: bool
    """
    contents = file if isinstance(file, bytes) else \
        file.read_bytes() if isinstance(file, Path) else file.tobytes()
    table = get_hash_table()
    if name not in table:
        return count_new
    fhash = xxhash.xxh32(contents).hexdigest()
    return not fhash in table[name]


def is_yaml_modded(entry, ref_list: dict, mod_list: dict) -> bool:
    """
    Determines if a YAML object has been modified from the original

    :param entry: The key of the YAML entry to compare.
    :type entry: str
    :param ref_list: The reference YAML dictionary.
    :type ref_list: dict
    :param mod_list: The modded YAML dictionary.
    :type mod_list: dict
    :returns: True if the normalized entry contents differs from the entry
    in the reference document or if the entry does not exist, false if it
    matches the reference entry.
    :rtype: bool
    """
    mod_entry = unicodedata.normalize('NFC', mod_list['entries'][entry].__str__())
    mod_entry = re.sub('[^0-9a-zA-Z]+', '', mod_entry)
    try:
        ref_entry = unicodedata.normalize('NFC', ref_list['entries'][entry].__str__())
        ref_entry = re.sub('[^0-9a-zA-Z]+', '', ref_entry)
    except KeyError:
        return True
    if not ref_entry == mod_entry:
        return True
    return False


def byml_to_yml_dir(tmp_dir: Path, ext: str = '.byml'):
    """ Converts BYML files in given temp dir to YAML """
    dumper = yaml.CDumper
    yaml_util.add_representers(dumper)
    for data in tmp_dir.rglob(f'**/*{ext}'):
        yml_data = byml.Byml(data.read_bytes())
        with (data.with_name(data.stem + '.yml')).open('w', encoding='utf-8') as y_file:
            yaml.dump(yml_data.parse(), y_file, Dumper=dumper,
                      allow_unicode=True, encoding='utf-8')
        data.unlink()


def yml_to_byml_dir(tmp_dir: Path, ext: str = '.byml'):
    """ Converts YAML files in given temp dir to BYML """
    loader = yaml.CSafeLoader
    yaml_util.add_constructors(loader)
    for yml in tmp_dir.rglob('**/*.yml'):
        with yml.open('r', encoding='utf-8') as y_file:
            root = yaml.load(y_file, loader)
        with (yml.with_name(yml.stem + ext)).open('wb') as b_file:
            byml.Writer(root, True).write(b_file)
        yml.unlink()


def is_file_sarc(path: str) -> bool:
    """ Checks the file extension of a game file to tell if it is a SARC """
    ext = os.path.splitext(str(path))[1]
    return ext in SARC_EXTS


def is_file_aamp(path: str) -> bool:
    """ Checks the file extension of a game file to tell if it is an AAMP file """
    ext = os.path.splitext(str(path))[1]
    return ext in AAMP_EXTS


def is_file_byml(path: str) -> bool:
    """ Checks the file extension of a game file to tell if it is a BYML file """
    ext = os.path.splitext(str(path))[1]
    return ext in BYML_EXTS


def decompress_file(file) -> bytes:
    if isinstance(file, str):
        file = Path(file)
    return decompress(file.read_bytes())


def unyaz_if_needed(file_bytes: bytes) -> bytes:
    """
    Detects by file extension if a file should be decompressed, and decompresses if needed

    :param file_bytes: The bytes to potentially decompress.
    :type file_bytes: bytes
    :returns: Returns the bytes of the file, decompressed if necessary.
    :rtype: bytes
    """
    if file_bytes[0:4] == b'Yaz0':
        return decompress(file_bytes)
    else:
        return file_bytes


def inject_file_into_bootup(file: str, data: bytes, create_bootup: bool = False):
    """
    Injects a file into the master BCML `Bootup.pack`

    :param file: The path of the file to inject
    :type file: str
    :param data: The bytes of the file to inject
    :type data: bytes
    :param create_bootup: Whether to create `Bootup.pack` if it does not exist, defaults to False
    :type create_bootup: bool, optional
    """
    bootup_path = get_master_modpack_dir() / 'content' / 'Pack' / 'Bootup.pack'
    if bootup_path.exists() or create_bootup:
        if not bootup_path.exists():
            bootup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(get_game_file('Pack/Bootup.pack'), bootup_path)
        with bootup_path.open('rb') as b_file:
            old_bootup = sarc.read_file_and_make_sarc(b_file)
            new_bootup = sarc.make_writer_from_sarc(old_bootup)
        if file in old_bootup.list_files():
            new_bootup.delete_file(file)
        new_bootup.add_file(file, data)
        bootup_path.write_bytes(new_bootup.get_bytes())
    else:
        raise FileNotFoundError('Bootup.pack is not present in the master BCML mod')


def get_mod_info(rules_path: Path) -> BcmlMod:
    """ Gets the name and priority of a mod from its rules.txt """
    rules: ConfigParser = RulesParser()
    rules.read(str(rules_path))
    name = str(rules['Definition']['name']).strip('" \'').replace('_', ' ')
    try:
        priority = int(rules['Definition']['fsPriority'])
    except KeyError:
        error = KeyError(
            f'Mod "{name}" contains no priority field. It may not have been installed completely.'
        )
        error.path = rules_path.parent
        raise error
    return BcmlMod(
        name,
        priority,
        rules_path.parent
    )


def get_mod_preview(mod: BcmlMod, rules: ConfigParser = None) -> QPixmap:
    """
    Gets the preview image of a given mod, if any, and caches it

    :param mod: The mod to preview
    :type mod: class:`bcml.util.BcmlMod`
    :param rules: The contents of the mod's `rules.txt` file
    :type rules: ConfigParser
    :return: Returns the preview image for the mod as QPixmap
    :rtype: QPixmap
    """
    if not rules:
        rules = RulesParser()
        rules.read(str(mod.path / 'rules.txt'))
    if 'url' in rules['Definition']:
        url = str(rules['Definition']['url'])
    if not list(mod.path.glob('thumbnail.*')):
        if 'image' not in rules['Definition']:
            if 'url' in rules['Definition'] and 'gamebanana.com' in url:
                response = urllib.request.urlopen(url)
                rdata = response.read().decode()
                img_match = re.search(
                    r'<meta property=\"og:image\" ?content=\"(.+?)\" />', rdata)
                if img_match:
                    image_path = 'thumbnail.jfif'
                    urllib.request.urlretrieve(
                        img_match.group(1),
                        str(mod.path / image_path)
                    )
                else:
                    raise IndexError(f'Rule for {url} failed to find the remote preview')
            else:
                raise KeyError(f'No preview image available')
        else:
            image_path = str(rules['Definition']['image'])
            if image_path.startswith('http'):
                urllib.request.urlretrieve(
                    image_path,
                    str(mod.path / ('thumbnail.' + image_path.split(".")[-1]))
                )
                image_path = 'thumbnail.' + image_path.split(".")[-1]
            if not os.path.isfile(str(mod.path / image_path)):
                raise FileNotFoundError(
                    f'Preview {image_path} specified in rules.txt not found')
    else:
        for thumb in mod.path.glob('thumbnail.*'):
            image_path = thumb
    return QPixmap(str(mod.path / image_path))


def get_mod_link_meta(rules: ConfigParser = None):
    """
    Gets the link metadata for the URL field of a mod

    :param rules: The contents of the mod's `rules.txt` file
    :type rules: ConfigParser
    :return: Returns an HTML link to the mod webpage
    :rtype: str
    """
    url = str(rules['Definition']['url'])
    mod_domain = ''
    if 'www.' in url:
        mod_domain = url.split('.')[1]
    elif 'http' in url:
        mod_domain = url.split('//')[1].split('.')[0]
    site_name = mod_domain.capitalize()
    fetch_site_meta = True
    if 'site_meta' not in get_settings():
        set_site_meta('')
    if len(get_settings()['site_meta'].split(';')) > 1:
        for site_meta in get_settings()['site_meta'].split(';'):
            if site_meta.split(':')[0] == mod_domain:
                fetch_site_meta = False
                site_name = site_meta.split(':')[1]
    if fetch_site_meta:
        try:
            response = urllib.request.urlopen(url)
            rdata = response.read().decode()
            name_match = re.search(
                r'property=\"og\:site_name\"[^\/\>]'
                r'*content\=\"(.+?)\"|content\=\"(.+?)\"[^\/\>]'
                r'*property=\"og\:site_name\"',
                rdata
            )
            if name_match:
                for group in name_match.groups():
                    if group is not None:
                        set_site_meta(f'{mod_domain}:{group}')
                        site_name = str(group)
            img_match = re.search(
                r'<link.*rel=\"(shortcut icon|icon)\".*href=\"(.+?)\".*>', rdata)
            if img_match:
                (get_exec_dir() / 'work_dir' / 'cache' / 'site_meta').mkdir(
                    parents=True,
                    exist_ok=True
                )
                try:
                    urllib.request.urlretrieve(
                        img_match.group(2),
                        str(get_exec_dir() / 'work_dir' / 'cache' / "site_meta" /\
                            f'fav_{site_name}.{img_match.group(2).split(".")[-1]}')
                    )
                except (urllib.error.URLError,
                        urllib.error.HTTPError,
                        urllib.error.ContentTooShortError):
                    pass
        except (urllib.error.URLError,
                urllib.error.HTTPError,
                urllib.error.ContentTooShortError):
            pass
    favicon = ''
    for file in (get_exec_dir() / "work_dir" / "cache" / "site_meta")\
                .glob(f'fav_{site_name}.*'):
        favicon = f'<img src="{file.resolve()}" height="16"/> '
    return f'<b>Link: <a style="text-decoration: none;" href="{url}">{favicon} {site_name}</a></b>'


def get_installed_mods(disabled: bool = False) -> []:
    """
    Gets all installed mods and their basic info

    :param disabled: Whether to include disabled mods, defaults to False
    :type disabled: bool, optional
    :returns: A list of mods with their names, priorities, and installed paths.
    :rtype: list of (str, int, class:`pathlib.Path`) )
    """
    mods = []
    for rules in get_modpack_dir().glob('*/rules.txt*'):
        if rules.parent.stem == '9999_BCML' or (not disabled and rules.suffix == '.disable'):
            continue
        try:
            mod = get_mod_info(rules)
        except KeyError as priority_error:
            rules.unlink()
            shutil.rmtree(str(priority_error.path), ignore_errors=True)
            continue
        mods.insert(mod.priority - 100, mod)
    return mods


def is_mod_disabled(mod: BcmlMod) -> bool:
    return (mod.path / 'rules.txt.disable').exists()


def get_all_modded_files(only_loose: bool = False) -> dict:
    """
    Gets all installed file modifications and the highest priority of each

    :return: A dict of canonical paths and the priority of the highest modded version
    :rtype: dict of str: int
    """
    modded_files = {}
    for mod in get_installed_mods():
        with (mod.path / 'logs' / 'rstb.log').open('r') as l_file:
            csv_loop = csv.reader(l_file)
            for row in csv_loop:
                if row[0] == 'name' or (only_loose and '//' in row[2]):
                    continue
                modded_files[row[0]] = mod.priority
    return modded_files


def log_error():
    """ Writes the most recent error traceback to the error log and prints the traceback text """
    log_path = get_work_dir() / 'error.log'
    error_log = traceback.format_exc()
    with log_path.open('w', encoding='utf-8') as l_file:
        l_file.write(error_log)
    print('BCML has encountered an error. The details are as follows:')
    print(error_log)
    print(f'The error information has been saved to:\n  {str(log_path)}')
    if sys.stdin.isatty():
        sys.exit(1)


def update_bcml():
    """ Updates BCML to the latest version """
    subprocess.call([sys.executable, '-m', 'pip', 'install', '--upgrade', 'bcml'])


def create_bcml_graphicpack_if_needed():
    """Creates the BCML master modpack if it doesn't exist"""
    bcml_mod_dir = get_modpack_dir() / '9999_BCML'
    (bcml_mod_dir / 'logs').mkdir(parents=True, exist_ok=True)
    rules = bcml_mod_dir / 'rules.txt'
    if not rules.exists():
        with rules.open('w', encoding='utf-8') as r_file:
            r_file.write('[Definition]\n'
                         'titleIds = 00050000101C9300,00050000101C9400,00050000101C9500\n'
                         'name = BCML\n'
                         'path = {BCML: DON\'T TOUCH}/Master BCML\n'
                         'description = Auto-generated pack which merges RSTB changes and packs '
                         'for other mods\n'
                         'version = 4\n'
                         'fsPriority = 9999')


def dict_merge(dct: dict, merge_dct: dict, overwrite_lists: bool = False):
    """ Recursive dict merge. Inspired by :meth:``dict.update()``, instead of
    updating only top-level keys, dict_merge recurses down into dicts nested
    to an arbitrary depth, updating keys. The ``merge_dct`` is merged into
    ``dct``.

    :param dct: dict onto which the merge is executed
    :param merge_dct: dct merged into dct
    :param overwrite_lists: Whether to prevent duplicate items in lists, defaults to False
    :return: None
    """
    for k in merge_dct:
        if (k in dct and isinstance(dct[k], dict)
                and isinstance(merge_dct[k], Mapping)):
            dict_merge(dct[k], merge_dct[k])
        elif (k in dct and isinstance(dct[k], list)
              and isinstance(merge_dct[k], list)):
            if overwrite_lists:
                dct[k] = merge_dct[k]
            else:
                dct[k].extend(merge_dct[k])
        else:
            dct[k] = merge_dct[k]


def create_schema_handler():
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r'Software\Classes\bcml') as key:
        try:
            winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Classes\bcml\shell\open\command',
                           0, winreg.KEY_READ)
        except (WindowsError, OSError):
            winreg.SetValueEx(key, 'URL Protocol', 0, winreg.REG_SZ, '')
            with winreg.CreateKey(key, r'shell\open\command') as key2:
                if (Path(os.__file__).parent.parent / 'Scripts' / 'bcml.exe').exists():
                    exec_path = Path(os.__file__).parent.parent / 'Scripts' / 'bcml.exe'
                elif (Path(__file__).parent.parent.parent / 'bin' / 'bcml.exe'):
                    exec_path = (Path(__file__).parent.parent.parent / 'bin' / 'bcml.exe')
                else:
                    return
                winreg.SetValueEx(key2, '', 0, winreg.REG_SZ, f'"{exec_path.resolve()}" "%1"')


class RulesParser(ConfigParser):
    def __init__(self):
        ConfigParser.__init__(self, dict_type=MultiDict)

    def write(self, fileobject):
        from io import StringIO
        buf = StringIO()
        ConfigParser.write(self, buf)
        config_str = re.sub(r'\[Preset[0-9]+\]', '[Preset]', buf.getvalue())
        fileobject.write(config_str)


class MultiDict(OrderedDict):
    _unique = 0

    def __setitem__(self, key, val):
        if isinstance(val, dict) and key == 'Preset':
            self._unique += 1
            key += str(self._unique)
        OrderedDict.__setitem__(self, key, val)