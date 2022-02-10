import base64
import json
import os
import shutil
import sys
import tempfile
import traceback
from math import ceil
from multiprocessing import Pool
from operator import itemgetter
from pathlib import Path
from platform import system
from subprocess import run, PIPE, Popen
from shutil import copytree, rmtree, copyfile
from tempfile import NamedTemporaryFile, mkdtemp
from time import sleep
from threading import Thread
from typing import List
from xml.dom import minidom

import requests
import webview

from bcml import DEBUG, install, dev, mergers, upgrade, util
from bcml.gamebanana import GameBananaDb
from bcml.util import BcmlMod, LOG, SYSTEM, get_7z_path
from bcml.__version__ import USER_VERSION, VERSION


def win_or_lose(func):
    def status_run(*args, **kwargs):
        try:
            data = func(*args, **kwargs)
        except Exception as err:  # pylint: disable=broad-except
            with LOG.open("a") as log_file:
                log_file.write(f"\n{err}\n")
            return {
                "error": {"short": str(err), "error_text": traceback.format_exc(-5)}
            }
        return {"success": True, "data": data}

    return status_run


def start_new_instance():
    sleep(0.33)
    Popen(
        [sys.executable.replace("python.exe", "pythonw.exe"), "-m", "bcml"],
        cwd=str(Path().resolve()),
    )


def help_window(host: str):
    webview.create_window("BCML Help", url=f"{host}/help/")


class Api:
    # pylint: disable=unused-argument,no-self-use,too-many-public-methods
    window: webview.Window
    host: str
    gb_api: GameBananaDb
    tmp_files: List[Path]

    def __init__(self, host: str):
        self.host = host
        self.tmp_files = []

    def get_ver(self, params=None):
        updated = util.get_settings("last_version") < VERSION
        res = {
            "version": USER_VERSION,
            "update": (
                util.get_latest_bcml() > VERSION
                and not util.get_settings("suppress_update")
            ),
            "showChangelog": updated and util.get_settings("changelog"),
        }
        if updated:
            util.get_settings()["last_version"] = VERSION
            util.save_settings()
        return res

    @win_or_lose
    def sanity_check(self, kwargs=None):
        util.sanity_check()

    def get_folder(self):
        if SYSTEM == "Windows":
            from tkinter import filedialog
            from tkinter import Tk

            root = Tk()
            root.attributes("-alpha", 0.0)
            folder = filedialog.askdirectory(parent=root)
            return folder if folder != "" else None
        else:
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

    def drill_dir(self, params):
        folder = Path(params["folder"])
        if not folder.exists():
            return params["folder"]
        folder = folder.parent
        if "game_dir" in params["type"]:
            targets: List[Path] = list(folder.rglob("**/Pack/Dungeon000.pack"))
            if targets:
                return str(targets[0].parent.parent)
        elif "update_dir" in params["type"]:
            targets: List[Path] = list(
                folder.rglob("**/Pack/ActorObserverByActorTagTag.sbactorpack")
            )
            if targets:
                return str(targets[0].parent.parent.parent)
        elif "dlc_dir" in params["type"]:
            targets: List[Path] = list(folder.rglob("**/Pack/AocMainField.pack"))
            if targets:
                return str(targets[0].parent.parent)
        return params["folder"]

    def parse_cemu_settings(self, params):
        try:
            cemu = Path(params["folder"])
            set_path = cemu / "settings.xml"
            settings: minidom = util.parse_cemu_settings(set_path)
            game_dir: Path
            for entry in settings.getElementsByTagName("GameCache")[
                0
            ].getElementsByTagName("Entry"):
                entry: minidom.Element
                path = entry.getElementsByTagName("path")[0].childNodes[0].data
                if "U-King" in path:
                    game_dir = Path(path).parent.parent / "content"
                    break
            if not game_dir:
                return {}
            mlc_path = Path(
                settings.getElementsByTagName("mlc_path")[0].childNodes[0].data
            )
            update_dir = util.guess_update_dir(mlc_path, game_dir)
            dlc_dir = util.guess_aoc_dir(mlc_path, game_dir)
            return {
                "game_dir": str(game_dir),
                "update_dir": str(update_dir) if update_dir else "",
                "dlc_dir": str(dlc_dir) if dlc_dir else "",
                "export_dir": str(cemu / "graphicPacks" / "BreathOfTheWild_BCML"),
            }
        except Exception as err:  # pylint: disable=broad-except
            print(err)
            return {}

    def get_settings(self, params=None):
        return util.get_settings()

    @win_or_lose
    def make_shortcut(self, params):
        util.create_shortcuts(params["desktop"], not params["desktop"])

    def get_user_langs(self, params):
        if params["dir"] and Path(params["dir"]).exists():
            return list(util.get_user_languages(Path(params["dir"])))
        else:
            return []

    def save_settings(self, params):
        print("Saving settings, BCML will reload momentarily...")
        if util.get_settings("wiiu") != params["settings"]["wiiu"]:
            util.clear_all_caches()
            if hasattr(self, "gb_api"):
                self.gb_api.reset_update_time(params["settings"]["wiiu"])
                del self.gb_api
                self.gb_api = GameBananaDb()
        util.get_settings.settings = params["settings"]
        util.save_settings()

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

    @win_or_lose
    def get_mods(self, params):
        if not params:
            params = {"disabled": False}
        mods = [mod.to_json() for mod in util.get_installed_mods(params["disabled"])]
        util.vprint(mods)
        return mods

    def save_mod_list(self, params=None):
        result = self.window.create_file_dialog(
            webview.SAVE_DIALOG,
            file_types=("JSON File (*.json)",),
            allow_multiple=False,
        )
        if not result:
            return
        out = Path(result if isinstance(result, str) else result[0])
        out.write_text(
            json.dumps(
                [mod.to_json() for mod in util.get_installed_mods(disabled=True)],
                indent=4,
            )
        )

    def get_mod_info(self, params):
        mod = BcmlMod.from_json(params["mod"])
        util.vprint(mod)
        img = ""
        try:
            img = base64.b64encode(mod.get_preview().read_bytes()).decode("utf8")
        except:  # pylint: disable=bare-except
            pass
        return {
            "changes": [
                m.NAME.upper() for m in mergers.get_mergers() if m().is_mod_logged(mod)
            ],
            "desc": mod.description,
            "date": mod.date,
            "processed": (mod.path / ".processed").exists(),
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
        result = self.window.create_file_dialog(
            file_types=params.get(
                "types",
                (
                    "All supported files (*.bnp;*.7z;*.zip;*.rar;*.txt;*.json)",
                    "Packaged mods (*.bnp;*.7z;*.zip;*.rar)",
                    "Mod meta (*.txt;*.json)",
                    "All files (*.*)",
                ),
            ),
            allow_multiple=params.get("multiple", True),
        )
        return result or []

    def file_drop(self, params):
        file = Path(tempfile.mkdtemp()) / params["file"]
        file.write_bytes(base64.b64decode(params["data"]))
        return str(file)

    def get_options(self):
        opts = [
            {
                "name": "general",
                "friendly": "general options",
                "options": {"base_priority": "Default to lowest priority"},
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

    def get_profiles(self):
        return [
            {"name": (d / ".profile").read_text("utf-8"), "path": str(d)}
            for d in {d for d in util.get_profiles_dir().glob("*") if d.is_dir()}
        ]

    def get_current_profile(self):
        profile = util.get_modpack_dir() / ".profile"
        if not (util.get_modpack_dir() / ".profile").exists():
            profile.write_text("Default")
            return "Default"
        return profile.read_text("utf-8")

    @win_or_lose
    @install.refresher
    def set_profile(self, params):
        mod_dir = util.get_modpack_dir()
        rmtree(mod_dir)
        copytree(params["profile"], mod_dir)

    @win_or_lose
    def delete_profile(self, params):
        rmtree(params["profile"])

    @win_or_lose
    def save_profile(self, params):
        mod_dir = util.get_modpack_dir()
        profile = mod_dir / ".profile"
        profile.write_text(params["profile"])
        profile_dir = util.get_profiles_dir() / util.get_safe_pathname(
            params["profile"]
        )
        if profile_dir.exists():
            rmtree(profile_dir)
        copytree(mod_dir, profile_dir)

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
        with Pool(maxtasksperchild=500) as pool:
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

    def update_mod(self, params):
        try:
            update_file = self.file_pick({"multiple": False})[0]
        except IndexError:
            raise Exception("canceled")
        mod = BcmlMod.from_json(params["mod"])
        if (mod.path / "options.json").exists():
            options = json.loads((mod.path / "options.json").read_text())
        else:
            options = {}
        rmtree(mod.path)
        with Pool(maxtasksperchild=500) as pool:
            new_mod = install.install_mod(
                Path(update_file),
                insert_priority=mod.priority,
                options=options,
                pool=pool,
                updated=True,
            )

    @win_or_lose
    def reprocess(self, params):
        mod = BcmlMod.from_json(params["mod"])
        rmtree(mod.path / "logs")
        if (mod.path / "options.json").exists():
            options = json.loads((mod.path / "options.json").read_text())
        else:
            options = {}
        install.generate_logs(mod.path, options)

    @win_or_lose
    @install.refresher
    def uninstall_all(self):
        for folder in {d for d in util.get_modpack_dir().glob("*") if d.is_dir()}:
            rmtree(folder, onerror=install.force_del)
        if not util.get_settings("no_cemu"):
            shutil.rmtree(
                util.get_cemu_dir() / "graphicPacks" / "bcmlPatches", ignore_errors=True
            )

    @win_or_lose
    def apply_queue(self, params):
        mods = []
        for move_mod in params["moves"]:
            mod = BcmlMod.from_json(move_mod["mod"])
            mods.append(mod)
            mod.change_priority(move_mod["priority"])
        with Pool(maxtasksperchild=500) as pool:
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
            install.enable_mod(mod, wait_merge=True)
        elif action == "disable":
            install.disable_mod(mod, wait_merge=True)
        elif action == "uninstall":
            install.uninstall_mod(mod, wait_merge=True)
        elif action == "update":
            self.update_mod(params)
        elif action == "reprocess":
            self.reprocess(params)

    def explore(self, params):
        path = params["mod"]["path"]
        if SYSTEM == "Windows":
            os.startfile(path)
        elif SYSTEM == "Darwin":
            run(["open", path], check=False)
        else:
            run(["xdg-open", path], check=False)

    def explore_master(self, params=None):
        path = util.get_master_modpack_dir()
        if SYSTEM == "Windows":
            os.startfile(path)
        elif SYSTEM == "Darwin":
            run(["open", path], check=False)
        else:
            run(["xdg-open", path], check=False)

    @win_or_lose
    def launch_game(self, params=None):
        install.enable_bcml_gfx()
        self.launch_cemu()

    @win_or_lose
    def launch_game_no_mod(self, params=None):
        install.disable_bcml_gfx()
        self.launch_cemu()

    @win_or_lose
    def launch_cemu(self, params=None):
        if not params:
            params = {"run_game": True}
        cemu = next(
            iter(
                {
                    f
                    for f in util.get_cemu_dir().glob("*.exe")
                    if "cemu" in f.name.lower()
                }
            )
        )
        uking = util.get_game_dir().parent / "code" / "U-King.rpx"
        try:
            assert uking.exists()
        except AssertionError:
            raise FileNotFoundError("Your BOTW executable could not be found")
        cemu_args: List[str]
        if SYSTEM == "Windows":
            cemu_args = [str(cemu)]
            if params["run_game"]:
                cemu_args.extend(("-g", str(uking)))
        else:
            cemu_args = ["wine", str(cemu)]
            if params["run_game"]:
                cemu_args.extend(
                    (
                        "-g",
                        "Z:\\" + str(uking).replace("/", "\\"),
                    )
                )
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
    @install.refresher
    def restore_old_backup(self, params=None):
        if (util.get_cemu_dir() / "bcml_backups").exists():
            open_dir = util.get_cemu_dir() / "bcml_backups"
        else:
            open_dir = Path.home()
        try:
            file = Path(
                self.window.create_file_dialog(
                    directory=str(open_dir),
                    file_types=("BCML Backups (*.7z)", "All Files (*.*)"),
                )[0]
            )
        except IndexError:
            return
        tmp_dir = Path(mkdtemp())
        x_args = [get_7z_path(), "x", str(file), f"-o{str(tmp_dir)}", "-aoa"]
        if system() == "Windows":
            run(
                x_args,
                capture_output=True,
                creationflags=util.CREATE_NO_WINDOW,
                check=True,
            )
        else:
            run(x_args, capture_output=True, check=True)
        upgrade.convert_old_mods(tmp_dir)

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
        meta["options"] = params.get("selects", {})
        if "selects" in meta:
            del meta["selects"]
        dev.create_bnp_mod(
            mod=Path(params["folder"]),
            output=Path(out if isinstance(out, str) else out[0]),
            meta=meta,
            options=params["options"],
        )

    def select_bnp_with_meta(self, params=None):
        file = self.file_pick(
            {"types": ("BOTW Nano Patch (*.bnp)",), "multiple": False}
        )
        if file:
            return {"file": file[0], "meta": install.extract_mod_meta(Path(file[0]))}
        return

    @win_or_lose
    def convert_bnp(self, params) -> List[str]:
        bnp = Path(params["mod"])
        mod = install.open_mod(bnp)
        warnings = dev.convert_mod(mod, params["wiiu"], params["warn"])
        out = self.window.create_file_dialog(
            webview.SAVE_DIALOG,
            file_types=("BOTW Nano Patch (*.bnp)", "All files (*.*)"),
            save_filename=bnp.stem + f"_{'wiiu' if params['wiiu'] else 'switch'}.bnp",
        )
        if not out:
            raise Exception("canceled")
        x_args = [
            util.get_7z_path(),
            "a",
            out if isinstance(out, str) else out[0],
            f'{str(mod / "*")}',
        ]
        if system() == "Windows":
            result = run(
                x_args,
                capture_output=True,
                universal_newlines=True,
                creationflags=util.CREATE_NO_WINDOW,
                check=False,
            )
        else:
            result = run(
                x_args, capture_output=True, universal_newlines=True, check=False
            )
        if result.stderr:
            raise RuntimeError(result.stderr)
        rmtree(mod, ignore_errors=True)
        return warnings

    def get_existing_meta(self, params):
        path = Path(params["path"])
        if (path / "info.json").exists():
            return json.loads((path / "info.json").read_text("utf-8"))
        if (path / "rules.txt").exists():
            return upgrade.parse_rules(path / "rules.txt")
        return {}

    @win_or_lose
    def gen_rstb(self, params=None):
        try:
            mod = Path(self.get_folder())
            assert mod.exists()
        except (FileNotFoundError, IndexError, AssertionError):
            return
        with util.TempModContext():
            if not ((mod / "info.json").exists() or (mod / "rules.txt").exists()):
                (mod / "info.json").write_text(
                    json.dumps(
                        {
                            "name": "Temp",
                            "desc": "Temp pack",
                            "url": "",
                            "id": "VGVtcD0wLjA=",
                            "image": "",
                            "version": "1.0.0",
                            "depends": [],
                            "options": {},
                            "platform": "wiiu"
                            if util.get_settings("wiiu")
                            else "switch",
                        }
                    )
                )
            install.install_mod(
                mod,
                merge_now=True,
                options={
                    "options": {},
                    "disable": [
                        m.NAME for m in mergers.get_mergers() if m.NAME != "rstb"
                    ],
                },
            )
            (mod / util.get_content_path() / "System" / "Resource").mkdir(
                parents=True, exist_ok=True
            )
            copyfile(
                util.get_master_modpack_dir()
                / util.get_content_path()
                / "System"
                / "Resource"
                / "ResourceSizeTable.product.srsizetable",
                mod
                / util.get_content_path()
                / "System"
                / "Resource"
                / "ResourceSizeTable.product.srsizetable",
            )

    @win_or_lose
    def bnp_to_gfx(self, params=None):
        try:
            bnp = Path(self.file_pick({"multiple": False})[0])
        except IndexError:
            return
        with util.TempModContext():
            install.install_mod(
                bnp,
                merge_now=True,
                options={"options": {"texts": {"all_langs": True}}, "disable": []},
            )
            out = self.window.create_file_dialog(
                webview.SAVE_DIALOG,
                file_types=(
                    f"{('Graphic Pack' if util.get_settings('wiiu') else 'Atmosphere')} (*.zip)",
                    "BOTW Nano Patch (*.bnp)",
                ),
                save_filename=f"{bnp.stem}.zip",
            )
            if out:
                output = Path(out if isinstance(out, str) else out[0])
                install.export(output, standalone=True)

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
        output = Path(output if isinstance(output, str) else output[0])
        print(f"Saving output file to {str(output)}...")
        x_args = [util.get_7z_path(), "a", str(output), f'{str(tmp_dir / "*")}']
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
        help_thread = Thread(target=help_window, args=(self.host,))
        help_thread.start()

    @win_or_lose
    def update_bcml(self):
        exe = str(util.get_python_exe(False))
        args = [
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-warn-script-location",
            "--upgrade",
            "bcml",
        ]
        if DEBUG:
            args.insert(-2, "--pre")
        if SYSTEM == "Windows":
            with NamedTemporaryFile("w", suffix=".bat", delete=False) as updater:
                updater.write(
                    "@echo off\n"
                    'taskkill /fi "WINDOWTITLE eq BOTW Cross-Platform Mod Loader"\n'
                    f"\"{exe}\" {' '.join(args)}\n"
                    "echo Finished updating, will launch BCML in a moment!\n"
                    "timeout 2 >nul 2>&1\n"
                    f'start "" "{str(util.get_python_exe(True))}" -m bcml\n'
                )
                file = updater.name
            os.system(f"timeout 2 >nul 2>&1 && start cmd /c {file}")
        else:
            with NamedTemporaryFile("w", suffix=".sh", delete=False) as updater:
                updater.write(
                    "#!/usr/bin/bash\n"
                    "sleep 2\n"
                    f"\"{exe}\" {' '.join(args)}\n"
                    "echo Finished updating, will launch BCML in a moment!\n"
                    f"{exe} -m bcml"
                )
                file = updater.name
            Popen(["/bin/sh", file], start_new_session=True)
        for win in webview.windows:
            win.destroy()

    def restart(self):
        opener = Thread(target=start_new_instance)
        opener.start()
        for win in webview.windows:
            win.destroy()

    def is_wiiu(self):
        return util.get_settings("wiiu")

    @win_or_lose
    def init_gb(self):
        self.gb_api = GameBananaDb()
        if util.get_settings("auto_gb"):
            self.gb_api.update_db()

    @win_or_lose
    def update_gb(self):
        self.gb_api.update_db()

    def get_gb_pages(self, category: str = None, search: str = None) -> int:
        mods = self.gb_api.mods
        if search:
            mods = self.gb_api.search(search)
            mods = mods[0] + mods[1]
        return ceil(
            len(
                mods if not category else [m for m in mods if m["category"] == category]
            )
            / 24
        )

    def get_gb_mods(
        self, page: int, sort: str = "new", category: str = None, search: str = None
    ):
        mods = self.gb_api.mods
        key = {
            "new": itemgetter("updated"),
            "old": itemgetter("updated"),
            "down": itemgetter("downloads"),
            "abc": itemgetter("name"),
            "likes": itemgetter("likes"),
        }.get(sort)
        if not search:
            mods = sorted(
                mods
                if not category
                else [m for m in mods if m["category"] == category],
                key=key,
                reverse=sort not in {"old", "abc"},
            )
        else:
            title_matches, desc_matches = self.gb_api.search(search)
            exacts = [
                title_matches.pop(i)
                for i in range(len(title_matches) - 1)
                if title_matches[i]["name"].lower() == search.lower()
            ]
            mods = (
                exacts
                + sorted(
                    title_matches
                    if not category
                    else [m for m in title_matches if m["category"] == category],
                    key=key,
                    reverse=sort not in {"old", "abc"},
                )
                + sorted(
                    desc_matches
                    if not category
                    else [m for m in desc_matches if m["category"] == category],
                    key=key,
                    reverse=sort not in {"old", "abc"},
                )
            )
        last = min(page * 24, len(mods))
        return mods[(page - 1) * 24 : last]

    @win_or_lose
    def update_gb_mod(self, mod_id: str):
        self.gb_api.update_mod(str(mod_id))
        return self.gb_api.get_mod_by_id(str(mod_id))

    @win_or_lose
    def install_gb_mod(self, file: dict):
        path = Path(mkdtemp()) / file["_sFile"]
        res: requests.Response = requests.get(file["_sDownloadUrl"])
        with path.open("wb") as tmp_file:
            for chunk in res.iter_content(chunk_size=1024):
                tmp_file.write(chunk)
        self.tmp_files.append(path)
        return str(path)

    def cleanup(self):
        for file in self.tmp_files:
            try:
                file.unlink()
            except (OSError, PermissionError, FileNotFoundError):
                pass
