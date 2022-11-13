"""Provides features for installing, creating, and mananging BCML mods"""
# Copyright 2020 Nicene Nerd <macadamiadaze@gmail.com>
# Licensed under GPLv3+
# pylint: disable=too-many-lines
import datetime
import errno
import json
import multiprocessing
import os
import re
import shutil
import stat
import subprocess
from functools import partial
from multiprocessing import Pool
from pathlib import Path
from platform import system
from shutil import rmtree, copyfile
from tempfile import TemporaryDirectory, mkdtemp
from typing import List, Union, Callable, Dict, Any, Optional
from xml.dom import minidom

import oead

from bcml import util, mergers, dev, upgrade
from bcml import bcml as rsext
from bcml.util import SYSTEM, BcmlMod, get_7z_path


def extract_mod_meta(mod: Path) -> Dict[str, Any]:
    result: subprocess.CompletedProcess
    if util.SYSTEM == "Windows":
        result = subprocess.run(
            [
                get_7z_path(),
                "e",
                str(mod.resolve()),
                "-r",
                "-so",
                "info.json",
            ],
            encoding="utf-8",
            capture_output=True,
            universal_newlines=True,
            creationflags=util.CREATE_NO_WINDOW,
        )
    else:
        result = subprocess.run(
            [
                get_7z_path(),
                "e",
                str(mod.resolve()),
                "-r",
                "-so",
                "info.json",
            ],
            encoding="utf-8",
            capture_output=True,
            universal_newlines=True,
        )
    try:
        assert not result.stderr
        meta = json.loads(result.stdout)
    except:
        return {}
    return meta


def open_mod(path: Path) -> Path:
    if isinstance(path, str):
        path = Path(path)
    tmpdir = Path(TemporaryDirectory().name)
    archive_formats = {".rar", ".zip", ".7z", ".bnp"}
    meta_formats = {".json", ".txt"}
    if tmpdir.exists():
        shutil.rmtree(tmpdir, ignore_errors=True)
    if path.suffix.lower() in archive_formats:
        x_args = [get_7z_path(), "x", str(path), f"-o{str(tmpdir)}"]
        if system() == "Windows":
            subprocess.run(
                x_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=util.CREATE_NO_WINDOW,
                check=False,
            )
        else:
            subprocess.run(
                x_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False
            )
    elif path.suffix.lower() in meta_formats:
        shutil.copytree(path.parent, tmpdir)
    else:
        raise ValueError(
            "The mod provided was not a supported archive (BNP, ZIP, RAR, or 7z) "
            "or meta file (rules.txt or info.json)."
        )
    if not tmpdir.exists():
        raise Exception(
            "No files were extracted. This may be because of an invalid or corrupted "
            "download."
        )

    rulesdir = tmpdir
    if (rulesdir / "info.json").exists():
        return rulesdir
    if not (rulesdir / "rules.txt").exists():
        for subdir in tmpdir.rglob("*"):
            if (subdir / "rules.txt").exists():
                rulesdir = subdir
                break
        else:
            raise FileNotFoundError(
                "No <code>info.json</code> or <code>rules.txt</code> file was found in "
                f'"{path.stem}". This could mean the mod is in an old or unsupported '
                "format. For information on creating BNPs, check the in-app help. If "
                "instead you want to make a graphic pack, check "
                '<a href="https://zeldamods.org/wiki/Help:Using_mods#Installing_mods_with_the_graphic_pack_menu" target="_blank">'
                "the guide on ZeldaMods here</a>."
            )
    print("Looks like an older mod, let's upgrade it...")
    upgrade.convert_old_mod(rulesdir, delete_old=True)
    return rulesdir


def get_next_priority() -> int:
    i = 100
    while list(util.get_modpack_dir().glob(f"{i:04}_*")):
        i += 1
    return i


def _check_modded(file: Path, tmp_dir: Path):
    try:
        canon = util.get_canon_name(file.relative_to(tmp_dir).as_posix())
    except ValueError:
        util.vprint(f"Ignored unknown file {file.relative_to(tmp_dir).as_posix()}")
        return None
    if util.is_file_modded(canon, file, True):
        util.vprint(f"Found modded file {canon}")
        return file
    else:
        if "Aoc/0010/Map/MainField" in canon:
            file.unlink()
        util.vprint(f"Ignored unmodded file {canon}")
        return None


def find_modded_files(
    tmp_dir: Path, pool: Optional[multiprocessing.pool.Pool] = None
) -> List[Union[Path, str]]:
    modded_files = []
    if isinstance(tmp_dir, str):
        tmp_dir = Path(tmp_dir)

    if (tmp_dir / util.get_dlc_path()).exists():
        try:
            util.get_aoc_dir()
        except FileNotFoundError:
            raise FileNotFoundError(
                "This mod uses DLC files, but BCML cannot locate the DLC folder in "
                "your game dump."
            )

    aoc_field = (
        tmp_dir
        / util.get_dlc_path()
        / ("0010" if util.get_settings("wiiu") else "")
        / "Pack"
        / "AocMainField.pack"
    )
    if aoc_field.exists() and aoc_field.stat().st_size > 0:
        if not list(
            (
                tmp_dir
                / util.get_dlc_path()
                / ("0010" if util.get_settings("wiiu") else "")
            ).rglob("Map/**/?-?_*.smubin")
        ):
            aoc_pack = oead.Sarc(aoc_field.read_bytes())
            for file in aoc_pack.get_files():
                ex_out = (
                    tmp_dir
                    / util.get_dlc_path()
                    / ("0010" if util.get_settings("wiiu") else "")
                    / file.name
                )
                ex_out.parent.mkdir(parents=True, exist_ok=True)
                ex_out.write_bytes(file.data)
        aoc_field.write_bytes(b"")

    modded_files = [
        f if "//" in f else Path(f)
        for f in rsext.find_modified_files(str(tmp_dir))
    ]
    return modded_files


def generate_logs(
    tmp_dir: Path,
    options: dict = None,
    pool: Optional[multiprocessing.pool.Pool] = None,
) -> List[Union[Path, str]]:
    if isinstance(tmp_dir, str):
        tmp_dir = Path(tmp_dir)
    if not options:
        options = {"disable": [], "options": {}}
    if "disable" not in options:
        options["disable"] = []
    util.vprint(options)

    this_pool = pool or util.start_pool()
    print("Scanning for modified files...")
    modded_files = find_modded_files(tmp_dir, pool=pool)
    if not (
        modded_files or (tmp_dir / "patches").exists() or (tmp_dir / "logs").exists()
    ):
        if "options" in tmp_dir.parts:
            message = (
                f"No modified files were found in {str(tmp_dir)}. "
                f"This may mean that this option's files are identical to the "
                f"base mod's, or that the folder has an improper structure."
            )
        else:
            message = (
                f"No modified files were found in {str(tmp_dir)}. "
                f"This probably means this mod is not in a supported format."
            )
        raise RuntimeError(message)

    (tmp_dir / "logs").mkdir(parents=True, exist_ok=True)
    try:
        for i, merger_class in enumerate(
            [
                merger_class
                for merger_class in mergers.get_mergers()
                if merger_class.NAME not in options["disable"]
            ]
        ):
            merger = merger_class()  # type: ignore
            util.vprint(f"Merger {merger.NAME}, #{i+1} of {len(mergers.get_mergers())}")
            if options is not None and merger.NAME in options["options"]:
                merger.set_options(options["options"][merger.NAME])
            merger.set_pool(this_pool)
            merger.log_diff(tmp_dir, modded_files)
        if util.get_settings("strip_gfx"):
            dev._clean_sarcs(
                tmp_dir, util.get_hash_table(util.get_settings("wiiu")), this_pool
            )
    except:  # pylint: disable=bare-except
        this_pool.close()
        this_pool.join()
        this_pool.terminate()
        raise
    if not pool:
        this_pool.close()
        this_pool.join()
    util.vprint(modded_files)
    return modded_files


def refresher(func: Callable) -> Callable:
    def do_and_refresh(*args, **kwargs):
        res = func(*args, **kwargs)
        refresh_master_export()
        return res

    return do_and_refresh


@util.timed
def refresh_master_export():
    print("Exporting merged mod pack...")
    link_master_mod()
    enable_bcml_gfx()


def install_mod(
    mod: Path,
    options: dict = None,
    selects: dict = None,
    pool: Optional[multiprocessing.pool.Pool] = None,
    insert_priority: int = 0,
    merge_now: bool = False,
    updated: bool = False,
):
    if not insert_priority:
        insert_priority = get_next_priority()

    try:
        if isinstance(mod, str):
            mod = Path(mod)
        if mod.is_file():
            print("Opening mod...")
            tmp_dir = open_mod(mod)
        elif mod.is_dir():
            if not ((mod / "rules.txt").exists() or (mod / "info.json").exists()):
                print(f"Cannot open mod at {str(mod)}, no rules.txt or info.json found")
                return
            print(f"Loading mod from {str(mod)}...")
            tmp_dir = Path(mkdtemp())
            if tmp_dir.exists():
                shutil.rmtree(tmp_dir)
            shutil.copytree(str(mod), str(tmp_dir))
            if (mod / "rules.txt").exists() and not (mod / "info.json").exists():
                print("Upgrading old mod format...")
                upgrade.convert_old_mod(mod, delete_old=True)
        else:
            print(f"Error: {str(mod)} is neither a valid file nor a directory")
            return
    except Exception as err:  # pylint: disable=broad-except
        raise util.InstallError(err) from err

    if not options:
        options = {"options": {}, "disable": []}

    this_pool: Optional[multiprocessing.pool.Pool] = None  # type: ignore
    try:
        rules = json.loads((tmp_dir / "info.json").read_text("utf-8"))
        mod_name = rules["name"].strip(" '\"").replace("_", "")
        print(f"Identified mod: {mod_name}")
        if rules["depends"]:
            try:
                installed_metas = {
                    v[0]: v[1]
                    for m in util.get_installed_mods()
                    for v in util.BcmlMod.meta_from_id(m.id)
                }
            except (IndexError, TypeError) as err:
                raise RuntimeError(f"This BNP has invalid or corrupt dependency data.")
            for depend in rules["depends"]:
                depend_name, depend_version = util.BcmlMod.meta_from_id(depend)
                if (depend_name not in installed_metas) or (
                    depend_name in installed_metas
                    and depend_version > installed_metas[depend_name]
                ):
                    raise RuntimeError(
                        f"{mod_name} requires {depend_name} version {depend_version}, "
                        f"but it is not installed. Please install {depend_name} and "
                        "try again."
                    )
        friendly_plaform = lambda p: "Wii U" if p == "wiiu" else "Switch"
        user_platform = "wiiu" if util.get_settings("wiiu") else "switch"
        if rules["platform"] != user_platform:
            raise ValueError(
                f'"{mod_name}" is for {friendly_plaform(rules["platform"])}, not '
                f" {friendly_plaform(user_platform)}.'"
            )
        if "priority" in rules and rules["priority"] == "base":
            insert_priority = 100

        logs = tmp_dir / "logs"
        if logs.exists():
            print("Loading mod logs...")
            for merger in [
                merger()  # type: ignore
                for merger in mergers.get_mergers()
                if merger.NAME in options["disable"]
            ]:
                if merger.is_mod_logged(BcmlMod(tmp_dir)):
                    (tmp_dir / "logs" / merger.log_name).unlink()
        else:
            this_pool = pool or util.start_pool()
            dev._pack_sarcs(
                tmp_dir, util.get_hash_table(util.get_settings("wiiu")), this_pool
            )
            generate_logs(tmp_dir=tmp_dir, options=options, pool=this_pool)
            if not util.get_settings("strip_gfx"):
                (tmp_dir / ".processed").touch()
    except Exception as err:  # pylint: disable=broad-except
        try:
            name = mod_name
        except NameError:
            name = "your mod, the name of which could not be detected"
        raise util.InstallError(err, name) from err

    if selects is not None:
        for opt_dir in {d for d in (tmp_dir / "options").glob("*") if d.is_dir()}:
            if opt_dir.name not in selects:
                shutil.rmtree(opt_dir, ignore_errors=True)
            else:
                file: Path
                for file in {
                    f
                    for f in opt_dir.rglob("**/*")
                    if ("logs" not in f.parts and f.is_file())
                }:
                    out = tmp_dir / file.relative_to(opt_dir)
                    out.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        os.link(file, out)
                    except FileExistsError:
                        if file.suffix in util.SARC_EXTS:
                            try:
                                old_sarc = oead.Sarc(
                                    util.unyaz_if_needed(out.read_bytes())
                                )
                            except (ValueError, oead.InvalidDataError, RuntimeError):
                                out.unlink()
                                os.link(file, out)
                            try:
                                link_sarc = oead.Sarc(
                                    util.unyaz_if_needed(file.read_bytes())
                                )
                            except (ValueError, oead.InvalidDataError, RuntimeError):
                                del old_sarc
                                continue
                            new_sarc = oead.SarcWriter.from_sarc(link_sarc)
                            link_files = {f.name for f in link_sarc.get_files()}
                            for sarc_file in old_sarc.get_files():
                                if sarc_file.name not in link_files:
                                    new_sarc.files[sarc_file.name] = bytes(
                                        sarc_file.data
                                    )
                            del old_sarc
                            del link_sarc
                            out.write_bytes(new_sarc.write()[1])
                            del new_sarc
                        else:
                            out.unlink()
                            os.link(file, out)

    rstb_path = (
        tmp_dir
        / util.get_content_path()
        / "System"
        / "Resource"
        / "ResourceSizeTable.product.srsizetable"
    )
    if rstb_path.exists():
        rstb_path.unlink()

    priority = insert_priority
    print(f"Assigned mod priority of {priority}")
    mod_id = util.get_mod_id(mod_name, priority)
    mod_dir = util.get_modpack_dir() / mod_id

    try:
        if not updated:
            for existing_mod in util.get_installed_mods(True):
                if existing_mod.priority >= priority:
                    existing_mod.change_priority(existing_mod.priority + 1)

        if (tmp_dir / "patches").exists() and not util.get_settings("no_cemu"):
            patch_dir = (
                util.get_cemu_dir()
                / "graphicPacks"
                / f"bcmlPatches"
                / util.get_safe_pathname(rules["name"])
            )
            patch_dir.mkdir(parents=True, exist_ok=True)
            for file in {f for f in (tmp_dir / "patches").rglob("*") if f.is_file()}:
                out = patch_dir / file.relative_to(tmp_dir / "patches")
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(file, out)

        mod_dir.parent.mkdir(parents=True, exist_ok=True)
        print(f"Moving mod to {str(mod_dir)}...")
        if mod.is_file():
            try:
                shutil.move(str(tmp_dir), str(mod_dir))
            except Exception:  # pylint: disable=broad-except
                try:
                    shutil.rmtree(str(mod_dir))
                    shutil.copytree(str(tmp_dir), str(mod_dir))
                    shutil.rmtree(str(tmp_dir), ignore_errors=True)
                except Exception:  # pylint: disable=broad-except
                    raise OSError(
                        "BCML could not transfer your mod from the temp directory to the"
                        " BCML directory."
                    )
        elif mod.is_dir():
            shutil.copytree(str(tmp_dir), str(mod_dir))

        shutil.rmtree(tmp_dir, ignore_errors=True)

        rules["priority"] = priority
        (mod_dir / "info.json").write_text(
            json.dumps(rules, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (mod_dir / "options.json").write_text(
            json.dumps(options, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        output_mod = BcmlMod(mod_dir)
        try:
            util.get_mod_link_meta(rules)
            util.get_mod_preview(output_mod)
        except Exception:  # pylint: disable=broad-except
            pass
    except Exception as err:  # pylint: disable=broad-except
        if mod_dir.exists():
            try:
                uninstall_mod(mod_dir, wait_merge=True)
            except Exception:  # pylint: disable=broad-except
                shutil.rmtree(str(mod_dir))
        raise util.InstallError(err, mod_name) from err

    try:
        if merge_now:
            for merger in [m() for m in mergers.get_mergers()]:
                if this_pool or pool:
                    merger.set_pool(this_pool or pool)
                if merger.NAME in options["options"]:
                    merger.set_options(options["options"][merger.NAME])
                merger.perform_merge()
    except Exception as err:  # pylint: disable=broad-except
        raise util.MergeError(err) from err

    if this_pool and not pool:
        this_pool.close()
        this_pool.join()
    return output_mod


@refresher
def disable_mod(mod: BcmlMod, wait_merge: bool = False):
    remergers = []
    print(f"Disabling {mod.name}...")
    for merger in [merger() for merger in mergers.get_mergers()]:  # type: ignore
        if merger.is_mod_logged(mod):
            remergers.append(merger)
    (mod.path / ".disabled").write_bytes(b"")
    if not wait_merge:
        print("Remerging...")
        refresh_merges()
    print(f"{mod.name} disabled")


@refresher
def enable_mod(mod: BcmlMod, wait_merge: bool = False):
    print(f"Enabling {mod.name}...")
    (mod.path / ".disabled").unlink()
    if not wait_merge:
        print("Remerging...")
        refresh_merges()
    print(f"{mod.name} enabled")


def force_del(func, path, exc):
    excvalue = exc[1]
    if func in (os.rmdir, os.remove) and excvalue.errno == errno.EACCES:
        os.chmod(path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)  # 0777
        func(path)
    else:
        raise RuntimeError(
            f"The folder {path} could not be removed. "
            "You may need to delete it manually and remerge, or "
            "close all open programs (including BCML and Windows Explorer) "
            "and try again. The location of the folder is "
            f"<code>{str(path)}</code>."
        )


@refresher
def uninstall_mod(mod: BcmlMod, wait_merge: bool = False):
    has_patches = (mod.path / "patches").exists()
    try:
        shutil.rmtree(str(mod.path), onerror=force_del)
    except (OSError, PermissionError, WindowsError) as err:
        raise RuntimeError(
            f"The folder for {mod.name} could not be removed. "
            "You may need to delete it manually and remerge, or "
            "close all open programs (including BCML and Windows Explorer) "
            "and try again. The location of the folder is "
            f"<code>{str(mod.path)}</code>."
        ) from err

    for fall_mod in [
        m for m in util.get_installed_mods(True) if m.priority > mod.priority
    ]:
        fall_mod.change_priority(fall_mod.priority - 1)

    if not util.get_installed_mods():
        shutil.rmtree(util.get_master_modpack_dir())
        util.create_bcml_graphicpack_if_needed()
    else:
        if not wait_merge:
            refresh_merges()

    if has_patches and not util.get_settings("no_cemu"):
        shutil.rmtree(
            util.get_cemu_dir()
            / "graphicPacks"
            / "bcmlPatches"
            / util.get_safe_pathname(mod.name),
            ignore_errors=True,
        )

    print(f"{mod.name} has been uninstalled.")


def refresh_merges():
    print("Cleansing old merges...")
    shutil.rmtree(util.get_master_modpack_dir(), True)
    print("Refreshing merged mods...")
    with util.start_pool() as pool:
        for merger in mergers.sort_mergers(
            [merger_class() for merger_class in mergers.get_mergers()]
        ):
            merger.set_pool(pool)
            merger.perform_merge()


def create_backup(name: str = ""):
    if not name:
        name = f'BCML_Backup_{datetime.datetime.now().strftime("%Y-%m-%d")}'
    else:
        name = re.sub(r"(?u)[^-\w.]", "", name.strip().replace(" ", "_"))
    num_mods = len([d for d in util.get_modpack_dir().glob("*") if d.is_dir()])
    output = util.get_storage_dir() / "backups" / f"{name}---{num_mods - 1}.7z"
    output.parent.mkdir(parents=True, exist_ok=True)
    print(f"Saving backup {name}...")
    x_args = [get_7z_path(), "a", str(output), f'{str(util.get_modpack_dir() / "*")}']
    if system() == "Windows":
        subprocess.run(
            x_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=util.CREATE_NO_WINDOW,
            check=True,
        )
    else:
        subprocess.run(
            x_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
        )
    print(f'Backup "{name}" created')


def get_backups() -> List[Path]:
    return list((util.get_storage_dir() / "backups").glob("*.7z"))


def restore_backup(backup: Union[str, Path]):
    if isinstance(backup, str):
        backup = Path(backup)
    if not backup.exists():
        raise FileNotFoundError(f'The backup "{backup.name}" does not exist.')
    print("Clearing installed mods...")
    for folder in [item for item in util.get_modpack_dir().glob("*") if item.is_dir()]:
        shutil.rmtree(str(folder))
    print("Extracting backup...")
    x_args = [get_7z_path(), "x", str(backup), f"-o{str(util.get_modpack_dir())}"]
    if system() == "Windows":
        subprocess.run(
            x_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=util.CREATE_NO_WINDOW,
            check=True,
        )
    else:
        subprocess.run(
            x_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
        )
    print("Re-enabling mods in Cemu...")
    refresh_master_export()
    print(f'Backup "{backup.name}" restored')


def enable_bcml_gfx():
    if util.get_settings("no_cemu"):
        return

    settings = util.parse_cemu_settings()
    try:
        gpack = settings.getElementsByTagName("GraphicPack")[0]
    except IndexError:
        gpack = settings.createElement("GraphicPack")
        settings.appendChild(gpack)
    new_cemu = True

    def create_entry(path: str):
        def entry_matches(entry):
            try:
                return (
                    path == entry.getElementsByTagName("filename")[0].childNodes[0].data
                )
            except IndexError:
                return path == entry.getAttribute("filename")

        if any(entry_matches(entry) for entry in gpack.getElementsByTagName("Entry")):
            return
        entry: minidom.Element = settings.createElement("Entry")
        if new_cemu:
            entry.setAttribute("filename", path)
        else:
            entryfile = settings.createElement("filename")
            entryfile.appendChild(settings.createTextNode(path))
            entry.appendChild(entryfile)
        entrypreset = settings.createElement("preset")
        entrypreset.appendChild(settings.createTextNode(""))
        entry.appendChild(entrypreset)
        gpack.appendChild(entry)

    create_entry("graphicPacks\\BreathOfTheWild_BCML\\rules.txt")

    if (util.get_cemu_dir() / "graphicPacks" / "bcmlPatches").exists():
        for rules in (util.get_cemu_dir() / "graphicPacks" / "bcmlPatches").rglob(
            "rules.txt"
        ):
            create_entry(str(rules.relative_to(util.get_cemu_dir())))

        settings.writexml(
            (util.get_cemu_dir() / "settings.xml").open("w", encoding="utf-8"),
            addindent="    ",
            newl="\n",
        )


def disable_bcml_gfx():
    if not util.get_settings("no_cemu"):
        settings = util.parse_cemu_settings()
        try:
            gpack = settings.getElementsByTagName("GraphicPack")[0]
        except IndexError:
            gpack = settings.createElement("GraphicPack")
            settings.appendChild(gpack)
        new_cemu = True
        entry: minidom.Element
        for entry in gpack.getElementsByTagName("Entry"):
            if new_cemu and entry.getElementsByTagName("filename"):
                new_cemu = False
            try:
                if (
                    "bcml"
                    in entry.getElementsByTagName("filename")[0]
                    .childNodes[0]
                    .data.lower()
                ):
                    gpack.removeChild(entry)
            except IndexError:
                if "bcml" in entry.getAttribute("filename").lower():
                    gpack.removeChild(entry)
        settings.writexml(
            (util.get_cemu_dir() / "settings.xml").open("w", encoding="utf-8"),
            addindent="    ",
            newl="\n",
        )


def link_master_mod(output: Path = None):
    util.create_bcml_graphicpack_if_needed()
    try:
        rsext.manager.link_master_mod(str(output) if output else None)
    except (OSError, RuntimeError) as err:
        if err is OSError or (err is RuntimeError and "junction" in str(err)):
            raise RuntimeError(
                "BCML failed to create the link to the merged mod. This is "
                "probably because Cemu is on an external USB, eSATA, or "
                "network drive. You can fix this in one of two ways:\n"
                "- Make sure Cemu is on an internal drive\n"
                "- Turn on the 'no hard links' option in BCML's settings "
                "(but be aware that mod merging will take much longer)"
            ) from err
        else:
            raise


def export(output: Path, standalone: bool = False):
    print("Loading files...")
    tmp_dir = Path(mkdtemp())
    if tmp_dir.exists():
        try:
            rmtree(tmp_dir)
        except (OSError, FileNotFoundError, PermissionError) as err:
            raise RuntimeError(
                "There was a problem cleaning the temporary export directory. This may be"
                " a fluke, so consider restarting BCML and trying again."
            ) from err
    link_master_mod(tmp_dir)
    if output.suffix == ".bnp" or output.name.endswith(".bnp.7z"):
        print("Exporting BNP...")
        dev.create_bnp_mod(
            mod=tmp_dir,
            meta={},
            output=output,
            options={"rstb": {"no_guess": util.get_settings("no_guess")}},
        )
    else:
        print("Exporting as graphic pack mod...")
        x_args = [get_7z_path(), "a", str(output), f'{str(tmp_dir / "*")}']
        result: subprocess.CompletedProcess
        if os.name == "nt":
            result = subprocess.run(
                x_args,
                creationflags=util.CREATE_NO_WINDOW,
                check=False,
                capture_output=True,
                universal_newlines=True,
            )
        else:
            result = subprocess.run(
                x_args, check=False, capture_output=True, universal_newlines=True
            )
        if result.stderr:
            raise RuntimeError(
                f"There was an error exporting your mod(s). {result.stderr}"
            )
    rmtree(tmp_dir, True)
