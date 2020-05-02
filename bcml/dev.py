# pylint: disable=unsupported-assignment-operation
from base64 import urlsafe_b64encode
from fnmatch import fnmatch
from functools import partial
from json import dumps
from multiprocessing import Pool, cpu_count, set_start_method
from pathlib import Path
from platform import system
import shutil
import subprocess
import traceback

import oead
import xxhash

from . import util, install

EXCLUDE_EXTS = {'.yml', '.yaml', '.bak', '.txt', '.json', '.old'}


def _yml_to_byml(file: Path):
    data = oead.byml.to_binary(
        oead.byml.from_text(
            file.read_text('utf-8')
        ),
        big_endian=util.get_settings('wiiu')
    )
    out = file.with_suffix('')
    out.write_bytes(
        data if not out.suffix.startswith('.s') else util.compress(data)
    )
    file.unlink()


def _yml_to_aamp(file: Path):
    file.with_suffix('').write_bytes(
        oead.aamp.ParameterIO.from_text(file.read_text('utf-8')).to_binary()
    )
    file.unlink()


def _pack_sarcs(tmp_dir: Path, hashes: dict, pool: Pool):
    sarc_folders = {
        d for d in tmp_dir.rglob('**/*') if (
            d.is_dir() and not 'options' in d.relative_to(tmp_dir).parts\
                and d.suffix != '.pack' and d.suffix in util.SARC_EXTS
        )
    }
    if sarc_folders:
        pool.map(
            partial(_pack_sarc, hashes=hashes, tmp_dir=tmp_dir),
            sarc_folders
        )
    pack_folders = {
        d for d in tmp_dir.rglob('**/*') if d.is_dir() \
            and not 'options' in d.relative_to(tmp_dir).parts and d.suffix == '.pack'
    }
    if pack_folders:
        pool.map(
            partial(_pack_sarc, hashes=hashes, tmp_dir=tmp_dir),
            pack_folders
        )

def _pack_sarc(folder: Path, tmp_dir: Path, hashes: dict):
    packed = oead.SarcWriter(
        endian=oead.Endianness.Big if util.get_settings('wiiu') else oead.Endianness.Little
    )
    try:
        canon = util.get_canon_name(
            folder.relative_to(tmp_dir).as_posix(),
            allow_no_source=True
        )
        if canon not in hashes:
            raise FileNotFoundError('File not in game dump')
        stock_file = util.get_game_file(folder.relative_to(tmp_dir))
        try:
            old_sarc = oead.Sarc(
                util.unyaz_if_needed(stock_file.read_bytes())
            )
        except (RuntimeError, ValueError, oead.InvalidDataError):
            raise ValueError('Cannot open file from game dump')
        old_files = {f.name for f in old_sarc.get_files()}
    except (FileNotFoundError, ValueError):
        for file in {f for f in folder.rglob('**/*') if f.is_file()}:
            packed.files[file.relative_to(folder).as_posix()] = file.read_bytes()
    else:
        for file in {
                f for f in folder.rglob('**/*') if f.is_file() and not f.suffix in EXCLUDE_EXTS
            }:
            file_data = file.read_bytes()
            xhash = xxhash.xxh64_intdigest(util.unyaz_if_needed(file_data))
            file_name = file.relative_to(folder).as_posix()
            if file_name in old_files:
                old_hash = xxhash.xxh64_intdigest(
                    util.unyaz_if_needed(
                        old_sarc.get_file(file_name).data
                    )
                )
            if file_name not in old_files or (
                    xhash != old_hash and file.suffix not in util.AAMP_EXTS
                ):
                packed.files[file_name] = file_data
    finally:
        shutil.rmtree(folder)
        if not packed.files:
            return # pylint: disable=lost-exception
        sarc_bytes = packed.write()[1]
        folder.write_bytes(
            util.compress(sarc_bytes) if (
                folder.suffix.startswith('.s') and not folder.suffix == '.sarc'
            ) else sarc_bytes
        )


def _clean_sarcs(tmp_dir: Path, hashes: dict, pool: Pool):
    sarc_files = {
        file for file in tmp_dir.rglob('**/*') if file.suffix in util.SARC_EXTS \
            and 'options' not in file.relative_to(tmp_dir).parts
    }
    if sarc_files:
        print('Creating partial packs...')
        pool.map(partial(_clean_sarc, hashes=hashes, tmp_dir=tmp_dir), sarc_files)

    sarc_files = {
        file for file in tmp_dir.rglob('**/*') if file.suffix in util.SARC_EXTS \
            and 'options' not in file.relative_to(tmp_dir).parts
    }
    if sarc_files:
        print('Updating pack log...')
        final_packs = [
            file for file in sarc_files if file.suffix in util.SARC_EXTS
        ]
        if final_packs:
            (tmp_dir / 'logs').mkdir(parents=True, exist_ok=True)
            (tmp_dir / 'logs' / 'packs.json').write_text(
                dumps({
                    util.get_canon_name(file.relative_to(tmp_dir)): str(file.relative_to(tmp_dir))\
                        for file in final_packs
                })
            )
        else:
            try:
                (tmp_dir / 'logs' / 'packs.json').unlink()
            except FileNotFoundError:
                pass
    else:
        try:
            (tmp_dir / 'logs' / 'packs.json').unlink()
        except FileNotFoundError:
            pass


def _clean_sarc(file: Path, hashes: dict, tmp_dir: Path):
    if 'TitleBG' in str(file):
        print('Here we go')
    canon = util.get_canon_name(file.relative_to(tmp_dir))
    try:
        stock_file = util.get_game_file(file.relative_to(tmp_dir))
    except FileNotFoundError:
        return
    try:
        old_sarc = oead.Sarc(util.unyaz_if_needed(stock_file.read_bytes()))
    except (RuntimeError, ValueError, oead.InvalidDataError):
        return
    old_files = {f.name for f in old_sarc.get_files()}
    if canon not in hashes:
        return
    try:
        base_sarc = oead.Sarc(util.unyaz_if_needed(file.read_bytes()))
    except (RuntimeError, ValueError, oead.InvalidDataError):
        return
    new_sarc = oead.SarcWriter(
        endian=oead.Endianness.Big if util.get_settings('wiiu') else oead.Endianness.Little
    )
    can_delete = True
    for nest_file, file_data in [(f.name, f.data) for f in base_sarc.get_files()]:
        canon = nest_file.replace('.s', '.')
        ext = Path(canon).suffix
        if ext in {'.yml', '.bak'}:
            continue
        if nest_file in old_files:
            old_data = util.unyaz_if_needed(old_sarc.get_file(nest_file).data)
        if nest_file not in old_files or (
                util.unyaz_if_needed(file_data) != old_data and ext not in util.AAMP_EXTS
            ):
            can_delete = False
            new_sarc.files[nest_file] = oead.Bytes(file_data)
    del old_sarc
    if can_delete:
        del new_sarc
        file.unlink()
    else:
        write_bytes = new_sarc.write()[1]
        file.write_bytes(
            write_bytes if not (
                file.suffix.startswith('.s') and file.suffix != '.ssarc'
            ) else util.compress(write_bytes)
        )


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

    if (tmp_dir / 'logs' / 'map.yml').exists():
        print('Removing map units...')
        for file in [file for file in logged_files if isinstance(file, Path) and \
                           fnmatch(file.name, '[A-Z]-[0-9]_*.smubin')]:
            file.unlink()

    if set((tmp_dir / 'logs').glob('*texts*')):
        print('Removing language bootup packs...')
        for bootup_lang in (tmp_dir / util.get_content_path() / 'Pack').glob('Bootup_*.pack'):
            bootup_lang.unlink()

    if (tmp_dir / 'logs' / 'actorinfo.yml').exists() and \
       (tmp_dir / util.get_content_path() / 'Actor' / 'ActorInfo.product.sbyml').exists():
        print('Removing ActorInfo.product.sbyml...')
        (tmp_dir / util.get_content_path() / 'Actor' / 'ActorInfo.product.sbyml').unlink()

    if (tmp_dir / 'logs' / 'gamedata.yml').exists() or (tmp_dir / 'logs' / 'savedata.yml').exists():
        print('Removing gamedata sarcs...')
        bsarc = oead.Sarc(
            (tmp_dir / util.get_content_path() / 'Pack' / 'Bootup.pack').read_bytes()
        )
        csarc = oead.SarcWriter.from_sarc(bsarc)
        bsarc_files = {f.name for f in bsarc.get_files()}
        if 'GameData/gamedata.ssarc' in bsarc_files:
            del csarc.files['GameData/gamedata.ssarc']
        if 'GameData/savedataformat.ssarc' in bsarc_files:
            del csarc.files['GameData/savedataformat.ssarc']
        (tmp_dir / util.get_content_path() / 'Pack' / 'Bootup.pack').write_bytes(csarc.write()[1])


def create_bnp_mod(mod: Path, output: Path, meta: dict, options: dict = None):
    if isinstance(mod, str):
        mod = Path(mod)

    if mod.is_file():
        print('Extracting mod...')
        tmp_dir: Path = install.open_mod(mod)
    elif mod.is_dir():
        print(f'Loading mod from {str(mod)}...')
        tmp_dir = util.get_work_dir() / f'tmp_{xxhash.xxh64_hexdigest(str(mod).encode("utf-8"))}'
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)
        shutil.copytree(mod, tmp_dir)
    else:
        print(f'Error: {str(mod)} is neither a valid file nor a directory')
        return

    if (tmp_dir / 'rules.txt').exists():
        (tmp_dir / 'rules.txt').unlink()

    meta['id'] = urlsafe_b64encode(meta['name'].encode('utf8')).decode('utf8')
    (tmp_dir / 'info.json').write_text(
        dumps(meta, ensure_ascii=False),
        encoding='utf-8'
    )

    set_start_method('spawn', True)
    with Pool(cpu_count()) as pool:
        yml_files = {f for f in tmp_dir.glob('**/*.yml')}
        if yml_files:
            print('Compiling YAML documents...')
            pool.map(_do_yml, yml_files)

        hashes = util.get_hash_table(util.get_settings('wiiu'))
        print('Packing SARCs...')
        _pack_sarcs(tmp_dir, hashes, pool)
        for folder in {d for d in tmp_dir.glob('options/*') if d.is_dir()}:
            _pack_sarcs(folder, hashes, pool)

        for option_dir in tmp_dir.glob('options/*'):
            for file in {
                    f for f in option_dir.rglob('**/*') if (
                        f.is_file() and (tmp_dir / f.relative_to(option_dir)).exists()
                    )
                }:
                xh1 = xxhash.xxh64_intdigest((tmp_dir / file.relative_to(option_dir)).read_bytes())
                xh2 = xxhash.xxh64_intdigest(file.read_bytes())
                if xh1 == xh2:
                    file.unlink()

        if not options:
            options = {
                'disable': [],
                'options': {}
            }
        options['texts'] = {'user_only': False}

        try:
            _make_bnp_logs(tmp_dir, options)
            for option_dir in tmp_dir.glob('options/*'):
                _make_bnp_logs(option_dir, options)
        except Exception as err: # pylint: disable=broad-except
            err.error_text = (
                'There was an error generating change logs for your mod. Error details:'
                f"""<textarea class="scroller" readonly>{
                    getattr(err, 'error_text', traceback.format_exc(-5))
                }</textarea>"""
            )

        _clean_sarcs(tmp_dir, hashes, pool)
        for folder in {d for d in tmp_dir.glob('options/*') if d.is_dir()}:
            _clean_sarcs(folder, hashes, pool)

    print('Cleaning any junk files...')
    for file in {f for f in tmp_dir.rglob('**/*') if f.is_file()}:
        if 'logs' in file.parts:
            continue
        if file.suffix in {'.yml', '.json', '.bak', '.tmp', '.old'} and file.stem != 'info':
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
            creationflags=util.CREATE_NO_WINDOW,
            check=True
        )
    else:
        subprocess.run(x_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    print('Conversion complete.')
