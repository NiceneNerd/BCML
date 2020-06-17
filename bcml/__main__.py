# fmt: off
try:
    import oead
    oead
except:
    from tkinter.messagebox import showerror
    showerror(
        "Dependency Error",
        "The latest (2019) Visual C++ redistributable for x64 is required to run BCML. "
        "Please download it from the following link and try again: \n"
        "https://aka.ms/vs/16/release/vc_redist.x64.exe",
    )
    exit(1)
# fmt: on

import base64
import json
import platform
import sys
import traceback
from contextlib import redirect_stderr, redirect_stdout
from multiprocessing import Pool, set_start_method
from os import chdir
from pathlib import Path
from platform import system
from subprocess import run, PIPE, Popen, DEVNULL
from shutil import rmtree
from time import sleep
from threading import Thread

try:
    from os import startfile  # pylint: disable=no-name-in-module
except ImportError:
    pass
import webview

from bcml import DEBUG, install, dev, mergers, upgrade, util, _oneclick
from bcml.util import BcmlMod, Messager
from bcml.mergers.rstable import generate_rstb_for_mod
from bcml.__version__ import USER_VERSION

LOG = util.get_data_dir() / "bcml.log"
SYSTEM = system()


def win_or_lose(func):
    def status_run(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except Exception as err:  # pylint: disable=broad-except
            with LOG.open("a") as log_file:
                log_file.write(f"\n{err}\n")
            return {"error": {"short": str(err), "error_text": traceback.format_exc(-5)}}
        return {"success": True}

    return status_run


class Api:
    # pylint: disable=unused-argument,no-self-use,too-many-public-methods
    window: webview.Window

    @win_or_lose
    def sanity_check(self, kwargs=None):
        ver = platform.python_version_tuple()
        if int(ver[0]) < 3 or (int(ver[0]) >= 3 and int(ver[1]) < 7):
            raise RuntimeError(
                f"BCML requires Python 3.7 or higher, but you have {ver[0]}.{ver[1]}"
            )
        is_64bits = sys.maxsize > 2 ** 32
        if not is_64bits:
            raise RuntimeError(
                "BCML requires 64 bit Python, but you appear to be running 32 bit."
            )
        settings = util.get_settings()
        util.get_game_dir()
        if settings["wiiu"]:
            util.get_update_dir()
        if not settings["no_cemu"]:
            util.get_cemu_dir()

    def get_folder(self):
        return self.window.create_file_dialog(webview.FOLDER_DIALOG)[0]

    def dir_exists(self, params):
        path = Path(params["folder"])
        real_folder = path.exists() and path.is_dir() and params["folder"] != ""
        if not real_folder:
            return False
        if params["type"] == "cemu_dir":
            return len(list(path.glob("?emu*.exe"))) > 0
        if "game_dir" in params["type"]:
            return (path / "Pack" / "Dungeon000.pack").exists()
        if params["type"] == "update_dir":
            return len(list((path / "Actor" / "Pack").glob("*.sbactorpack"))) > 7000
        if "dlc_dir" in params["type"]:
            return (path / "Pack" / "AocMainField.pack").exists()
        if params["type"] == "store_dir":
            return True
        return True

    def get_settings(self, params=None):
        return util.get_settings()

    def save_settings(self, params):
        old_cef = util.get_settings("use_cef")
        print("Saving settings, BCML will reload momentarily...")
        util.get_settings.settings = params["settings"]
        util.save_settings()
        if params["settings"]["use_cef"] and not util.can_cef():
            print(
                "Installing <code>cefpython3</code>, "
                "if BCML does not restart, launch it again manually"
            )
            self.install_cef()
        if params["settings"]["use_cef"] != old_cef:
            sleep(1)
            self.restart()

    def old_settings(self):
        old = util.get_data_dir() / "settings.ini"
        if old.exists():
            try:
                upgrade.convert_old_settings()
                settings = util.get_settings()
                return {
                    "exists": True,
                    "message": "Your old settings were converted successfully.",
                    "settings": settings,
                }
            except:  # pylint: disable=bare-except
                return {
                    "exists": True,
                    "message": "Your old settings could not be converted.",
                }
        else:
            return {"exists": False, "message": "No old settings found."}

    def get_old_mods(self):
        return len(
            {
                d
                for d in (util.get_cemu_dir() / "graphicPacks" / "BCML").glob("*")
                if d.is_dir()
            }
        )

    @win_or_lose
    def convert_old_mods(self):
        upgrade.convert_old_mods()

    @win_or_lose
    def delete_old_mods(self):
        rmtree(util.get_cemu_dir() / "graphicPacks" / "BCML")

    def get_mods(self, params):
        if not params:
            params = {"disabled": False}
        mods = [mod.to_json() for mod in util.get_installed_mods(params["disabled"])]
        util.vprint(mods)
        return mods

    def get_mod_info(self, params):
        mod = BcmlMod.from_json(params["mod"])
        util.vprint(mod)
        img = ""
        try:
            img = base64.b64encode(mod.get_preview().read_bytes()).decode("utf8")
        except (KeyError, FileNotFoundError):
            pass
        return {
            "changes": [
                m.NAME.upper() for m in mergers.get_mergers() if m().is_mod_logged(mod)
            ],
            "desc": mod.description,
            "image": img,
            "url": mod.url,
        }

    def get_setup(self):
        return {
            "hasCemu": not util.get_settings("no_cemu"),
            "mergers": [m().friendly_name for m in mergers.get_mergers()],
        }

    def file_pick(self, params=None):
        if not params:
            params = {}
        return (
            self.window.create_file_dialog(
                file_types=(
                    "All supported files (*.bnp;*.7z;*.zip;*.rar;*.txt;*.json)",
                    "Packaged mods (*.bnp;*.7z;*.zip;*.rar)",
                    "Mod meta (*.txt;*.json)",
                    "All files (*.*)",
                ),
                allow_multiple=True if "multiple" not in params else params["multiple"],
            )
            or []
        )

    def get_options(self):
        opts = [
            {
                "name": "general",
                "friendly": "general options",
                "options": {"agnostic": "Allow cross-platform install"},
            }
        ]
        for merger in mergers.get_mergers():
            merger = merger()
            opts.append(
                {
                    "name": merger.NAME,
                    "friendly": merger.friendly_name,
                    "options": dict(merger.get_checkbox_options()),
                }
            )
        return opts

    def get_backups(self):
        return [
            {"name": b[0][0], "num": b[0][1], "path": b[1]}
            for b in [(b.stem.split("---"), str(b)) for b in install.get_backups()]
        ]

    def check_mod_options(self, params):
        metas = {
            mod: install.extract_mod_meta(Path(mod))
            for mod in params["mods"]
            if mod.endswith(".bnp")
        }
        return {
            mod: meta
            for mod, meta in metas.items()
            if "options" in meta and meta["options"]
        }

    @win_or_lose
    @install.refresher
    def install_mod(self, params: dict):
        util.vprint(params)
        with Pool(maxtasksperchild=1000) as pool:
            selects = (
                params["selects"] if "selects" in params and params["selects"] else {}
            )
            mods = [
                install.install_mod(
                    Path(m),
                    options=params["options"],
                    selects=selects.get(m, None),
                    pool=pool,
                )
                for m in params["mods"]
            ]
            util.vprint(f"Installed {len(mods)} mods")
            print(f"Installed {len(mods)} mods")
            try:
                install.refresh_merges()
                print("Install complete")
            except Exception:  # pylint: disable=broad-except
                pool.terminate()
                raise

    @win_or_lose
    @install.refresher
    def update_mod(self, params):
        try:
            update_file = self.file_pick({"multiple": False})[0]
        except IndexError:
            return
        mod = BcmlMod.from_json(params["mod"])
        if (mod.path / "options.json").exists():
            options = json.loads(
                (mod.path / "options.json").read_text(), encoding="utf-8"
            )
        else:
            options = {}
        remergers = mergers.get_mergers_for_mod(mod)
        rmtree(mod.path)
        with Pool(maxtasksperchild=1000) as pool:
            new_mod = install.install_mod(
                Path(update_file),
                insert_priority=mod.priority,
                options=options,
                pool=pool,
            )
            remergers |= {
                m
                for m in mergers.get_mergers_for_mod(new_mod)
                if m.NAME not in {m.NAME for m in remergers}
            }
            try:
                install.refresh_merges()
            except Exception:  # pylint: disable=broad-except
                pool.terminate()
                raise

    @win_or_lose
    @install.refresher
    def uninstall_all(self):
        for folder in {d for d in util.get_modpack_dir().glob("*") if d.is_dir()}:
            rmtree(folder)

    @win_or_lose
    def apply_queue(self, params):
        mods = []
        for move_mod in params["moves"]:
            mod = BcmlMod.from_json(move_mod["mod"])
            mods.append(mod)
            mod.change_priority(move_mod["priority"])
        with Pool(maxtasksperchild=1000) as pool:
            for i in params["installs"]:
                print(i)
                mods.append(
                    install.install_mod(
                        Path(i["path"].replace("QUEUE", "")),
                        options=i["options"],
                        insert_priority=i["priority"],
                        pool=pool,
                    )
                )
                print("Remerging...")
                try:
                    install.refresh_merges()
                except Exception:  # pylint: disable=broad-except
                    pool.terminate()
                    raise
        install.refresh_master_export()

    @win_or_lose
    def mod_action(self, params):
        mod = BcmlMod.from_json(params["mod"])
        action = params["action"]
        if action == "enable":
            install.enable_mod(mod)
        elif action == "disable":
            install.disable_mod(mod)
        elif action == "uninstall":
            install.uninstall_mod(mod)
        elif action == "update":
            self.update_mod(params)

    def explore(self, params):
        path = params["mod"]["path"]
        if SYSTEM == "Windows":
            startfile(path)
        elif SYSTEM == "Darwin":
            run(["open", path], check=False)
        else:
            run(["xdg-open", path], check=False)

    def explore_master(self, params=None):
        path = util.get_master_modpack_dir()
        if SYSTEM == "Windows":
            startfile(path)
        elif SYSTEM == "Darwin":
            run(["open", path], check=False)
        else:
            run(["xdg-open", path], check=False)

    @win_or_lose
    def launch_game(self, params=None):
        cemu = next(
            iter(
                {f for f in util.get_cemu_dir().glob("*.exe") if "cemu" in f.name.lower()}
            )
        )
        uking = util.get_game_dir().parent / "code" / "U-King.rpx"
        try:
            assert uking.exists()
        except AssertionError:
            raise FileNotFoundError("Your BOTW executable could not be found")
        if SYSTEM == "Windows":
            cemu_args = [str(cemu), "-g", str(uking)]
        else:
            cemu_args = [
                "wine",
                str(cemu),
                "-g",
                "Z:\\" + str(uking).replace("/", "\\"),
            ]
        Popen(cemu_args, cwd=str(util.get_cemu_dir()))

    @win_or_lose
    @install.refresher
    def remerge(self, params):
        try:
            if not util.get_installed_mods():
                if util.get_master_modpack_dir().exists():
                    rmtree(util.get_master_modpack_dir())
                    install.link_master_mod()
                return
            if params["name"] == "all":
                install.refresh_merges()
            else:
                [
                    m()
                    for m in mergers.get_mergers()
                    if m().friendly_name == params["name"]
                ][0].perform_merge()
        except Exception as err:  # pylint: disable=broad-except
            raise Exception(
                f"There was an error merging your mods. {str(err)}\n"
                "Note that this could leave your game in an unplayable state."
            )

    @win_or_lose
    def create_backup(self, params):
        install.create_backup(params["backup"])

    @win_or_lose
    def restore_backup(self, params):
        install.restore_backup(params["backup"])

    @win_or_lose
    def delete_backup(self, params):
        Path(params["backup"]).unlink()

    @win_or_lose
    def export(self):
        if not util.get_installed_mods():
            raise Exception("No mods installed to export.")
        out = self.window.create_file_dialog(
            webview.SAVE_DIALOG,
            file_types=(
                f"{('Graphic Pack' if util.get_settings('wiiu') else 'Atmosphere')} (*.zip)",
                "BOTW Nano Patch (*.bnp)",
            ),
            save_filename="exported-mods.zip",
        )
        if out:
            output = Path(out if isinstance(out, str) else out[0])
            install.export(output)

    def get_option_folders(self, params):
        try:
            return [d.name for d in Path(params["mod"]).glob("options/*") if d.is_dir()]
        except FileNotFoundError:
            return []

    @win_or_lose
    def create_bnp(self, params):
        out = self.window.create_file_dialog(
            webview.SAVE_DIALOG,
            file_types=("BOTW Nano Patch (*.bnp)", "All files (*.*)"),
            save_filename=util.get_safe_pathname(params["name"]) + ".bnp",
        )
        if not out:
            raise Exception("canceled")
        meta = params.copy()
        del meta["folder"]
        meta["options"] = params["selects"]
        del meta["selects"]
        dev.create_bnp_mod(
            mod=Path(params["folder"]),
            output=Path(out if isinstance(out, str) else out[0]),
            meta=meta,
            options=params["options"],
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
        mod = BcmlMod.from_json(params["mod"])
        edits = {}
        merger_list = sorted({m() for m in mergers.get_mergers()}, key=lambda m: m.NAME)
        for merger in merger_list:
            edits[merger.friendly_name] = merger.get_mod_edit_info(mod)
        return {key: sorted({str(v) for v in value}) for key, value in edits.items()}

    @win_or_lose
    def upgrade_bnp(self, params=None):
        path = self.window.create_file_dialog(
            file_types=tuple(["BOTW Nano Patch (*.bnp)"])
        )
        if not path:
            return
        path = Path(path if isinstance(path, str) else path[0])
        if not path.exists():
            return
        tmp_dir = install.open_mod(path)
        output = self.window.create_file_dialog(
            webview.SAVE_DIALOG, file_types=tuple(["BOTW Nano Patch (*.bnp)"])
        )
        if not output:
            return
        output = Path(output[0])
        print(f"Saving output file to {str(output)}...")
        x_args = [install.ZPATH, "a", str(output), f'{str(tmp_dir / "*")}']
        if SYSTEM == "Windows":
            run(
                x_args,
                stdout=PIPE,
                stderr=PIPE,
                creationflags=util.CREATE_NO_WINDOW,
                check=True,
            )
        else:
            run(x_args, stdout=PIPE, stderr=PIPE, check=True)

    def open_help(self):
        help_thread = Thread(target=help_window)
        help_thread.start()

    @win_or_lose
    def update_bcml(self):
        run(
            [
                util.get_python_exe(),
                "-m",
                "pip",
                "install",
                "--upgrade",
                "--pre" if DEBUG else "",
                "bcml",
            ],
            check=True,
            stdout=PIPE,
            stderr=PIPE,
        )

    @win_or_lose
    def install_cef(self):
        run(
            [util.get_python_exe(), "-m", "pip", "install", "cefpython3",],
            check=True,
            stdout=PIPE,
            stderr=PIPE,
        )

    def restart(self):
        opener = Thread(target=start_new_instance)
        opener.start()
        for win in webview.windows:
            win.destroy()

    def get_version(self):
        return USER_VERSION


def start_new_instance():
    sleep(0.33)
    Popen([util.get_python_exe(), "-m", "bcml"], cwd=str(Path().resolve()))


def help_window():
    webview.create_window("BCML Help", url=f"{util.get_url_base()}/help.html?page=main")


def stop_it(messager: Messager = None):
    if messager:
        messager.save()
    try:
        del globals()["logger"]
    except KeyError:
        pass
    if SYSTEM == "Windows" and util.get_settings("use_cef"):
        Popen(
            "taskkill /F /IM subprocess.exe /T".split(),
            stdout=DEVNULL,
            stderr=DEVNULL,
            creationflags=0x08000000,
        )
        rmtree(Path() / "blob_storage", ignore_errors=True)
        rmtree(Path() / "webrtc_event_logs", ignore_errors=True)
        return


def main(debug: bool = False):
    set_start_method("spawn", True)
    globals()["logger"] = None
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        LOG.write_text("")
        for folder in util.get_work_dir().glob("*"):
            rmtree(folder)
    except (FileNotFoundError, OSError, PermissionError):
        pass

    _oneclick.register_handlers()
    oneclick = Thread(target=_oneclick.listen)
    oneclick.daemon = True
    oneclick.start()

    api = Api()

    gui: str = ""
    if SYSTEM == "Windows" and util.get_settings("use_cef") and util.can_cef():
        gui = "cef"
    elif SYSTEM == "Linux":
        gui = "qt"

    base = util.get_url_base()
    if (util.get_data_dir() / "settings.json").exists():
        url = f"{base}/index.html"
        width, height = 907, 680
    else:
        url = f"{base}/index.html?firstrun=yes"
        width, height = 750, 600

    api.window = webview.create_window(
        "BOTW Cross-Platform Mod Loader",
        url=url,
        js_api=api,
        text_select=DEBUG,
        width=width,
        height=height,
        min_size=(width if width == 750 else 820, 600),
    )
    globals()["logger"] = Messager(api.window)
    api.window.closing += stop_it

    if not debug:
        debug = DEBUG or "bcml-debug" in sys.argv

    messager = Messager(api.window)
    with redirect_stderr(sys.stdout):
        with redirect_stdout(messager):
            webview.start(
                gui=gui, debug=debug, http_server=True, func=_oneclick.process_arg
            )
    stop_it(messager=messager)


def main_debug():
    main(True)


if __name__ == "__main__":
    main()
