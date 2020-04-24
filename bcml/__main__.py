import base64
import json
import sys
import traceback
import urllib
from contextlib import redirect_stderr, redirect_stdout
from importlib.util import find_spec
from multiprocessing import Pool, cpu_count, set_start_method
from pathlib import Path

import webview

from . import DEBUG, NO_CEF, install, dev, mergers, upgrade, util
from .util import BcmlMod, Messager, InstallError, MergeError

LOG = util.get_data_dir() / 'bcml.log'

def win_or_lose(func):
    def status_run(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except Exception as e:  # pylint: disable=bare-except
            err = getattr(e, 'error_text', '') or traceback.format_exc(limit=-5, chain=True)
            with LOG.open('a') as log_file:
                log_file.write(f'\n{err}\n')
            return {
                'error': err,
                'error_text': hasattr(err, 'error_text')
            }
        return {'success': True}
    return status_run


class Api:
    window: webview.Window

    @win_or_lose
    def sanity_check(self, kwargs = None):
        import platform
        ver = platform.python_version_tuple()
        if int(ver[0]) < 3 or (int(ver[0]) >= 3 and int(ver[1]) < 7):
            err = RuntimeError(
                f'BCML requires Python 3.7 or higher, but you have {ver[0]}.{ver[1]}'
            )
            err.error_text = f'BCML requires Python 3.7 or higher, but you have {ver[0]}.{ver[1]}'
            raise err
        is_64bits = sys.maxsize > 2**32
        if not is_64bits:
            err = RuntimeError(
                'BCML requires 64 bit Python, but you appear to be running 32 bit.'
            )
            err.error_text = 'BCML requires 64 bit Python, but you appear to be running 32 bit.'
            raise err
        settings = util.get_settings()
        util.get_game_dir()
        util.get_update_dir()
        if not settings['no_cemu']:
            util.get_cemu_dir()

    def get_folder(self):
        return self.window.create_file_dialog(webview.FOLDER_DIALOG)[0]

    def dir_exists(self, params):
        p = Path(params['folder'])
        real_folder = p.exists() and p.is_dir() and params['folder'] != ''
        if not real_folder:
            return False
        else:
            if params['type'] == 'cemu_dir':
                return len(list(p.glob('Cemu*.exe'))) > 0
            elif params['type'] == 'game_dir':
                return (p / 'Pack' / 'Dungeon000.pack').exists()
            elif params['type'] == 'update_dir':
                return len(list((p / 'Actor' / 'Pack').glob('*.sbactorpack'))) > 7000
            elif params['type'] == 'dlc_dir':
                return (p / 'Pack' / 'AocMainField.pack').exists()

    def get_settings(self, params = None):
        return util.get_settings()

    def save_settings(self, params):
        util.get_settings.settings = params['settings']
        util.save_settings()

    def old_settings(self):
        old = util.get_data_dir() / 'settings.ini'
        if old.exists():
            try:    
                upgrade.convert_old_settings()
                settings = util.get_settings()
                return {
                    'exists': True,
                    'message': 'Your old settings were converted successfully.',
                    'settings': settings
                }
            except:  # pylint: disable=bare-except
                return {
                    'exists': True,
                    'message': 'Your old settings could not be converted.'
                }
        else:
            return {
                'exists': False,
                'message': 'No old settings found.'
            }

    def get_old_mods(self):
        return len({
            d for d in (util.get_cemu_dir() / 'graphicPacks' / 'BCML').glob('*') if d.is_dir()
        })
    
    @win_or_lose
    def convert_old_mods(self):
        upgrade.convert_old_mods()

    @win_or_lose
    def delete_old_mods(self):
        from shutil import rmtree
        rmtree(util.get_cemu_dir() / 'graphicPacks' / 'BCML')

    def get_mods(self, params):
        if not params:
            params = { 'disabled': False }
        mods = [mod.to_json()
                for mod in util.get_installed_mods(params['disabled'])]
        util.vprint(mods)
        return mods

    def get_mod_info(self, params):
        mod = BcmlMod.from_json(params['mod'])
        util.vprint(mod)
        img = ''
        try:
            img = base64.b64encode(
                mod.get_preview().read_bytes()
            ).decode('utf8')
        except (KeyError, FileNotFoundError):
            pass
        return {
            'changes': [m.NAME.upper() for m in mergers.get_mergers() if m().is_mod_logged(mod)],
            'desc': mod.description,
            'image': img,
            'url': mod.url
        }

    def get_mergers(self):
        return [m().friendly_name for m in mergers.get_mergers()]

    def file_pick(self, params = None):
        if not params:
            params = {}
        return self.window.create_file_dialog(
            file_types=(
                'Packaged mods (*.bnp;*.7z;*.zip;*.rar)',
                'Mod meta (*.txt;*.json)'
            ),
            allow_multiple=True if not 'multiple' in params else params['multiple']
        ) or []
    
    def get_options(self):
        opts = []
        for m in mergers.get_mergers():
            m = m()
            opts.append({
                'name': m.NAME,
                'friendly': m.friendly_name,
                'options': {k: v for (k, v) in m.get_checkbox_options()}
            })
        return opts

    def get_backups(self):
        return [
            {'name': b[0][0], 'num': b[0][1], 'path': b[1]} for b in [
                (b.stem.split('---'), str(b)) for b in install.get_backups()
            ]
        ]

    def check_mod_options(self, params):
        metas = {
            mod: install.extract_mod_meta(Path(mod)) for mod in params['mods'] if mod.endswith('.bnp')
        }
        return {
            mod: meta for mod, meta in metas.items() if 'options' in meta and meta['options']
        }

    @win_or_lose
    def install_mod(self, params: dict):
        util.vprint(params)
        set_start_method('spawn', True)
        with Pool(cpu_count()) as pool:
            selects = params['selects'] if 'selects' in params and params['selects'] else {}
            mods = [
                install.install_mod(
                    Path(m),
                    options=params['options'],
                    selects=selects.get(m, None),
                    wait_merge=True,
                    pool=pool
                ) for m in params['mods']
            ]
            ms = {}
            try:
                for mod in mods:
                    for m in mergers.get_mergers_for_mod(mod):
                        ms[m] = None if not m.can_partial_remerge() else m.get_mod_affected(mod)
                for m in ms:
                    if ms[m] is not None:
                        m.set_options({'only_these': ms[m]})
                    m.set_pool(pool)
                    m.perform_merge()
                print('Install complete')
            except Exception as e:
                raise MergeError(e)

    def update_mod(self, params):
        try:
            update_file = self.file_pick({'multiple': False})[0]
        except IndexError:
            return
        from shutil import rmtree
        mod = BcmlMod.from_json(params['mod'])
        if (mod.path / 'options.json').exists():
            options = json.loads(
                (mod.path / 'options.json').read_text(),
                encoding='utf-8'
            )
        else:
            options = {}
        rmtree(mod.path)
        install.install_mod(
            Path(update_file),
            insert_priority=mod.priority,
            options=options, wait_merge=False
        )

    @win_or_lose
    def uninstall_all(self):
        from shutil import rmtree
        [rmtree(d) for d in util.get_modpack_dir().glob('*') if d.is_dir()]

    @win_or_lose
    def apply_queue(self, params):
        mods = []
        for m in params['moves']:
            mod = BcmlMod.from_json(m['mod'])
            mods.append(mod)
            mod.change_priority(m['priority'])
        for i in params['installs']:
            print(i)
            mods.append(
                install.install_mod(
                    Path(i['path'].replace('QUEUE', '')), 
                    options=i['options'],
                    insert_priority=i['priority'],
                    wait_merge=True
                )
            )
        set_start_method('spawn', True)
        with Pool(cpu_count()) as pool:
            print('Remerging where needed...')
            all_mergers = [merger() for merger in mergers.get_mergers()]
            remergers = set()
            partials = {}
            for mod in mods:
                for merger in all_mergers:
                    if merger.is_mod_logged(mod):
                        remergers.add(merger)
                        if merger.can_partial_remerge():
                            partials[merger.NAME] = set(merger.get_mod_affected(mod))
            for merger in mergers.sort_mergers(remergers):
                if merger.NAME in partials:
                    merger.set_options({'only_these': partials[merger.NAME]})
                merger.set_pool(pool)
                merger.perform_merge()
        install.refresh_master_export()

    @win_or_lose
    def mod_action(self, params):
        mod = BcmlMod.from_json(params['mod'])
        action = params['action']
        if action == 'enable':
            install.enable_mod(mod)
        elif action == 'disable':
            install.disable_mod(mod)
        elif action == 'uninstall':
            install.uninstall_mod(mod)
        elif action == 'update':
            self.update_mod(params)

    def explore(self, params):
        from platform import system
        from subprocess import Popen
        path = params['mod']['path']
        if system() == "Windows":
            from os import startfile  # pylint: disable=no-name-in-module
            startfile(path)
        elif system() == "Darwin":
            Popen(["open", path])
        else:
            Popen(["xdg-open", path])

    @win_or_lose
    def remerge(self, params):
        if params['name'] == 'all':
            install.refresh_merges()
        else:
            [
                m() for m in mergers.get_mergers() if m().friendly_name == params['name']
            ][0].perform_merge()
            install.refresh_master_export()

    @win_or_lose
    def create_backup(self, params):
        install.create_backup(params['backup'])

    @win_or_lose
    def restore_backup(self, params):
        install.restore_backup(params['backup'])

    @win_or_lose
    def delete_backup(self, params):
        Path(params['backup']).unlink()

    @win_or_lose
    def export(self):
        out = self.window.create_file_dialog(
            webview.SAVE_DIALOG,
            file_types=(
                'BOTW Nano Patch (*.bnp)',
                ('Graphic Pack' if util.get_settings('wiiu') else 'Atmosphere') + ' (*.zip)'
            )
        )
        output = Path(out[0])
        install.export(output)

    def get_option_folders(self, params):
        try:
            return [
                d.name for d in Path(params['mod']).glob('options/*') if d.is_dir()
            ]
        except FileNotFoundError:
            return []

    @win_or_lose
    def create_bnp(self, params):
        out = self.window.create_file_dialog(
            webview.SAVE_DIALOG,
            file_types=tuple(['BOTW Nano Patch (*.bnp)'])
        )
        meta = params.copy()
        del meta['folder']
        meta['options'] = params['selects']
        del meta['selects']
        dev.create_bnp_mod(
            mod=Path(params['folder']),
            output=Path(out[0]),
            meta=meta,
            options=params['options']
        )

    @win_or_lose
    def gen_rstb(self, params = None):
        try:
            mod = Path(self.get_folder())
            assert mod.exists()
        except (FileNotFoundError, IndexError, AssertionError):
            return
        from .mergers.rstable import generate_rstb_for_mod
        generate_rstb_for_mod(mod)


def main():
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        LOG.write_text('')
    except (FileNotFoundError, OSError, PermissionError):
        pass

    api = Api()

    url: str
    if (util.get_data_dir() / 'settings.json').exists():
        mods = urllib.parse.quote(
            json.dumps(
                api.get_mods({'disabled': True})
            )
        )
        url = str(util.get_exec_dir() / 'assets' / 'index.html') + f'?mods={mods}'
        w, h = 907, 680
    else:
        url = str(util.get_exec_dir() / 'assets' / 'index.html') + f'?firstrun=yes'
        w, h = 750, 600

    api.window = webview.create_window(
        'BOTW Cemu Mod Loader',
        url=url,
        js_api=api,
        text_select=DEBUG,
        width=w,
        height=h
    )

    no_cef = find_spec('cefpython3') is None or NO_CEF
    mods = util.get_installed_mods(True)

    with redirect_stderr(sys.stdout):
        with redirect_stdout(Messager(api.window)):
            webview.start(
                gui='' if no_cef else 'cef',
                debug=DEBUG if not no_cef else False,
                http_server=False
            )

if __name__ == "__main__":
    main()
