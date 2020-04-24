"""Provides functions for diffing and merging BotW game text files"""
# Copyright 2020 Nicene Nerd <macadamiadaze@gmail.com>
# Licensed under GPLv3+
import copy
import csv
import io
import json
import multiprocessing
import shutil
import subprocess
from functools import partial
from os.path import abspath
from pathlib import Path
from platform import system
from typing import List, Union

import oead
import rstb
import rstb.util
import xxhash

from bcml import mergers, util
from bcml.mergers import rstable
from bcml.util import BcmlMod

EXCLUDE_TEXTS = [
    'ErrorMessage',
    'StaffRoll',
    'LayoutMsg/MessageTipsRunTime_00.msbt',
    'LayoutMsg/OptionWindow_00.msbt',
    'LayoutMsg/SystemWindow_00.msbt'
]

LANGUAGES = [
    'USen',
    'EUen',
    'USfr',
    'USes',
    'EUde',
    'EUes',
    'EUfr',
    'EUit',
    'EUnl',
    'EUru',
    'CNzh',
    'JPja',
    'KRko',
    'TWzh'
]

MSYT_PATH = str(util.get_exec_dir() / 'helpers' / 'msyt{}'.format(
    '.exe' if system() == 'Windows' else ''
))


def get_user_languages() -> set:
    langs = set()
    for file in (util.get_update_dir() / 'Pack').glob('Bootup_????.pack'):
        langs.add(util.get_file_language(file.name))
    return langs


def get_msbt_hashes(lang: str = 'USen') -> {}:
    if not hasattr(get_msbt_hashes, 'texthashes'):
        get_msbt_hashes.texthashes = {}
    if lang not in get_msbt_hashes.texthashes:
        hash_table = util.get_exec_dir() / 'data' / 'msyt' / \
            f'Msg_{lang}_hashes.csv'
        if hash_table.exists():
            get_msbt_hashes.texthashes[lang] = {}
            with hash_table.open('r') as h_file:
                csv_loop = csv.reader(h_file)
                for row in csv_loop:
                    get_msbt_hashes.texthashes[lang][row[0]] = row[1]
        elif util.get_game_file(f'Pack/Bootup_{lang}.pack').exists():
            get_msbt_hashes.texthashes[lang] = {}
            bootup_pack = oead.Sarc(
                util.get_game_file(f'Pack/Bootup_{lang}.pack').read_bytes()
            )
            msg_bytes = util.decompress(
                bootup_pack.get_file(f'Message/Msg_{lang}.product.ssarc').data
            )
            msg_pack = oead.Sarc(msg_bytes)
            for msbt in msg_pack.get_files():
                get_msbt_hashes.texthashes[lang][msbt.name] = xxhash.xxh32(msbt.data).hexdigest()
    return get_msbt_hashes.texthashes[lang]


def get_msyt_hashes() -> dict:
    if not hasattr(get_msyt_hashes, 'hashes'):
        import json
        get_msyt_hashes.hashes = json.loads(
            (util.get_exec_dir() / 'data' / 'msyt' / 'msyt_hashes.json')\
                .read_text(encoding='utf-8'),
            encoding='utf-8'
        )
    return get_msyt_hashes.hashes


def get_entry_hashes() -> dict:
    """
    Gets the text entry hash table
    
    :return: A dict containing the hashes of every text entry in every game language
    :rtype: dict
    """
    if not hasattr(get_entry_hashes, 'hashes'):
        from json import loads
        get_entry_hashes.hashes = loads(
            (util.get_exec_dir() / 'data' / 'msyt' / 'lang_hashes.json').read_text(encoding='utf-8')
        )
    return get_entry_hashes.hashes


def extract_ref_msyts(lang: str = 'USen', for_merge: bool = False,
                      tmp_dir: Path = util.get_work_dir() / 'tmp_text'):
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir, ignore_errors=True)

    bootup_pack = oead.Sarc(
        util.get_game_file(f'Pack/Bootup_{lang}.pack').read_bytes()
    )
    msg_bytes = util.decompress(
        bootup_pack.get_file(f'Message/Msg_{lang}.product.ssarc').data
    )
    msg_pack = oead.Sarc(msg_bytes)
    if not for_merge:
        merge_dir = tmp_dir / 'ref'
    else:
        merge_dir = tmp_dir / 'merged'
    for file in msg_pack.get_files():
        ex_file = merge_dir / file.name
        ex_file.parent.mkdir(parents=True, exist_ok=True)
        ex_file.write_bytes(file.data)
    msbt_to_msyt(merge_dir)
    del msg_pack


def _msyt_file(file):
    if system() == 'Windows':
        subprocess.call(
            [MSYT_PATH, 'export', str(file)],
            creationflags=util.CREATE_NO_WINDOW
        )
    else:
        subprocess.call([MSYT_PATH, 'export', str(file)])


def msbt_to_msyt(tmp_dir: Path = util.get_work_dir() / 'tmp_text',
                 pool: multiprocessing.Pool = None):
    """ Converts MSBTs in given temp dir to MSYTs """
    if system() == 'Windows':
        subprocess.run(
            [MSYT_PATH, 'export', '-d', str(tmp_dir)],
            creationflags=util.CREATE_NO_WINDOW
        )
    else:
        subprocess.run([MSYT_PATH, 'export', '-d', str(tmp_dir)])
    fix_msbts = [msbt for msbt in tmp_dir.rglob(
        '**/*.msbt') if not msbt.with_suffix('.msyt').exists()]
    if fix_msbts:
        print('Some MSBTs failed to convert. Trying again individually...')
        if not pool:
            multiprocessing.set_start_method('spawn', True)
        p = pool or multiprocessing.Pool(processes=min(
            multiprocessing.cpu_count(), len(fix_msbts)))
        p.map(_msyt_file, fix_msbts)
        fix_msbts = [
            msbt for msbt in tmp_dir.rglob('**/*.msbt') \
                if not msbt.with_suffix('.msyt').exists()
        ]
        if not pool:
            p.close()
            p.join()
    if fix_msbts:
        print(f'{len(fix_msbts)} MSBT files failed to convert. They will not be merged.')
        util.vprint(fix_msbts)
    for msbt_file in tmp_dir.rglob('**/*.msbt'):
        Path(msbt_file).unlink()
    return fix_msbts


def msyt_to_msbt(tmp_dir: Path = util.get_work_dir() / 'tmp_text'):
    """ Converts merged MSYTs in given temp dir to MSBTs """
    merge_dir = tmp_dir / 'merged'
    m_args = [MSYT_PATH, 'create', '-d', str(merge_dir), '-p', 'wiiu', '-o', str(merge_dir)]
    if system() == 'Windows':
        subprocess.run(
            m_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=util.CREATE_NO_WINDOW
        )
    else:
        subprocess.run(m_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    for merged_msyt in merge_dir.rglob('**/*.msyt'):
        merged_msyt.unlink()


def bootup_from_msbts(lang: str = 'USen',
                      msbt_dir: Path = util.get_work_dir() / 'tmp_text' / 'merged') -> (Path, int):
    new_boot_path = msbt_dir.parent / f'Bootup_{lang}.pack'
    s_msg = oead.SarcWriter(
        endian=oead.Endianness.Big if util.get_settings('wiiu') else oead.Endianness.Little
    )
    for new_msbt in msbt_dir.rglob('**/*.msbt'):
        s_msg.files[str(new_msbt.relative_to(msbt_dir)).replace('\\', '/')] = new_msbt.read_bytes()
    unyaz_bytes = bytes(s_msg.write()[1])
    rsize = rstb.SizeCalculator().calculate_file_size_with_ext(unyaz_bytes, True, '.sarc')
    new_msg_bytes = util.compress(unyaz_bytes)
    s_boot = oead.SarcWriter(
        endian=oead.Endianness.Big if util.get_settings('wiiu') else oead.Endianness.Little
    )
    s_boot.files[f'Message/Msg_{lang}.product.ssarc'] = new_msg_bytes
    new_boot_path.write_bytes(s_boot.write()[1])
    return new_boot_path, rsize


def write_msbt(msbt_info: tuple):
    msbt_path, msbt_data = msbt_info
    msbt_path.parent.mkdir(parents=True, exist_ok=True)
    msbt_path.write_bytes(msbt_data)
    return None


def get_modded_msyts(msg_sarc: oead.Sarc, lang: str = 'USen',
                     tmp_dir: Path = util.get_work_dir() / 'tmp_text',
                     pool: multiprocessing.Pool = None) -> (list, dict):
    hashes = get_msbt_hashes(lang)
    modded_msyts = []
    added_msbts = {}
    write_msbts = []
    for msbt, m_data in [(f.name, bytes(f.data)) for f in msg_sarc.get_files()]:
        if any(exclusion in msbt for exclusion in EXCLUDE_TEXTS):
            continue
        m_hash = xxhash.xxh32(m_data).hexdigest()
        if msbt not in hashes:
            added_msbts[msbt] = m_data
        elif m_hash != hashes[msbt]:
            write_msbts.append((tmp_dir / msbt, m_data))
            modded_msyts.append(msbt.replace('.msbt', '.msyt'))
    if write_msbts:
        if not pool:
            multiprocessing.set_start_method('spawn', True)
        p = pool or multiprocessing.Pool()
        p.map(write_msbt, write_msbts)
        if not pool:
            p.close()
            p.join()
    return modded_msyts, added_msbts


def store_added_texts(new_texts: dict) -> oead.SarcWriter:
    text_sarc = oead.SarcWriter(
        endian=oead.Endianness.Big if util.get_settings('wiiu') else oead.Endianness.Little
    )
    for msbt in new_texts:
        text_sarc.files[msbt] = oead.Bytes(new_texts[msbt])
    return text_sarc
    

def get_entry_hash(text: str) -> str:
    if isinstance(text, list):
        text = str(text)
    import re
    import unicodedata
    text = unicodedata.normalize('NFC', text)
    return xxhash.xxh32(re.sub(r'[\W\d_ ]+', '', text).encode('utf8')).hexdigest()


def threaded_compare_texts(msyt: Path, tmp_dir: Path, lang: str = 'USen') -> (str, dict):
    """Diffs texts in an MYST in a way suitable for multiprocessing"""
    rel_path = str(msyt.relative_to(tmp_dir)).replace('\\', '/')
    if lang in ['USen', 'EUen']:
        lang = 'XXen'
    try:
        with (tmp_dir / rel_path).open('r', encoding='utf-8') as mod_file:
            contents = mod_file.read()
            xhash = xxhash.xxh32(contents.encode('utf8')).hexdigest()
            if xhash == get_msyt_hashes()[lang][rel_path]:
                return rel_path, None
            try:
                mod_text = json.loads(contents)
            except json.JSONDecodeError:
                err = ValueError(f'A character in {rel_path} could not be read')
                err.error_text = (f'A character in {rel_path} could not be read. This probably means that the MSBT '
                                  'file is damaged or corrupt. You may need to report this to the mod\'s creator.')
                raise err
    except FileNotFoundError:
        return rel_path, None
    text_edits = {
        'entries': {}
    }
    hashes = get_entry_hashes()[lang]
    for entry, text in mod_text['entries'].items():
        if entry not in hashes or hashes[entry] != get_entry_hash(text['contents']):
            text_edits['entries'][entry] = copy.deepcopy(text)
    return rel_path, text_edits


def get_modded_texts(modded_msyts: list, lang: str = 'USen', tmp_dir: Path = \
                     util.get_work_dir() / 'tmp_text', pool: multiprocessing.Pool = None) -> dict:
    """
    Builds a dictionary of all edited text entries in modded MSYTs

    :param modded_msyts: A list of MSYT files that have been modified.
    :type modded_msyts: list of str
    :param tmp_dir: The temp directory to use, defaults to "tmp_text" in BCML's working directory.
    :type tmp_dir: class:`pathlib.Path`
    :returns: Returns a dictionary of modified MSYT text entries.
    :rtype: dict
    """
    text_edits = {}
    check_msyts = [msyt for msyt in list(tmp_dir.rglob('**/*.msyt'))
                   if str(msyt.relative_to(tmp_dir)).replace('\\', '/') in modded_msyts]
    if not check_msyts:
        return {}
    num_threads = min(multiprocessing.cpu_count(), len(check_msyts))
    thread_checker = partial(threaded_compare_texts,
                             tmp_dir=tmp_dir, lang=lang)
    if not pool:
        multiprocessing.set_start_method('spawn', True)
    p = pool or multiprocessing.Pool(processes=num_threads)
    edit_results = p.map(thread_checker, check_msyts)
    for edit in edit_results:
        rel_path, edits = edit
        if edits is None:
            print(f'{rel_path} is corrupt and will not be merged.')
            continue
        if edits['entries']:
            text_edits[rel_path] = edits
    if not pool:
        p.close()
        p.join()
    return text_edits


def get_text_mods_from_bootup(bootup_path: Union[Path, str],
                              tmp_dir: Path = util.get_work_dir() / 'tmp_text', lang: str = '',
                              pool: multiprocessing.Pool = None):
    if not lang:
        lang = util.get_file_language(bootup_path)
    print(f'Scanning text modifications for language {lang}...')
    spaces = '  '

    util.vprint(f'{spaces}Identifying modified text files...')
    
    try:
        bootup_sarc = oead.Sarc(bootup_path.read_bytes())
        msg_bytes = util.decompress(bootup_sarc.get_file(f'Message/Msg_{lang}.product.ssarc').data)
        msg_sarc = oead.Sarc(msg_bytes)
    except (ValueError, RuntimeError, oead.InvalidDataError, KeyError):
        print(f'Failed to open Msg_{lang}.product.ssarc, could not analyze texts')
        return
    modded_msyts, added_msbts = get_modded_msyts(msg_sarc, lang, pool=pool)
    added_text_store = None
    if added_msbts:
        added_text_store = store_added_texts(added_msbts)

    for modded_text in modded_msyts:
        util.vprint(f'{spaces}{spaces}{modded_text} has been changed')
    for added_text in added_msbts:
        util.vprint(f'{spaces}{spaces}{added_text} has been added')

    problems = msbt_to_msyt(pool=pool)
    for problem in problems:
        msyt_name = problem.relative_to(tmp_dir).with_suffix('.msyt').as_posix()
        try:
            modded_msyts.remove(msyt_name)
        except ValueError:
            pass
    util.vprint(f'{spaces}Scanning texts files for modified entries...')
    modded_texts = get_modded_texts(modded_msyts, lang=lang, pool=pool)
    s_modded = 's' if len(modded_texts) != 1 else ''
    s_added = 's' if len(added_msbts) != 1 else ''
    print(f'Language {lang} has total {len(modded_texts)} modified text file{s_modded} and '
          f'{len(added_msbts)} new text file{s_added}')
    shutil.rmtree(tmp_dir)
    return modded_texts, added_text_store, lang


def get_text_mods(lang: str = 'USen') -> List[BcmlMod]:
    """
    Gets all installed text mods for a given language

    :param lang: The game language to use, defaults to USen.
    :type lang: str, optional
    :return: Returns a list of all text mods installed for the selected language.
    :rtype: list of class:`bcml.util.BcmlMod`
    """
    tmods = [mod for mod in util.get_installed_mods() if (
        mod.path / 'logs' / f'texts_{lang}.json').exists()]
    return sorted(tmods, key=lambda mod: mod.priority)


def match_language(lang: str, log_dir: Path) -> str:
    logged_langs = set([util.get_file_language(l) for l in log_dir.glob('*texts*')])
    if lang in logged_langs:
        return lang
    elif lang[2:4] in [l[2:4] for l in logged_langs]:
        return [l for l in logged_langs if l[2:4] == lang[2:4]][0]
    else:
        return [l for l in LANGUAGES if l in logged_langs][0]

def get_modded_text_entries(lang: str = 'USen') -> List[dict]:
    """
    Gets a list containing all modified text entries installed
    """
    textmods = []
    tm = TextsMerger()
    for mod in [mod for mod in util.get_installed_mods() if tm.is_mod_logged(mod)]:
        l = match_language(lang, mod.path / 'logs')
        try:
            with (mod.path / 'logs' / f'texts_{l}.json').open('r', encoding='utf-8') as mod_text:
                textmods.append(json.load(mod_text))
        except FileNotFoundError:
            pass
    return textmods


def get_modded_languages(mod: Path) -> []:
    """ Gets all languages with modded texts for a given mod """
    if isinstance(mod, BcmlMod):
        mod = mod.path
    text_langs = []
    for text_lang in (mod / 'logs').glob('*text*'):
        lang = util.get_file_language(text_lang)
        if lang not in text_langs:
            text_langs.append(lang)
    return text_langs


def get_added_text_mods(lang: str = 'USen') -> List[oead.Sarc]:
    """
    Gets a list containing all mod-original texts installed
    """
    textmods = []
    tm = TextsMerger()
    for mod in [mod for mod in util.get_installed_mods() if tm.is_mod_logged(mod)]:
        l = match_language(lang, mod.path / 'logs')
        try:
            textmods.append(oead.Sarc((mod.path / 'logs' / f'newtexts_{l}.sarc').read_bytes()))
        except FileNotFoundError:
            pass
    return textmods


def threaded_merge_texts(msyt: Path, merge_dir: Path,
                         text_mods: List[dict]) -> (int, str):
    """
    Merges changes to a text file

    :param msyt: The path to the MSYT to merge into.
    :type msyt: class:`pathlib.Path`
    :param merge_dir: The path of the directory containing MSYT files to merge.
    :type merge_dir: class:`pathlib.Path`
    :param text_mods: A list of dicts containing text entires to merge.
    :type text_mods: list of dict
    :return: Returns the number of merged entries and the path to the merged MSYT.
    :rtype: (int, str)
    """
    rel_path = str(msyt.relative_to(merge_dir)).replace('\\', '/')
    should_bother = False
    merge_count = 0
    for textmod in text_mods:
        if rel_path in textmod:
            break
    else:
        util.vprint(f'  Skipping {rel_path}, no merge needed')
        return 0, None

    with msyt.open('r', encoding='utf-8') as f_ref:
        merged_text = json.load(f_ref)
    # util.vprint(text_mods)
    for textmod in text_mods:
        diff_found = False
        if rel_path in textmod:
            if textmod[rel_path]['entries'] == merged_text['entries']:
                continue
            for entry in textmod[rel_path]['entries']:
                diff_found = True
                merged_text['entries'][entry] = copy.deepcopy(
                    textmod[rel_path]['entries'][entry])
        if diff_found:
            merge_count += 1

    with msyt.open('w', encoding='utf-8') as f_ref:
        json.dump(merged_text, f_ref, ensure_ascii=False)
    return merge_count, rel_path


def merge_texts(lang: str = 'USen', tmp_dir: Path = util.get_work_dir() / 'tmp_text',
                pool: multiprocessing.Pool = None):
    print(f'Loading text mods for language {lang}...')
    text_mods = get_modded_text_entries(lang)
    util.vprint(text_mods)
    if not text_mods:
        print('No text merging necessary.')
        old_path = util.get_master_modpack_dir() / util.get_content_path() / 'Pack' / \
            f'Bootup_{lang}.pack'
        if old_path.exists():
            old_path.unlink()
        return
    print(f'Found {len(text_mods)} text mods to be merged')

    if tmp_dir.exists():
        util.vprint('Cleaning temp directory...')
        shutil.rmtree(tmp_dir, ignore_errors=True)
    print('Extracting clean MSYTs...')
    extract_ref_msyts(lang, for_merge=True, tmp_dir=tmp_dir)
    merge_dir = tmp_dir / 'merged'
    merge_dir.mkdir(parents=True, exist_ok=True)

    print('Merging modified text files...')
    modded_text_files = list(merge_dir.rglob('**/*.msyt'))
    if not pool:
        num_threads = min(multiprocessing.cpu_count(), len(modded_text_files))
        multiprocessing.set_start_method('spawn', True)
    p = pool or multiprocessing.Pool(processes=num_threads)
    thread_merger = partial(threaded_merge_texts, merge_dir=merge_dir, text_mods=text_mods)
    p.map(thread_merger, modded_text_files)
    if not pool:
        p.close()
        p.join()
    print('Generating merged MSBTs...')
    msyt_to_msbt(tmp_dir)

    added_texts = get_added_text_mods(lang)
    if added_texts:
        print('Adding mod-original MSBTs...')
        for added_text in added_texts:
            for msbt in added_text.get_files():
                Path(merge_dir / msbt.name).parent.mkdir(parents=True, exist_ok=True)
                Path(merge_dir / msbt.name).write_bytes(msbt.data)

    print(f'Creating new Bootup_{lang}.pack...')
    tmp_boot_path = bootup_from_msbts(lang)[0]
    merged_boot_path = util.get_modpack_dir() / '9999_BCML' / util.get_content_path() / \
        'Pack' / f'Bootup_{lang}.pack'
    if merged_boot_path.exists():
        util.vprint(f'  Removing old Bootup_{lang}.pack...')
        merged_boot_path.unlink()
    merged_boot_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(str(tmp_boot_path), str(merged_boot_path))

    rstb_path = util.get_modpack_dir() / '9999_BCML' / util.get_content_path() / 'System' / 'Resource' /\
                                         'ResourceSizeTable.product.srsizetable'
    if rstb_path.exists():
        table: rstb.ResourceSizeTable = rstb.util.read_rstb(
            str(rstb_path), True)
    else:
        table = rstable.get_stock_rstb()
    msg_path = f'Message/Msg_{lang}.product.sarc'
    if table.is_in_table(msg_path):
        print('Correcting RSTB...')
        table.delete_entry(msg_path)
    rstb_path.parent.mkdir(parents=True, exist_ok=True)
    rstb.util.write_rstb(table, str(rstb_path), True)

class TextsMerger(mergers.Merger):
    """ A merger for game texts """
    NAME: str = 'texts'

    def __init__(self, user_only: bool = True):
        super().__init__('game texts', 'Merges changes to game texts', '', options={
            'user_only': user_only
        })

    def generate_diff(self, mod_dir: Path, modded_files: List[Union[str, Path]]):
        diffs = {}
        bootups = {util.get_file_language(file): file for file in modded_files
                   if 'Bootup_' in str(file) and 'Graphics' not in str(file) 
                   and isinstance(file, Path)}
        if not bootups:
            return {}
        mod_langs = list(bootups.keys())
        lang_map = {}
        save_langs = LANGUAGES if not self._options['user_only'] else [util.get_settings('lang')]
        for lang in save_langs:
            if lang in mod_langs:
                lang_map[lang] = lang
            elif lang[2:4] in [l[2:4] for l in mod_langs]:
                lang_map[lang] = [l for l in mod_langs if l[2:4] == lang[2:4]][0]
            else:
                lang_map[lang] = [l for l in LANGUAGES if l in mod_langs][0]
        lang_diffs = {}
        from io import StringIO
        for lang in set(lang_map.values()):
            dict_diffs, added = get_text_mods_from_bootup(
                bootups[lang],
                lang=lang,
                pool=self._pool
            )[:2]
            str_buf = StringIO()
            json.dump(dict_diffs, str_buf, ensure_ascii=False)
            lang_diffs[lang] = (str_buf.getvalue(), added)
            del str_buf
        for u_lang, t_lang in lang_map.items():
            diffs[u_lang] = lang_diffs[t_lang]
        return diffs


    def log_diff(self, mod_dir: Path, diff_material):
        if isinstance(diff_material, List):
            diff_material = self.generate_diff(mod_dir, diff_material)
        for lang in diff_material:
            with Path(mod_dir / 'logs' / f'texts_{lang}.json').open('w', encoding='utf-8') as t_file:
                t_file.write(diff_material[lang][0])
            text_sarc = diff_material[lang][1]
            if text_sarc is not None:
                Path(mod_dir / 'logs' / f'newtexts_{lang}.sarc').write_bytes(
                    text_sarc.write()[1]
                )

    def is_mod_logged(self, mod: BcmlMod):
        return bool(
            list((mod.path / 'logs').glob('*texts*'))
        )

    def get_mod_diff(self, mod: BcmlMod):
        diffs = []

        def load_diff(folder: Path) -> {}:
            diff = {}
            for file in (folder / 'logs').glob('texts_*.json'):
                lang = util.get_file_language(file)
                if not lang in diff:
                    diff[lang] = {}
                with file.open('r', encoding='utf-8') as log:
                    diff[lang]['mod'] = json.load(log)
            for file in (folder / 'logs').glob('newtexts*.sarc'):
                lang = util.get_file_language(file)
                if not lang in diff:
                    diff[lang] = {}
                diff[lang]['add'] = oead.Sarc(file.read_bytes())
            return diff

        if self.is_mod_logged(mod):
            diffs.append(load_diff(mod.path / 'logs'))
        for opt in {d for d in (mod.path / 'options').glob('*') if d.is_dir()}:
            if (opt / 'logs' / self._log_name).exists():
                diffs.append(load_diff(opt / 'logs'))

        return diffs

    def get_all_diffs(self):
        diffs = []
        for mod in util.get_installed_mods():
            diffs.extend(self.get_mod_diff(mod))
        return diffs

    def consolidate_diffs(self, diffs: list):
        all_diffs = {}
        for diff in reversed(diffs):
            for lang in diff:
                if lang not in all_diffs:
                    all_diffs[lang] = {}
                if 'mod' in diff[lang]:
                    if 'mod' not in all_diffs[lang]:
                        all_diffs[lang]['mod'] = {}
                    for file in diff[lang]['mod']:
                        if file not in all_diffs[lang]['mod']:
                            all_diffs[lang]['mod'][file] = {'entries': {}}
                        for entry, contents in diff[lang]['mod'][file]['entries'].items():
                            if entry not in all_diffs[lang]['mod'][file]['entries']:
                                all_diffs[lang]['mod'][file]['entries'][entry] = contents
                if 'add' in diff[lang]:
                    if 'add' not in all_diffs[lang]:
                        all_diffs[lang]['add'] = []
                    all_diffs[lang]['add'].append(diff[lang]['add'])
        util.vprint('All text diffs:')
        # util.vprint(all_diffs)
        return all_diffs

    @util.timed
    def perform_merge(self):
        merge_texts(util.get_settings('lang'), pool=self._pool)
