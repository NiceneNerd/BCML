from configparser import ConfigParser
from pathlib import Path
import json

import yaml
from aamp import yaml_util as ayu
from byml import yaml_util as byu
from bcml import util, json_util

def convert_old_mods():
    import shutil
    mod_dir = util.get_modpack_dir()
    old_path = util.get_cemu_dir() / 'graphicPacks' / 'BCML'
    print('Moving old mods...')
    shutil.rmtree(mod_dir, ignore_errors=True)
    try:
        shutil.move(old_path, mod_dir)
    except OSError:
        shutil.copytree(old_path, mod_dir)
        shutil.rmtree(old_path, ignore_errors=True)
    print('Converting old mods...')
    for mod in {
        d for d in mod_dir.glob('*') if d.is_dir() and d.name != '9999_BCML'
    }:
        print(f'Converting {mod.name[4:]}')
        try:
            convert_old_mod(mod, True)
        except Exception as e:
            e.error_text = f'BCML was unable to convert {mod.name[4:]}. Error: {str(e)}'
            raise e


def convert_old_mod(mod: Path, delete_old: bool = False):
    rules_to_info(mod / 'rules.txt', delete_old=delete_old)
    if (mod / 'logs').exists():
        convert_old_logs(mod, delete_old=delete_old)


def convert_old_settings():
    old_settings = ConfigParser()
    old_settings.read(str(util.get_data_dir() / 'settings.ini'))
    cemu_dir = old_settings['Settings']['cemu_dir']
    game_dir = old_settings['Settings']['game_dir']
    update_dir = util.guess_update_dir(Path(cemu_dir), Path(game_dir))
    dlc_dir = util.guess_aoc_dir(Path(cemu_dir), Path(game_dir))
    settings = {
        'cemu_dir': cemu_dir,
        'game_dir': game_dir,
        'load_reverse': old_settings['Settings']['load_reverse'] == 'True',
        'update_dir': str(update_dir or ""),
        'dlc_dir': str(dlc_dir or ""),
        'site_meta': old_settings['Settings']['site_meta'],
        'guess_merge': old_settings['Settings']['guess_merge'] == 'True',
        'lang': old_settings['Settings']['lang'],
        'no_cemu': False,
        'wiiu': True
    }
    setattr(util.get_settings, 'settings', settings)
    (util.get_data_dir() / 'settings.ini').unlink()
    util.save_settings()


def rules_to_info(rules_path: Path, delete_old: bool = False):
    from bcml.util import RulesParser
    import base64
    rules = RulesParser()
    rules.read(str(rules_path))
    info = {
        'name': str(rules['Definition']['name']),
        'description': str(rules['Definition'].get('description', '')),
        'url': str(rules['Definition'].get('url', '')),
        'image': str(rules['Definition'].get('image', '')),
        'version': 1.0,
        'dependencies': [],
        'options': []
    }
    info['id'] = base64.urlsafe_b64encode(info['name'].encode('utf8')).decode('utf8')
    try:
        info['priority'] = int(rules['Definition']['fsPriority'])
    except KeyError:
        info['priority'] = int(getattr(rules['Definition'], 'fspriority', 100))
    (rules_path.parent / 'info.json').write_text(
        json.dumps(info, ensure_ascii=False, indent=4)
    )
    if delete_old:
        rules_path.unlink()


def convert_old_logs(mod_dir: Path, delete_old: bool = False):
    if (mod_dir / 'logs' / 'packs.log').exists():
        _convert_pack_log(mod_dir)
    for log in mod_dir.glob('logs/*.yml'):
        if log.name == 'deepmerge.yml':
            _convert_aamp_log(log)
        elif log.name.startswith('texts'):
            text_data = yaml.safe_load(log.read_text('utf-8'))
            log.with_suffix('.json').write_text(
                json.dumps(text_data, ensure_ascii=False),
                encoding='utf-8'
            )
        else:
            _convert_byml_log(log)
        if delete_old:
            log.unlink()

def _convert_byml_log(log: Path):
    if not hasattr(_convert_byml_log, 'loader'):
        _convert_byml_log.loader = yaml.CSafeLoader
        byu.add_constructors(_convert_byml_log.loader)
    log_yaml = yaml.load(
        log.read_text('utf-8'),
        Loader=_convert_byml_log.loader
    )
    log.with_suffix('.json').write_text(
        json_util.byml_to_json(log_yaml),
        encoding='utf-8'
    )


def _convert_pack_log(mod: Path):
    import csv
    packs = {}
    with (mod / 'logs' / 'packs.log').open('r') as rlog:
        csv_loop = csv.reader(rlog)
        for row in csv_loop:
            if 'logs' in str(row[1]) or str(row[0]) == 'name':
                continue
            packs[str(row[0])] = Path(str(row[1])).as_posix().replace('\\', '/')
    (mod / 'logs' / 'packs.log').unlink()
    (mod / 'logs' / 'packs.json').write_text(
        json.dumps(packs, ensure_ascii=False),
        encoding='utf-8'
    )


def _convert_aamp_log(log: Path):
    if not hasattr(_convert_aamp_log, 'loader'):
        _convert_aamp_log.loader = yaml.CSafeLoader
        ayu.register_constructors(_convert_aamp_log.loader)
    log_yaml = yaml.load(
        log.read_text('utf-8'),
        Loader=_convert_aamp_log.loader
    )
    log.with_suffix('.json').write_text(
        json_util.aamp_to_json(log_yaml),
        encoding='utf-8'
    )
