import base64
import json
import platform
import sys
import traceback
import urllib
from contextlib import redirect_stderr, redirect_stdout
from importlib.util import find_spec
from multiprocessing import Pool, cpu_count, set_start_method
from pathlib import Path
from platform import system
from shutil import rmtree
from subprocess import Popen, run, PIPE

import webview

from . import DEBUG, NO_CEF, install, dev, mergers, upgrade, util
from .util import BcmlMod, Messager, MergeError
from .mergers.rstable import generate_rstb_for_mod

LOG = util.get_data_dir() / 'bcml.log'

def win_or_lose(func):
    def status_run(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except Exception as err:  # pylint: disable=broad-except
            setattr(
                err,
                'error_text',
                getattr(err, 'error_text', traceback.format_exc(limit=-5, chain=True))
            )
            with LOG.open('a') as log_file:
                log_file.write(f'\n{err}\n')
            return {
                'error': getattr(err, 'error_text'),
                'error_text': hasattr(err, 'error_text')
            }
        return {'success': True}
    return status_run


class Api:
    # pylint: disable=unused-argument
    window: webview.Window

    @win_or_lose
    def sanity_check(self, kwargs=None):
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
        if settings['wiiu']:
            util.get_update_dir()
        if not settings['no_cemu']:
            util.get_cemu_dir()

    def get_folder(self):
        return self.window.create_file_dialog(webview.FOLDER_DIALOG)[0]

    def dir_exists(self, params):
        path = Path(params['folder'])
        real_folder = path.exists() and path.is_dir() and params['folder'] != ''
        if not real_folder:
            return False
        else:
            if params['type'] == 'cemu_dir':
                return len(list(path.glob('Cemu*.exe'))) > 0
            elif params['type'] == 'game_dir':
                return (path / 'Pack' / 'Dungeon000.pack').exists()
            elif params['type'] == 'update_dir':
                return len(list((path / 'Actor' / 'Pack').glob('*.sbactorpack'))) > 7000
            elif params['type'] == 'dlc_dir':
                return (path / 'Pack' / 'AocMainField.pack').exists()

    def get_settings(self, params=None):
        return util.get_settings()

    def save_settings(self, params):
        print('Saving settings, BCML will reload momentarily...')
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
        rmtree(util.get_cemu_dir() / 'graphicPacks' / 'BCML')

    def get_mods(self, params):
        if not params:
            params = {'disabled': False}
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

    def get_setup(self):
        return {
            'hasCemu': not util.get_settings('no_cemu'),
            'mergers': [m().friendly_name for m in mergers.get_mergers()]
        }

    def file_pick(self, params=None):
        if not params:
            params = {}
        return self.window.create_file_dialog(
            file_types=(
                'All supported files (*.bnp;*.7z;*.zip;*.rar;*.txt;*.json)',
                'Packaged mods (*.bnp;*.7z;*.zip;*.rar)',
                'Mod meta (*.txt;*.json)',
                'All files (*.*)'
            ),
            allow_multiple=True if 'multiple' not in params else params['multiple']
        ) or []

    def get_options(self):
        opts = [{
            'name': 'general',
            'friendly': 'general options',
            'options': {'agnostic': 'Allow cross-platform install'}
        }]
        for merger in mergers.get_mergers():
            merger = merger()
            opts.append({
                'name': merger.NAME,
                'friendly': merger.friendly_name,
                'options': {k: v for (k, v) in merger.get_checkbox_options()}
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
            mod: install.extract_mod_meta(Path(mod)) for mod in params['mods']\
                if mod.endswith('.bnp')
        }
        return {
            mod: meta for mod, meta in metas.items() if 'options' in meta and meta['options']
        }

    @win_or_lose
    @install.refresher
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
                    pool=pool
                ) for m in params['mods']
            ]
            util.vprint(f'Installed {len(mods)} mods')
            print(f'Installed {len(mods)} mods')
            merger_set = {}
            try:
                for mod in mods:
                    for merger in mergers.get_mergers_for_mod(mod):
                        merger_set[merger] = (
                            None if not merger.can_partial_remerge()\
                                 else merger.get_mod_affected(mod)
                        )
                util.vprint('')
                util.vprint({m.NAME: merger_set[m] for m in merger_set if merger_set[m]})
                for merger in merger_set:
                    if merger_set[merger] is not None:
                        merger.set_options({'only_these': merger_set[merger]})
                    merger.set_pool(pool)
                    merger.perform_merge()
                print('Install complete')
            except Exception as err: # pylint: disable=broad-except
                raise MergeError(err)

    @win_or_lose
    @install.refresher
    def update_mod(self, params):
        try:
            update_file = self.file_pick({'multiple': False})[0]
        except IndexError:
            return
        mod = BcmlMod.from_json(params['mod'])
        if (mod.path / 'options.json').exists():
            options = json.loads(
                (mod.path / 'options.json').read_text(),
                encoding='utf-8'
            )
        else:
            options = {}
        remergers = mergers.get_mergers_for_mod(mod)
        rmtree(mod.path)
        new_mod = install.install_mod(
            Path(update_file),
            insert_priority=mod.priority,
            options=options
        )
        remergers.extend([m for m in mergers.get_mergers_for_mod(new_mod) if m not in remergers])
        with Pool() as pool:
            for merger in remergers:
                merger.set_pool(pool)
                merger.perform_merge()

    @win_or_lose
    @install.refresher
    def uninstall_all(self):
        for folder in {d for d in util.get_modpack_dir().glob('*') if d.is_dir()}:
            rmtree(folder)

    @win_or_lose
    @install.refresher
    def apply_queue(self, params):
        mods = []
        for move_mod in params['moves']:
            mod = BcmlMod.from_json(move_mod['mod'])
            mods.append(mod)
            mod.change_priority(move_mod['priority'])
        for i in params['installs']:
            print(i)
            mods.append(
                install.install_mod(
                    Path(i['path'].replace('QUEUE', '')),
                    options=i['options'],
                    insert_priority=i['priority']
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
        path = params['mod']['path']
        if system() == "Windows":
            from os import startfile  # pylint: disable=no-name-in-module,import-outside-toplevel
            startfile(path)
        elif system() == "Darwin":
            run(["open", path], check=False)
        else:
            run(["xdg-open", path], check=False)

    def explore_master(self, params=None):
        path = util.get_master_modpack_dir()
        if system() == "Windows":
            from os import startfile  # pylint: disable=no-name-in-module,import-outside-toplevel
            startfile(path)
        elif system() == "Darwin":
            run(["open", path], check=False)
        else:
            run(["xdg-open", path], check=False)

    @win_or_lose
    def launch_game(self, params=None):
        cemu = next(iter(
            {f for f in util.get_cemu_dir().glob('*.exe') if 'cemu' in f.name.lower()}
        ))
        uking = util.get_game_dir().parent / 'code' / 'U-King.rpx'
        try:
            assert uking.exists()
        except AssertionError:
            raise FileNotFoundError('Your BOTW executable could not be found')
        if system() == 'Windows':
            cemu_args = [str(cemu), '-g', str(uking)]
        else:
            cemu_args = ['wine', str(cemu), '-g', 'Z:\\' + str(uking).replace('/', '\\')]
        run(cemu_args, cwd=str(util.get_cemu_dir()), check=False)

    @win_or_lose
    def remerge(self, params):
        try:
            if params['name'] == 'all':
                install.refresh_merges()
            else:
                [
                    m() for m in mergers.get_mergers() if m().friendly_name == params['name']
                ][0].perform_merge()
                install.refresh_master_export()
        except Exception as err: # pylint: disable=broad-except
            raise MergeError(err)

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
                f"{('Graphic Pack' if util.get_settings('wiiu') else 'Atmosphere')} (*.zip)",
                'BOTW Nano Patch (*.bnp)'
            ),
            save_filename='exported-mods.zip'
        )
        if out:
            output = Path(out[0] if isinstance(out, list) else out)
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
            output=Path(out[0] if isinstance(out, list) else out),
            meta=meta,
            options=params['options']
        )

    @win_or_lose
    def gen_rstb(self, params=None):
        try:
            mod = Path(self.get_folder())
            assert mod.exists()
        except (FileNotFoundError, IndexError, AssertionError):
            return
        generate_rstb_for_mod(mod)

    def get_mod_edits(self, params=None):
        mod = BcmlMod.from_json(params['mod'])
        edits = {}
        merger_list = sorted({m() for m in mergers.get_mergers()}, key=lambda m: m.NAME)
        for merger in merger_list:
            edits[merger.friendly_name] = merger.get_mod_edit_info(mod)
        return {
            key: sorted({str(v) for v in value}) for key, value in edits.items()
        }

    @win_or_lose
    def upgrade_bnp(self, params=None):
        path = self.window.create_file_dialog(file_types=tuple(['BOTW Nano Patch (*.bnp)']))
        if not path:
            return
        path = Path(path[0])
        if not path.exists():
            return
        tmp_dir = install.open_mod(path)
        output = self.window.create_file_dialog(
            webview.SAVE_DIALOG,
            file_types=tuple(['BOTW Nano Patch (*.bnp)'])
        )
        if not output:
            return
        output = Path(output[0])
        print(f'Saving output file to {str(output)}...')
        x_args = [install.ZPATH, 'a', str(output), f'{str(tmp_dir / "*")}']
        if system() == 'Windows':
            run(
                x_args,
                stdout=PIPE,
                stderr=PIPE,
                creationflags=util.CREATE_NO_WINDOW,
                check=True
            )
        else:
            run(x_args, stdout=PIPE, stderr=PIPE, check=True)


def main():
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        LOG.write_text('')
        for folder in util.get_work_dir().glob('*'):
            rmtree(folder)
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
        url = 'assets/index.html' #str(util.get_exec_dir() / 'assets' / 'index.html') + f'?mods={mods}'
        width, height = 907, 680
    else:
        url = 'assets/index.html?firstrun=yes' #str(util.get_exec_dir() / 'assets' / 'index.html') + f'?firstrun=yes'
        width, height = 750, 600

    api.window = webview.create_window(
        'BOTW Cemu Mod Loader',
        url=url,
        js_api=api,
        text_select=DEBUG,
        width=width,
        height=height,
        min_size=(width if width == 750 else 820, 600)
    )

    no_cef = find_spec('cefpython3') is None or NO_CEF
    gui: str = ''
    if system() == 'Windows' and not no_cef:
        gui = 'cef'
    elif system() == 'Linux':
        gui = 'qt'

    with redirect_stderr(sys.stdout):
        with redirect_stdout(Messager(api.window)):
            webview.start(
                gui=gui,
                debug=DEBUG if not no_cef else False,
                http_server=True
            )

if __name__ == "__main__":
    main()
