"""Provides features for installing, creating, and mananging BCML mods"""
# Copyright 2020 Nicene Nerd <macadamiadaze@gmail.com>
# Licensed under GPLv3+
# pylint: disable=too-many-lines
import datetime
import json
import os
import re
import shutil
import subprocess
from base64 import b64decode
from functools import partial
from multiprocessing import Pool
from pathlib import Path
from platform import system
from shutil import rmtree, copyfile
from tempfile import TemporaryDirectory, mkdtemp
from typing import List, Union, Callable
from xml.dom import minidom

import oead

from bcml import util, mergers, dev, upgrade
from bcml.util import BcmlMod, ZPATH


def extract_mod_meta(mod: Path) -> {}:
    process = subprocess.Popen(
        f'"{ZPATH}" e "{str(mod.resolve())}" -r -so info.json',
        stdout=subprocess.PIPE,
        shell=True,
    )
    out, _ = process.communicate()
    process.wait()
    return json.loads(out.decode("utf-8")) if out else {}


def open_mod(path: Path) -> Path:
    if isinstance(path, str):
        path = Path(path)
    tmpdir = Path(TemporaryDirectory().name)
    archive_formats = {".rar", ".zip", ".7z", ".bnp"}
    meta_formats = {".json", ".txt"}
    if tmpdir.exists():
        shutil.rmtree(tmpdir, ignore_errors=True)
    if path.suffix.lower() in archive_formats:
        x_args = [ZPATH, "x", str(path), f"-o{str(tmpdir)}"]
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
        raise Exception("No files were extracted.")

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
                "format. For information on converting mods, see "
                '<a href="https://gamebanana.com/tuts/12493">'
                "this tutorial</a>."
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


def find_modded_files(tmp_dir: Path, pool: Pool = None) -> List[Union[Path, str]]:
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
        if not (
            tmp_dir / util.get_dlc_path() / ("0010" if util.get_settings("wiiu") else "")
        ).rglob("Map/**/?-?_*.smubin"):
            aoc_pack = oead.Sarc(aoc_field.read_bytes())
            for file in aoc_pack.get_files():
                ex_out = tmp_dir / util.get_dlc_path() / "0010" / file.name
                ex_out.parent.mkdir(parents=True, exist_ok=True)
                ex_out.write_bytes(file.data)
        aoc_field.write_bytes(b"")

    this_pool = pool or Pool()
    results = this_pool.map(
        partial(_check_modded, tmp_dir=tmp_dir),
        {
            f
            for f in tmp_dir.rglob("**/*")
            if f.is_file() and "options" not in f.relative_to(tmp_dir).parts
        },
    )
    for result in results:
        if result:
            modded_files.append(result)
    total = len(modded_files)
    print(f'Found {total} modified file{"s" if total > 1 else ""}')

    total = 0
    sarc_files = {f for f in modded_files if f.suffix in util.SARC_EXTS}
    if sarc_files:
        print("Scanning files packed in SARCs...")
        for files in this_pool.imap_unordered(
            partial(find_modded_sarc_files, tmp_dir=tmp_dir), sarc_files
        ):
            total += len(files)
            modded_files.extend(files)
        print(f'Found {total} modified packed file{"s" if total > 1 else ""}')
    if not pool:
        this_pool.close()
        this_pool.join()
    return modded_files


def find_modded_sarc_files(
    mod_sarc: Union[Path, oead.Sarc], tmp_dir: Path, name: str = "", aoc: bool = False
) -> List[str]:
    if isinstance(mod_sarc, Path):
        if any(mod_sarc.name.startswith(exclude) for exclude in ["Bootup_"]):
            return []
        name = str(mod_sarc.relative_to(tmp_dir))
        aoc = util.get_dlc_path() in mod_sarc.parts or "Aoc" in mod_sarc.parts
        try:
            mod_sarc = oead.Sarc(util.unyaz_if_needed(mod_sarc.read_bytes()))
        except (RuntimeError, ValueError, oead.InvalidDataError):
            return []
    modded_files = []
    for file, contents in [(f.name, bytes(f.data)) for f in mod_sarc.get_files()]:
        canon = file.replace(".s", ".")
        if aoc:
            canon = "Aoc/0010/" + canon
        contents = util.unyaz_if_needed(contents)
        nest_path = str(name).replace("\\", "/") + "//" + file
        if util.is_file_modded(canon, contents, True):
            modded_files.append(nest_path)
            util.vprint(f'Found modded file {canon} in {str(name).replace("//", "/")}')
            if util.is_file_sarc(canon) and ".ssarc" not in file:
                try:
                    nest_sarc = oead.Sarc(contents)
                except ValueError:
                    continue
                sub_mod_files = find_modded_sarc_files(
                    nest_sarc, name=nest_path, tmp_dir=tmp_dir, aoc=aoc
                )
                modded_files.extend(sub_mod_files)
        else:
            util.vprint(
                f'Ignored unmodded file {canon} in {str(name).replace("//", "/")}'
            )
    return modded_files


def generate_logs(tmp_dir: Path, options: dict = None, pool: Pool = None) -> List[Path]:
    if isinstance(tmp_dir, str):
        tmp_dir = Path(tmp_dir)
    if not options:
        options = {"disable": [], "options": {}}
    if "disable" not in options:
        options["disable"] = []
    util.vprint(options)

    this_pool = pool or Pool()
    print("Scanning for modified files...")
    modded_files = find_modded_files(tmp_dir, pool=pool)
    if not modded_files:
        raise RuntimeError(
            f"No modified files were found in {str(tmp_dir)}."
            "This probably means this mod is not in a supported format."
        )

    (tmp_dir / "logs").mkdir(parents=True, exist_ok=True)
    try:
        for i, merger_class in enumerate(
            [
                merger_class
                for merger_class in mergers.get_mergers()
                if merger_class.NAME not in options["disable"]
            ]
        ):
            merger = merger_class()
            util.vprint(f"Merger {merger.NAME}, #{i+1} of {len(mergers.get_mergers())}")
            if options is not None and merger.NAME in options["options"]:
                merger.set_options(options["options"][merger.NAME])
            merger.set_pool(this_pool)
            merger.log_diff(tmp_dir, modded_files)
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


def refresh_master_export():
    print("Exporting merged mod pack...")
    link_master_mod()
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
                if "BCML" in entry.getElementsByTagName("filename")[0].childNodes[0].data:
                    break
            except IndexError:
                if "BCML" in entry.getAttribute("filename"):
                    break
        else:
            bcmlentry = settings.createElement("Entry")
            if new_cemu:
                bcmlentry.setAttribute(
                    "filename", "graphicPacks\\BreathOfTheWild_BCML\\rules.txt"
                )
            else:
                entryfile = settings.createElement("filename")
                entryfile.appendChild(
                    settings.createTextNode(
                        "graphicPacks\\BreathOfTheWild_BCML\\rules.txt"
                    )
                )
                bcmlentry.appendChild(entryfile)
            entrypreset = settings.createElement("preset")
            entrypreset.appendChild(settings.createTextNode(""))
            bcmlentry.appendChild(entrypreset)
            gpack.appendChild(bcmlentry)
            settings.writexml(
                (util.get_cemu_dir() / "settings.xml").open("w", encoding="utf-8"),
                addindent="    ",
                newl="\n",
            )


def install_mod(
    mod: Path,
    options: dict = None,
    selects: dict = None,
    pool: Pool = None,
    insert_priority: int = 0,
    merge_now: bool = False,
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

    this_pool: Pool = None
    try:
        rules = json.loads((tmp_dir / "info.json").read_text("utf-8"))
        mod_name = rules["name"].strip(" '\"").replace("_", "")
        print(f"Identified mod: {mod_name}")
        if rules["depends"]:
            installed_metas = {
                v[0]: v[1]
                for m in util.get_installed_mods()
                for v in util.BcmlMod.meta_from_id(m.id)
            }
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
                f" {friendly_plaform(user_platform)}. If you want to use it, check "
                'the "Allow cross-platform install" option.'
            )

        logs = tmp_dir / "logs"
        if logs.exists():
            print("Loading mod logs...")
            for merger in [
                merger()
                for merger in mergers.get_mergers()
                if merger.NAME in options["disable"]
            ]:
                if merger.is_mod_logged(BcmlMod(tmp_dir)):
                    (tmp_dir / "logs" / merger.log_name).unlink()
        else:
            this_pool = pool or Pool()
            generate_logs(tmp_dir=tmp_dir, options=options, pool=pool)
            (tmp_dir / ".processed").touch()
    except Exception as err:  # pylint: disable=broad-except
        try:
            name = mod_name
        except NameError:
            name = "your mod, the name of which could not be detected"
        raise util.InstallError(err, name) from err

    if selects:
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
                                    new_sarc.files[sarc_file.name] = bytes(sarc_file.data)
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
        for existing_mod in util.get_installed_mods(True):
            if existing_mod.priority >= priority:
                existing_mod.change_priority(existing_mod.priority + 1)

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

        print(f"Enabling {mod_name} in Cemu...")
    except Exception as err:  # pylint: disable=broad-except
        if mod_dir.exists():
            try:
                uninstall_mod(mod_dir, wait_merge=True)
            except Exception:  # pylint: disable=broad-except
                shutil.rmtree(str(mod_dir))
        raise util.InstallError(err, mod_name) from err

    try:
        if merge_now:
            all_mergers = set()
            for merger in {m() for m in mergers.get_mergers()}:
                if merger.is_mod_logged(output_mod):
                    all_mergers.add(merger)
            for merger in mergers.sort_mergers(all_mergers):
                merger.set_pool(this_pool)
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
    for merger in [merger() for merger in mergers.get_mergers()]:
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


@refresher
def uninstall_mod(mod: BcmlMod, wait_merge: bool = False):
    print(f"Uninstalling {mod.name}...")
    try:
        shutil.rmtree(str(mod.path))
    except (OSError, PermissionError) as err:
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

    print(f"{mod.name} has been uninstalled.")


def refresh_merges():
    print("Cleansing old merges...")
    shutil.rmtree(util.get_master_modpack_dir(), True)
    print("Refreshing merged mods...")
    with Pool() as pool:
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
    x_args = [ZPATH, "a", str(output), f'{str(util.get_modpack_dir() / "*")}']
    if system() == "Windows":
        subprocess.run(
            x_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=util.CREATE_NO_WINDOW,
            check=True,
        )
    else:
        subprocess.run(x_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
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
    x_args = [ZPATH, "x", str(backup), f"-o{str(util.get_modpack_dir())}"]
    if system() == "Windows":
        subprocess.run(
            x_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=util.CREATE_NO_WINDOW,
            check=True,
        )
    else:
        subprocess.run(x_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    print("Re-enabling mods in Cemu...")
    refresh_master_export()
    print(f'Backup "{backup.name}" restored')


def link_master_mod(output: Path = None):
    util.create_bcml_graphicpack_if_needed()
    if not output:
        if util.get_settings("no_cemu"):
            return
        output = util.get_cemu_dir() / "graphicPacks" / "BreathOfTheWild_BCML"
    if output.exists():
        shutil.rmtree(output, ignore_errors=True)
    try:
        output.mkdir(parents=True, exist_ok=True)
        if not util.get_settings("no_cemu"):
            shutil.copy(util.get_master_modpack_dir() / "rules.txt", output / "rules.txt")
    except (OSError, PermissionError, FileExistsError, FileNotFoundError) as err:
        raise RuntimeError(
            "There was a problem creating the master BCML graphic pack. "
            "It may be a one time fluke, so try remerging and/or restarting BCML. "
            "If the problem persists, good luck, because it's something wonky about your "
            "PC, I guess."
        ) from err

    mod_folders: List[Path] = sorted(
        [
            item
            for item in util.get_modpack_dir().glob("*")
            if item.is_dir() and not (item / ".disabled").exists()
        ],
        reverse=True,
    )
    util.vprint(mod_folders)
    link_or_copy = os.link if not util.get_settings("no_hardlinks") else copyfile
    for mod_folder in mod_folders:
        for item in mod_folder.rglob("**/*"):
            rel_path = item.relative_to(mod_folder)
            exists = (output / rel_path).exists()
            is_log = str(rel_path).startswith("logs")
            is_opt = str(rel_path).startswith("options")
            is_meta = str(rel_path).startswith("meta")
            is_extra = (
                len(rel_path.parts) == 1
                and rel_path.suffix != ".txt"
                and not item.is_dir()
            )
            if exists or is_log or is_extra or is_meta or is_opt:
                continue
            if item.is_dir():
                (output / rel_path).mkdir(parents=True, exist_ok=True)
            elif item.is_file():
                try:
                    link_or_copy(str(item), str(output / rel_path))
                except OSError:
                    if link_or_copy is os.link:
                        link_or_copy = copyfile
                        link_or_copy(str(item), str(output / rel_path))
                    else:
                        raise


def export(output: Path):
    print("Loading files...")
    tmp_dir = Path(mkdtemp())
    if tmp_dir.drive != util.get_modpack_dir().drive:
        tmp_dir = Path(util.get_modpack_dir().drive) / "tmp_bcml_export"
    if tmp_dir.exists():
        try:
            rmtree(tmp_dir)
        except (OSError, FileNotFoundError, PermissionError) as err:
            raise RuntimeError(
                "There was a problem cleaning the temporary export directory. This may be"
                " a fluke, so consider restarting BCML and trying again."
            ) from err
    link_master_mod(tmp_dir)
    print("Adding rules.txt...")
    rules_path = tmp_dir / "rules.txt"
    mods = util.get_installed_mods()
    if util.get_settings("wiiu"):
        rules_path.write_text(
            "[Definition]\n"
            "titleIds = 00050000101C9300,00050000101C9400,00050000101C9500\n"
            "name = Exported BCML Mod\n"
            "path = The Legend of Zelda: Breath of the Wild/Mods/Exported BCML\n"
            f'description = Exported merge of {", ".join([mod.name for mod in mods])}\n'
            "version = 4\n",
            encoding="utf-8",
        )
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
        x_args = [ZPATH, "a", str(output), f'{str(tmp_dir / "*")}']
        result: subprocess.CompletedProcess
        if os.name == "nt":
            result = subprocess.run(
                x_args,
                creationflags=util.CREATE_NO_WINDOW,
                check=False,
                capture_output=True,
            )
        else:
            result = subprocess.run(check=False, capture_output=True)
        if result.stderr:
            raise RuntimeError(
                f"There was an error exporting your mod(s). {result.stderr}"
            )
    rmtree(tmp_dir, True)
