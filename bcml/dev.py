from fnmatch import fnmatch
from functools import partial
from multiprocessing import Pool, cpu_count, set_start_method
from pathlib import Path
from platform import system
import shutil
import subprocess

import aamp
from aamp import yaml_util
import byml
import sarc
import xxhash
import yaml
import lib_bcml

from . import util, install, json_util

EXCLUDE_EXTS = {'.yml', '.yaml', '.bak', '.txt', '.json', '.old'}


def _yml_to_byml(file: Path):
    data = byml.Writer(
        json_util.json_to_byml(
            lib_bcml.byml_yaml_to_json(
                file.read_text('utf-8')
            )
        ),
        be=util.get_settings('wiiu')
    ).get_bytes()
    out = file.with_suffix('')
    out.write_bytes(
        data if not out.suffix.startswith('.s') else util.compress(data)
    )
    file.unlink()


def _yml_to_aamp(file: Path):
    file.with_suffix('').write_bytes(
        aamp.Writer(
            json_util.json_to_aamp(
                lib_bcml.aamp_yaml_to_json(
                    file.read_text('utf-8')
                )
            )
        )
    )
    file.unlink()


def _pack_sarcs(tmp_dir: Path, hashes: dict):
    sarc_folders = {
        d for d in tmp_dir.rglob('**/*') if (
            d.is_dir() and not 'options' in d.relative_to(tmp_dir).parts\
                and d.suffix != '.pack' and d.suffix in util.SARC_EXTS
        )
    }
    if sarc_folders:
        num_threads = min(len(sarc_folders), cpu_count())
        pool = Pool(processes=num_threads)
        pool.map(
            partial(_pack_sarc, hashes=hashes, tmp_dir=tmp_dir),
            sarc_folders
        )
        pool.close()
        pool.join()
        del pool
    pack_folders = {
        d for d in tmp_dir.rglob('**/*') if d.is_dir() \
            and not 'options' in d.relative_to(tmp_dir).parts and d.suffix == '.pack'
    }
    if pack_folders:
        num_threads = min(len(pack_folders), cpu_count())
        pool = Pool(processes=num_threads)
        pool.map(
            partial(_pack_sarc, hashes=hashes, tmp_dir=tmp_dir),
            pack_folders
        )
        pool.close()
        pool.join()

def _pack_sarc(folder: Path, tmp_dir: Path, hashes: dict):
    packed = sarc.SARCWriter(util.get_settings('wiiu'))
    try:
        canon = util.get_canon_name(
            folder.relative_to(tmp_dir).as_posix(),
            allow_no_source=True
        )
        if canon not in hashes:
            raise FileNotFoundError('File not in game dump')
        stock_file = util.get_game_file(folder.relative_to(tmp_dir))
        with stock_file.open('rb') as old_file:
            old_sarc = sarc.read_file_and_make_sarc(old_file)
            if not old_sarc:
                raise ValueError('Cannot open file from game dump')
            old_files = set(old_sarc.list_files())
    except (FileNotFoundError, ValueError):
        for file in {f for f in folder.rglob('**/*') if f.is_file()}:
            packed.add_file(
                file.relative_to(folder).as_posix(),
                file.read_bytes()
            )
    else:
        for file in {
            f for f in folder.rglob('**/*') if f.is_file() and not f.suffix in EXCLUDE_EXTS
        }:
            file_data = file.read_bytes()
            xhash = xxhash.xxh32(util.unyaz_if_needed(file_data)).hexdigest()
            file_name = file.relative_to(folder).as_posix()
            if file_name in old_files:
                old_hash = xxhash.xxh32(
                    util.unyaz_if_needed(
                        old_sarc.get_file_data(file_name).tobytes()
                    )
                ).hexdigest()
            if file_name not in old_files or (
                xhash != old_hash and file.suffix not in util.AAMP_EXTS
            ):
                packed.add_file(file_name, file_data)
    finally:
        shutil.rmtree(folder)
        if not packed._files:  # pylint: disable=no-member
            return
        sarc_bytes = packed.get_bytes()
        folder.write_bytes(
            util.compress(sarc_bytes) if (
                folder.suffix.startswith('.s') and not folder.suffix == '.sarc'
            ) else sarc_bytes
        )


def _clean_sarcs(tmp_dir: Path, hashes: dict):
    sarc_files = {
        file for file in tmp_dir.rglob('**/*') if file.suffix in util.SARC_EXTS \
            and 'options' not in file.relative_to(tmp_dir).parts
    }
    if sarc_files:
        print('Creating partial packs...')
        num_threads = min(len(sarc_files), cpu_count())
        pool = Pool(processes=num_threads)
        pool.map(partial(_clean_sarc, hashes=hashes, tmp_dir=tmp_dir), sarc_files)
        pool.close()
        pool.join()

    sarc_files = {
        file for file in tmp_dir.rglob('**/*') if file.suffix in util.SARC_EXTS \
            and 'options' not in file.relative_to(tmp_dir).parts
    }
    if sarc_files:
        print('Updating pack log...')
        with (tmp_dir / 'logs' / 'packs.json').open('w', encoding='utf-8') as p_file:
            final_packs = [
                file for file in list(tmp_dir.rglob('**/*')) if file.suffix in util.SARC_EXTS
            ]
            if final_packs:
                p_file.write('name,path\n')
                for file in final_packs:
                    p_file.write(
                        f'{util.get_canon_name(file.relative_to(tmp_dir))},'
                        f'{file.relative_to(tmp_dir)}\n'
                    )
    else:
        try:
            (tmp_dir / 'logs' / 'packs.json').unlink()
        except FileNotFoundError:
            pass


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


def _do_yml(file: Path):
    out = file.with_suffix('')
    if out.exists():
        return
    if out.suffix in util.AAMP_EXTS:
        _yml_to_aamp(file)
    elif out.suffix in util.BYML_EXTS:
        _yml_to_byml(file)


def _make_bnp_logs(tmp_dir: Path, options: dict):
    logged_files = install.generate_logs(tmp_dir, options=options)

    print('Removing unnecessary files...')

    if (tmp_dir / 'logs' / 'map.json').exists():
        print('Removing map units...')
        for file in [file for file in logged_files if isinstance(file, Path) and \
                           fnmatch(file.name, '[A-Z]-[0-9]_*.smubin')]:
            file.unlink()

    if [file for file in (tmp_dir / 'logs').glob('*texts*')]:
        print('Removing language bootup packs...')
        for bootup_lang in (tmp_dir / util.get_content_path() / 'Pack').glob('Bootup_*.pack'):
            bootup_lang.unlink()

    if (tmp_dir / 'logs' / 'actorinfo.json').exists() and \
       (tmp_dir / util.get_content_path() / 'Actor' / 'ActorInfo.product.sbyml').exists():
        print('Removing ActorInfo.product.sbyml...')
        (tmp_dir / util.get_content_path() / 'Actor' / 'ActorInfo.product.sbyml').unlink()

    if (tmp_dir / 'logs' / 'gamedata.json').exists() or (tmp_dir / 'logs' / 'savedata.yml').exists():
        print('Removing gamedata sarcs...')
        with (tmp_dir / util.get_content_path() / 'Pack' / 'Bootup.pack').open('rb') as b_file:
            bsarc = sarc.read_file_and_make_sarc(b_file)
        csarc = sarc.make_writer_from_sarc(bsarc)
        bsarc_files = list(bsarc.list_files())
        if 'GameData/gamedata.ssarc' in bsarc_files:
            csarc.delete_file('GameData/gamedata.ssarc')
        if 'GameData/savedataformat.ssarc' in bsarc_files:
            csarc.delete_file('GameData/savedataformat.ssarc')
        with (tmp_dir / util.get_content_path() / 'Pack' / 'Bootup.pack').open('wb') as b_file:
            csarc.write(b_file)


def create_bnp_mod(mod: Path, output: Path, meta: dict, options: dict = None):
    if isinstance(mod, str):
        mod = Path(mod)

    if mod.is_file():
        print('Extracting mod...')
        tmp_dir: Path = install.open_mod(mod)
    elif mod.is_dir():
        print(f'Loading mod from {str(mod)}...')
        tmp_dir = util.get_work_dir() / f'tmp_{xxhash.xxh32(str(mod).encode("utf-8")).hexdigest()}'
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)
        shutil.copytree(mod, tmp_dir)
    else:
        print(f'Error: {str(mod)} is neither a valid file nor a directory')
        return

    if (tmp_dir / 'rules.txt').exists():
        (tmp_dir / 'rules.txt').unlink()
    import json
    (tmp_dir / 'info.json').write_text(
        json.dumps(meta, ensure_ascii=False),
        encoding='utf-8'
    )

    yml_files = {f for f in tmp_dir.glob('**/*.yml')}
    if yml_files:
        print('Compiling YAML documents...')
        p = Pool(
            min(len(yml_files, cpu_count()))
        )
        p.map(_do_yml, yml_files)

    set_start_method('spawn', True)
    hashes = util.get_hash_table()
    print('Packing SARCs...')
    _pack_sarcs(tmp_dir, hashes)
    for d in {d for d in tmp_dir.glob('options/*') if d.is_dir()}:
        _pack_sarcs(d, hashes)

    for o in tmp_dir.glob('options/*'):
        for file in {
            f for f in o.rglob('**/*') if f.is_file() and (tmp_dir / f.relative_to(tmp_dir)).exists()
        }:
            xh1 = xxhash.xxh32_hexdigest((tmp_dir / file.relative_to(o)).read_bytes())
            xh2 = xxhash.xxh32_hexdigest(file.read_bytes())
            if xh1 == xh2:
                file.unlink()

    if not options:
        options = {
            'disable': [],
            'options': {}
        }
    options['texts'] = {'user_only': False}
    
    _make_bnp_logs(tmp_dir, options)
    for o in tmp_dir.glob('options/*'):
        _make_bnp_logs(o, options)

    _clean_sarcs(tmp_dir, hashes)
    for d in {d for d in tmp_dir.glob('options/*') if d.is_dir()}:
        _clean_sarcs(d, hashes)

    print('Cleaning any junk files...')
    for file in {f for f in tmp_dir.rglob('**/*') if f.is_file()}:
        if 'logs' in file.parts:
            continue
        if file.suffix in ['.yml', '.json', '.bak', '.tmp', '.old'] and file.stem != 'info':
            file.unlink()

    print('Removing blank folders...')
    for folder in reversed(list(tmp_dir.rglob('**/*'))):
        if folder.is_dir() and not list(folder.glob('*')):
            shutil.rmtree(folder)

    print(f'Saving output file to {str(output)}...')
    x_args = [install.ZPATH, 'a', str(output), f'{str(tmp_dir / "*")}']
    if system() == 'Windows':
        subprocess.run(
            x_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=util.CREATE_NO_WINDOW
        )
    else:
        subprocess.run(x_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print('Conversion complete.')
