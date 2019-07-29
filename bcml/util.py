import csv
import os
import re
import subprocess
import sys
import traceback
import unicodedata
from collections import Mapping, namedtuple
from configparser import ConfigParser
from pathlib import Path
from typing import Union

import byml
import sarc
import wszst_yaz0
import xxhash
import yaml
from byml import yaml_util

BcmlMod = namedtuple('BcmlMod', 'name priority path')
CREATE_NO_WINDOW = 0x08000000
SARC_EXTS = ['.sarc', '.pack', '.bactorpack', '.bmodelsh', '.beventpack', '.stera', '.stats', '.ssarc', '.spack',
             '.sbactorpack', '.sbmodelsh', '.sbeventpack', '.sstera', '.sstats', '.blarc', '.sblarc', '.genvb',
             '.sgenvb', '.bfarc', '.sbfarc']
AAMP_EXTS = ['.bxml', '.sbxml', '.bas', '.sbas', '.baglblm', '.sbaglblm', '.baglccr', '.sbaglccr', '.baglclwd',
             '.sbaglclwd', '.baglcube', '.sbaglcube', '.bagldof', '.sbagldof', '.baglenv', '.sbaglenv', '.baglenvset',
             '.sbaglenvset', '.baglfila', '.sbaglfila', '.bagllmap', '.sbagllmap', '.bagllref', '.sbagllref', '.baglmf',
             '.sbaglmf', '.baglshpp', '.sbaglshpp', '.baiprog', '.sbaiprog', '.baslist', '.sbaslist', '.bassetting',
             '.sbassetting', '.batcl', '.sbatcl', '.batcllist', '.sbatcllist', '.bawareness', '.sbawareness',
             '.bawntable', '.sbawntable', '.bbonectrl', '.sbbonectrl', '.bchemical', '.sbchemical', '.bchmres',
             '.sbchmres', '.bdemo', '.sbdemo', '.bdgnenv', '.sbdgnenv', '.bdmgparam', '.sbdmgparam', '.bdrop',
             '.sbdrop', '.bgapkginfo', '.sbgapkginfo', '.bgapkglist', '.sbgapkglist', '.bgenv', '.sbgenv', '.bglght',
             '.sbglght', '.bgmsconf', '.sbgmsconf', '.bgparamlist', '.sbgparamlist', '.bgsdw', '.sbgsdw', '.bksky',
             '.sbksky', '.blifecondition', '.sblifecondition', '.blod', '.sblod', '.bmodellist', '.sbmodellist',
             '.bmscdef', '.sbmscdef', '.bmscinfo', '.sbmscinfo', '.bnetfp', '.sbnetfp', '.bphyscharcon',
             '.sbphyscharcon', '.bphyscontact', '.sbphyscontact', '.bphysics', '.sbphysics', '.bphyslayer',
             '.sbphyslayer', '.bphysmaterial', '.sbphysmaterial', '.bphyssb', '.sbphyssb', '.bphyssubmat',
             '.sbphyssubmat', '.bptclconf', '.sbptclconf', '.brecipe', '.sbrecipe', '.brgbw', '.sbrgbw', '.brgcon',
             '.sbrgcon', '.brgconfig', '.sbrgconfig', '.brgconfiglist', '.sbrgconfiglist', '.bsfbt', '.sbsfbt', '.bsft',
             '.sbsft', '.bshop', '.sbshop', '.bumii', '.sbumii', '.bvege', '.sbvege', '.bactcapt', '.sbactcapt']
BYML_EXTS = ['.bgdata', '.sbgdata', '.bquestpack', '.sbquestpack', '.byml', '.sbyml', '.mubin', '.smubin',
             '.baischedule', '.sbaischedule', '.baniminfo', '.sbaniminfo', '.bgsvdata', '.sbgsvdata']


def get_exec_dir() -> Path:
    """ Gets the root BCML directory """
    return Path(os.path.dirname(os.path.realpath(__file__)))


def get_work_dir() -> Path:
    """ Gets the BCML internal working directory """
    work_dir = get_exec_dir() / 'work_dir'
    if not work_dir.exists():
        work_dir.mkdir(parents=True, exist_ok=True)
    return work_dir


def get_cemu_dir() -> Path:
    """ Gets the saved Cemu installation directory """
    if not hasattr(get_cemu_dir, 'cemu_dir'):
        cdir = get_work_dir() / '.cdir'
        if not cdir.exists():
            raise FileNotFoundError(
                'The Cemu directory has not been saved yet.')
        with cdir.open('r') as cf:
            get_cemu_dir.cemu_dir = Path(cf.read())
    return get_cemu_dir.cemu_dir


def set_cemu_dir(path: Path):
    """ Sets the saved Cemu installation directory """
    cdir = get_work_dir() / '.cdir'
    if cdir.exists():
        cdir.unlink()
    with cdir.open('w') as cf:
        cf.write(str(path.resolve()))
    get_cemu_dir.cemu_dir = path


def get_game_dir() -> Path:
    """ Gets the saved Breath of the Wild game directory """
    if not hasattr(get_game_dir, 'game_dir'):
        gdir = get_work_dir() / '.gdir'
        if not gdir.exists():
            raise FileNotFoundError(
                'The game directory has not been saved yet.')
        with gdir.open('r') as cf:
            get_game_dir.game_dir = Path(cf.read())
    return get_game_dir.game_dir


def set_game_dir(path: Path):
    """ Sets the saved Breath of the Wild game directory """
    gdir = get_work_dir() / '.gdir'
    if gdir.exists():
        gdir.unlink()
    with gdir.open('w') as cf:
        cf.write(str(path.resolve()))
    get_game_dir.game_dir = path
    try:
        get_mlc_dir()
    except FileNotFoundError:
        title_id = '00050000101C9400'
        with (path.parent / 'code' / 'app.xml').open('r') as af:
            for line in af:
                title_match = re.search(
                    r'<title_id type=\"hexBinary\" length=\"8\">([0-9A-F]{16})</title_id>', line)
                if title_match:
                    title_id = title_match.group(1)
                    break
        mlc_path = get_cemu_dir() / 'mlc01' / 'usr' / 'title' / \
            title_id[0:8] / title_id[8:]
        set_mlc_dir(mlc_path)


def get_mlc_dir() -> Path:
    """ Gets the saved Cemu mlc directory """
    if not hasattr(get_mlc_dir, 'mlc_dir'):
        mdir = get_work_dir() / '.mdir'
        if not mdir.exists():
            raise FileNotFoundError(
                'The mlc directory has not been saved yet.')
        with mdir.open('r') as cf:
            get_mlc_dir.mlc_dir = Path(cf.read())
    return get_mlc_dir.mlc_dir


def set_mlc_dir(path: Path):
    """ Sets the saved Cemu mlc directory """
    mdir = get_work_dir() / '.mdir'
    if mdir.exists():
        mdir.unlink()
    with mdir.open('w') as cf:
        cf.write(str(path.resolve()))
    get_mlc_dir.mlc_dir = path


def get_update_dir() -> Path:
    """ Gets the path to the game's update files in the Cemu mlc directory """
    return get_mlc_dir() / 'content'


def get_aoc_dir() -> Path:
    """ Gets the path to the game's aoc files in the Cemu mlc direcroy """
    return get_mlc_dir() / 'aoc' / 'content' / '0010'


def get_modpack_dir() -> Path:
    """ Gets the Cemu graphic pack directory for mods """
    return get_cemu_dir() / 'graphicPacks' / 'BCML'


def get_util_dirs() -> tuple:
    """
    Gets the primary directories BCML uses

    :returns: A tuple containing the root BCML directory, the BCML working
    directory, the Cemu installation directory, and the Cemu graphicPacks
    directory.
    :rtype: (:class:`pathlib.Path`, :class:`pathlib.Path`, :class:`pathlib.Path`, :class:`pathlib.Path`)
    """
    return get_exec_dir(), get_work_dir(), get_cemu_dir(), get_modpack_dir()


def get_botw_dirs() -> tuple:
    """
    Gets the directories the BotW game files

    :returns: A tuple containing the main BotW directory, the update directoy,
    and the aoc directory.
    :rtype: (:class:`pathlib.Path`, :class:`pathlib.Path`, :class:`pathlib.Path`)
    """
    return get_game_dir(), get_update_dir(), get_aoc_dir()


def get_bcml_version() -> str:
    with (get_exec_dir() / 'data' / 'version.txt').open('r') as sf:
        setup_text = sf.read()
    ver_match = re.search(r"version='([0-9]+\.[0-9]+)'", setup_text)
    return ver_match.group(1) + (' Beta' if 'Beta' in setup_text else '')

def get_game_file(path: Union[Path, str], aoc: bool = False) -> Path:
    """
    Gets the path to an original copy of a modded file from the game dump.

    :param path: The relative path to the modded file.
    :type path: Union[:class:`pathlib.Path`, str]
    :param aoc: Whether the file is part of add-on content (DLC)
    :type aoc: bool, optional
    """
    if str(path).startswith('content/') or str(path).startswith('content\\'):
        path = Path(str(path).replace('content/', '').replace('content\\', ''))
    if type(path) is str:
        path = Path(path)
    game_dir, update_dir, aoc_dir = get_botw_dirs()
    if 'aoc' in str(path) or aoc:
        path = Path(path.as_posix().replace('aoc/content/0010/', '').replace('aoc/0010/content/', '')
                    .replace('aoc/content/', '').replace('aoc/0010/', ''))
        return aoc_dir / path
    if (update_dir / path).exists():
        return update_dir / path
    else:
        if (game_dir / path).exists():
            return game_dir / path
        elif (aoc_dir / path).exists():
            return aoc_dir / path
        else:
            raise FileNotFoundError(
                f'File {str(path)} was not found in game dump.')


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
    with open(nests[0], 'rb') as sf:
        sarcs.append(sarc.read_file_and_make_sarc(sf))
    i = 1
    while i < len(nests) - 1:
        sarc_bytes = unyaz_if_needed(
            sarcs[i - 1].get_file_data(nests[i]).tobytes())
        sarcs.append(sarc.SARC(sarc_bytes))
        i += 1
    file_bytes = sarcs[-1].get_file_data(nests[-1]).tobytes()
    if file_bytes[0:4] == b'Yaz0' and unyaz:
        file_bytes = wszst_yaz0.decompress(file_bytes)
    del sarcs
    return file_bytes


def get_master_modpack_dir() -> Path:
    """ Gets the directory for the BCML master graphicpack """
    return get_modpack_dir() / '9999_BCML'


def get_hash_table() -> {}:
    """ Returns a dict containing an xxHash table for BotW game files """
    if not hasattr(get_hash_table, 'table'):
        get_hash_table.table = {}
        with (get_exec_dir() / 'data' / 'hashtable.csv').open('r') as hf:
            rows = csv.reader(hf)
            for row in rows:
                get_hash_table.table[row[0]] = row[1]
    return get_hash_table.table


def get_canon_name(file: str) -> str:
    """ Gets the canonical path of a game file taken from an extracted graphic pack """
    name = file.replace("\\", "/").replace('.s', '.')
    if 'aoc/' in name:
        return name.replace('aoc/content', 'aoc').replace('aoc', 'Aoc')
    elif 'content/' in name and '/aoc' not in name:
        return name.replace('content/', '')


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
    contents = file if type(file) is bytes else file.read_bytes()
    table = get_hash_table()
    if name not in table:
        return count_new
    fhash = xxhash.xxh32(contents).hexdigest()
    return not (fhash == table[name])


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
    mod_entry = unicodedata.normalize(
        'NFC', mod_list['entries'][entry].__str__())
    mod_entry = re.sub('[^0-9a-zA-Z]+', '', mod_entry)
    try:
        ref_entry = unicodedata.normalize(
            'NFC', ref_list['entries'][entry].__str__())
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
        with (data.with_name(data.stem + '.yml')).open('w') as yf:
            yaml.dump(yml_data.parse(), yf, Dumper=dumper,
                      allow_unicode=True, encoding='utf-8')
        data.unlink()


def yml_to_byml_dir(tmp_dir: Path, ext: str = '.byml'):
    """ Converts YAML files in given temp dir to BYML """
    loader = yaml.CSafeLoader
    yaml_util.add_constructors(loader)
    for yml in tmp_dir.rglob('**/*.yml'):
        with yml.open('r', encoding='utf-8') as yf:
            root = yaml.load(yf, loader)
        with (yml.with_name(yml.stem + ext)).open('wb') as bf:
            byml.Writer(root, True).write(bf)
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


def unyaz_if_needed(file_bytes: bytes) -> bytes:
    """
    Detects by file extension if a file should be decompressed, and decompresses if needed

    :param file_bytes: The bytes to potentially decompress.
    :type file_bytes: bytes
    :returns: Returns the bytes of the file, decompressed if necessary.
    :rtype: bytes
    """
    if file_bytes[0:4] == b'Yaz0':
        return wszst_yaz0.decompress(file_bytes)
    else:
        return file_bytes


def get_mod_info(rules_path: Path) -> BcmlMod:
    """ Gets the name and priority of a mod from its rules.txt """
    rules: ConfigParser = ConfigParser()
    rules.read(str(rules_path))
    return BcmlMod(str(rules['Definition']['name']).strip('" \''), int(rules['Definition']['fsPriority']),
                   rules_path.parent)


def get_installed_mods() -> []:
    """
    Gets all installed mods and their basic info

    :returns: A list of mods with their names, priorities, and installed paths.
    :rtype: list of (str, int, :class:`pathlib.Path`) )
    """
    mods = []
    for rules in get_modpack_dir().glob('*/rules.txt'):
        if rules.parent.stem == '9999_BCML':
            continue
        mod = get_mod_info(rules)
        mods.insert(mod.priority - 100, mod)
    return mods


def log_error():
    """ Writes the most recent error traceback to the error log and prints the traceback text """
    log_path = get_work_dir() / 'error.log'
    error_log = traceback.format_exc()
    with log_path.open('w') as lf:
        lf.write(error_log)
    print('BCML has encountered an error. The details are as follows:')
    print(error_log)
    print(f'The error information has been saved to:\n  {str(log_path)}')
    if sys.stdin.isatty():
        sys.exit(1)


def update_bcml():
    """ Updates BCML to the latest version """
    subprocess.call([sys.executable, '-m', 'pip',
                     'install', '--upgrade', 'bcml'])


def create_bcml_graphicpack_if_needed():
    bcml_mod_dir = get_master_modpack_dir()
    if not bcml_mod_dir.exists():
        bcml_mod_dir.mkdir(parents=True, exist_ok=True)
        rules = bcml_mod_dir / 'rules.txt'
        with rules.open('w') as rf:
            rf.write('[Definition]\n'
                     'titleIds = 00050000101C9300,00050000101C9400,00050000101C9500\n'
                     'name = BCML\n'
                     'path = The Legend of Zelda: Breath of the Wild/BCML Mods/Master BCML\n'
                     'description = Auto-generated pack which merges RSTB changes and packs for other mods\n'
                     'version = 4\n'
                     'fsPriority = 9999')


def dict_merge(dct: dict, merge_dct: dict):
    """ Recursive dict merge. Inspired by :meth:``dict.update()``, instead of
    updating only top-level keys, dict_merge recurses down into dicts nested
    to an arbitrary depth, updating keys. The ``merge_dct`` is merged into
    ``dct``.

    :param dct: dict onto which the merge is executed
    :param merge_dct: dct merged into dct
    :return: None
    """
    for k, v in merge_dct.items():
        if (k in dct and isinstance(dct[k], dict)
                and isinstance(merge_dct[k], Mapping)):
            dict_merge(dct[k], merge_dct[k])
        elif (k in dct and isinstance(dct[k], list)
                and isinstance(merge_dct[k], list)):
            dct[k].extend(merge_dct[k])
        else:
            dct[k] = merge_dct[k]
