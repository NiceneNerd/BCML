# pylint: disable=unsupported-assignment-operation,no-member
from base64 import urlsafe_b64encode
from copy import deepcopy
from fnmatch import fnmatch
from functools import partial
from json import dumps
from multiprocessing import Pool
from pathlib import Path
from platform import system
from tempfile import TemporaryDirectory
from typing import Optional
import shutil
import subprocess

import oead
import xxhash  # pylint: disable=wrong-import-order

from bcml import util, install

EXCLUDE_EXTS = {".yml", ".yaml", ".bak", ".txt", ".json", ".old"}


def _yml_to_byml(file: Path):
    data = oead.byml.to_binary(
        oead.byml.from_text(file.read_text("utf-8")),
        big_endian=util.get_settings("wiiu"),
    )
    out = file.with_suffix("")
    out.write_bytes(data if not out.suffix.startswith(".s") else util.compress(data))
    file.unlink()


def _yml_to_aamp(file: Path):
    file.with_suffix("").write_bytes(
        oead.aamp.ParameterIO.from_text(file.read_text("utf-8")).to_binary()
    )
    file.unlink()


def _pack_sarcs(tmp_dir: Path, hashes: dict, pool: Pool):
    sarc_folders = {
        d
        for d in tmp_dir.rglob("**/*")
        if (
            d.is_dir()
            and not "options" in d.relative_to(tmp_dir).parts
            and d.suffix != ".pack"
            and d.suffix in util.SARC_EXTS
        )
    }
    if sarc_folders:
        pool.map(partial(_pack_sarc, hashes=hashes, tmp_dir=tmp_dir), sarc_folders)
    pack_folders = {
        d
        for d in tmp_dir.rglob("**/*")
        if d.is_dir()
        and not "options" in d.relative_to(tmp_dir).parts
        and d.suffix == ".pack"
    }
    if pack_folders:
        pool.map(partial(_pack_sarc, hashes=hashes, tmp_dir=tmp_dir), pack_folders)


def _pack_sarc(folder: Path, tmp_dir: Path, hashes: dict):
    packed = oead.SarcWriter(
        endian=oead.Endianness.Big
        if util.get_settings("wiiu")
        else oead.Endianness.Little
    )
    try:
        canon = util.get_canon_name(
            folder.relative_to(tmp_dir).as_posix(), allow_no_source=True
        )
        if canon not in hashes:
            raise FileNotFoundError("File not in game dump")
        stock_file = util.get_game_file(folder.relative_to(tmp_dir))
        try:
            old_sarc = oead.Sarc(util.unyaz_if_needed(stock_file.read_bytes()))
        except (RuntimeError, ValueError, oead.InvalidDataError):
            raise ValueError("Cannot open file from game dump")
        old_files = {f.name for f in old_sarc.get_files()}
    except (FileNotFoundError, ValueError):
        for file in {f for f in folder.rglob("**/*") if f.is_file()}:
            packed.files[file.relative_to(folder).as_posix()] = file.read_bytes()
    else:
        for file in {
            f
            for f in folder.rglob("**/*")
            if f.is_file() and not f.suffix in EXCLUDE_EXTS
        }:
            file_data = file.read_bytes()
            xhash = xxhash.xxh64_intdigest(util.unyaz_if_needed(file_data))
            file_name = file.relative_to(folder).as_posix()
            if file_name in old_files:
                old_hash = xxhash.xxh64_intdigest(
                    util.unyaz_if_needed(old_sarc.get_file(file_name).data)
                )
            if file_name not in old_files or (
                xhash != old_hash and file.suffix not in util.AAMP_EXTS
            ):
                packed.files[file_name] = file_data
    finally:
        shutil.rmtree(folder)
        if not packed.files:
            return  # pylint: disable=lost-exception
        sarc_bytes = packed.write()[1]
        folder.write_bytes(
            util.compress(sarc_bytes)
            if (folder.suffix.startswith(".s") and not folder.suffix == ".sarc")
            else sarc_bytes
        )


def _clean_sarcs(tmp_dir: Path, hashes: dict, pool: Pool):
    sarc_files = {
        file
        for file in tmp_dir.rglob("**/*")
        if file.suffix in util.SARC_EXTS
        and "options" not in file.relative_to(tmp_dir).parts
    }
    if sarc_files:
        print("Creating partial packs...")
        pool.map(partial(_clean_sarc_file, hashes=hashes, tmp_dir=tmp_dir), sarc_files)

    sarc_files = {
        file
        for file in tmp_dir.rglob("**/*")
        if file.suffix in util.SARC_EXTS
        and "options" not in file.relative_to(tmp_dir).parts
    }
    if sarc_files:
        print("Updating pack log...")
        final_packs = [file for file in sarc_files if file.suffix in util.SARC_EXTS]
        if final_packs:
            (tmp_dir / "logs").mkdir(parents=True, exist_ok=True)
            (tmp_dir / "logs" / "packs.json").write_text(
                dumps(
                    {
                        util.get_canon_name(file.relative_to(tmp_dir)): str(
                            file.relative_to(tmp_dir)
                        )
                        for file in final_packs
                    },
                    indent=2,
                )
            )
        else:
            try:
                (tmp_dir / "logs" / "packs.json").unlink()
            except FileNotFoundError:
                pass
    else:
        try:
            (tmp_dir / "logs" / "packs.json").unlink()
        except FileNotFoundError:
            pass


def _clean_sarc(old_sarc: oead.Sarc, base_sarc: oead.Sarc) -> Optional[oead.SarcWriter]:
    old_files = {f.name for f in old_sarc.get_files()}
    new_sarc = oead.SarcWriter(
        endian=oead.Endianness.Big
        if util.get_settings("wiiu")
        else oead.Endianness.Little
    )
    can_delete = True
    for nest_file, file_data in [(f.name, f.data) for f in base_sarc.get_files()]:
        ext = Path(nest_file).suffix
        if ext in {".yml", ".bak"}:
            continue
        if nest_file in old_files:
            old_data = util.unyaz_if_needed(old_sarc.get_file(nest_file).data)
        file_data = util.unyaz_if_needed(file_data)
        if nest_file not in old_files or (
            file_data != old_data and ext not in util.AAMP_EXTS
        ):
            if ext in util.SARC_EXTS:
                nest_old_sarc = oead.Sarc(old_data)
                nest_base_sarc = oead.Sarc(file_data)
                nest_new_sarc = _clean_sarc(nest_old_sarc, nest_base_sarc)
                if nest_new_sarc:
                    new_bytes = nest_new_sarc.write()[1]
                    if ext.startswith(".s") and ext != ".sarc":
                        new_bytes = util.compress(new_bytes)
                    new_sarc.files[nest_file] = oead.Bytes(new_bytes)
                    can_delete = False
                else:
                    continue
            else:
                new_sarc.files[nest_file] = oead.Bytes(file_data)
                can_delete = False
    return None if can_delete else new_sarc


def _clean_sarc_file(file: Path, hashes: dict, tmp_dir: Path):
    canon = util.get_canon_name(file.relative_to(tmp_dir))
    try:
        stock_file = util.get_game_file(file.relative_to(tmp_dir))
    except FileNotFoundError:
        return
    try:
        old_sarc = oead.Sarc(util.unyaz_if_needed(stock_file.read_bytes()))
    except (RuntimeError, ValueError, oead.InvalidDataError):
        return
    if canon not in hashes:
        return
    try:
        base_sarc = oead.Sarc(util.unyaz_if_needed(file.read_bytes()))
    except (RuntimeError, ValueError, oead.InvalidDataError):
        return
    new_sarc = _clean_sarc(old_sarc, base_sarc)
    if not new_sarc:
        file.unlink()
    else:
        write_bytes = new_sarc.write()[1]
        file.write_bytes(
            write_bytes
            if not (file.suffix.startswith(".s") and file.suffix != ".ssarc")
            else util.compress(write_bytes)
        )


def _do_yml(file: Path):
    out = file.with_suffix("")
    if out.exists():
        return
    if out.suffix in util.AAMP_EXTS:
        _yml_to_aamp(file)
    elif out.suffix in util.BYML_EXTS:
        _yml_to_byml(file)


def _make_bnp_logs(tmp_dir: Path, options: dict):
    util.vprint(install.generate_logs(tmp_dir, options=options))

    print("Removing unnecessary files...")

    if (tmp_dir / "logs" / "map.yml").exists():
        print("Removing map units...")
        for file in [
            file
            for file in tmp_dir.rglob("**/*.smubin")
            if fnmatch(file.name, "[A-Z]-[0-9]_*.smubin") and "MainField" in file.parts
        ]:
            file.unlink()

    if set((tmp_dir / "logs").glob("*texts*")):
        print("Removing language bootup packs...")
        for bootup_lang in (tmp_dir / util.get_content_path() / "Pack").glob(
            "Bootup_*.pack"
        ):
            bootup_lang.unlink()

    if (tmp_dir / "logs" / "actorinfo.yml").exists() and (
        tmp_dir / util.get_content_path() / "Actor" / "ActorInfo.product.sbyml"
    ).exists():
        print("Removing ActorInfo.product.sbyml...")
        (tmp_dir / util.get_content_path() / "Actor" / "ActorInfo.product.sbyml").unlink()

    if (tmp_dir / "logs" / "gamedata.yml").exists() or (
        tmp_dir / "logs" / "savedata.yml"
    ).exists():
        print("Removing gamedata sarcs...")
        bsarc = oead.Sarc(
            (tmp_dir / util.get_content_path() / "Pack" / "Bootup.pack").read_bytes()
        )
        csarc = oead.SarcWriter.from_sarc(bsarc)
        bsarc_files = {f.name for f in bsarc.get_files()}
        if "GameData/gamedata.ssarc" in bsarc_files:
            del csarc.files["GameData/gamedata.ssarc"]
        if "GameData/savedataformat.ssarc" in bsarc_files:
            del csarc.files["GameData/savedataformat.ssarc"]
        (tmp_dir / util.get_content_path() / "Pack" / "Bootup.pack").write_bytes(
            csarc.write()[1]
        )


def create_bnp_mod(mod: Path, output: Path, meta: dict, options: dict = None):
    if isinstance(mod, str):
        mod = Path(mod)

    if mod.is_file():
        print("Extracting mod...")
        tmp_dir: Path = install.open_mod(mod)
    elif mod.is_dir():
        print(f"Loading mod from {str(mod)}...")
        tmp_dir = Path(TemporaryDirectory().name)
        shutil.copytree(mod, tmp_dir)
    else:
        print(f"Error: {str(mod)} is neither a valid file nor a directory")
        return

    if not (
        (tmp_dir / util.get_content_path()).exists()
        or (tmp_dir / util.get_dlc_path()).exists()
    ):
        if (tmp_dir.parent / util.get_content_path()).exists():
            tmp_dir = tmp_dir.parent
        elif util.get_settings("wiiu") and (tmp_dir / "Content").exists():
            (tmp_dir / "Content").rename(tmp_dir / "content")
        else:
            raise FileNotFoundError(
                "This mod does not appear to have a valid folder structure"
            )

    if (tmp_dir / "rules.txt").exists():
        (tmp_dir / "rules.txt").unlink()

    if "showDepends" in meta:
        del meta["showDepends"]
    depend_string = f"{meta['name']}=={meta['version']}"
    meta["id"] = urlsafe_b64encode(depend_string.encode("utf8")).decode("utf8")
    any_platform = (
        options.get("options", dict()).get("general", dict()).get("agnostic", False)
    )
    meta["platform"] = (
        "any" if any_platform else "wiiu" if util.get_settings("wiiu") else "switch"
    )
    (tmp_dir / "info.json").write_text(
        dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    with Pool() as pool:
        yml_files = set(tmp_dir.glob("**/*.yml"))
        if yml_files:
            print("Compiling YAML documents...")
            pool.map(_do_yml, yml_files)

        hashes = util.get_hash_table(util.get_settings("wiiu"))
        print("Packing SARCs...")
        _pack_sarcs(tmp_dir, hashes, pool)
        for folder in {d for d in tmp_dir.glob("options/*") if d.is_dir()}:
            _pack_sarcs(folder, hashes, pool)

        for option_dir in tmp_dir.glob("options/*"):
            for file in {
                f
                for f in option_dir.rglob("**/*")
                if (f.is_file() and (tmp_dir / f.relative_to(option_dir)).exists())
            }:
                data1 = (tmp_dir / file.relative_to(option_dir)).read_bytes()
                data2 = file.read_bytes()
                if data1 == data2:
                    util.vprint(
                        f"Removing {file} from option {option_dir.name}, "
                        "identical to base mod"
                    )
                    file.unlink()
                del data1
                del data2

        if not options:
            options = {"disable": [], "options": {}}
        options["options"]["texts"] = {"all_langs": True}

        try:
            _make_bnp_logs(tmp_dir, options)
            for option_dir in {d for d in tmp_dir.glob("options/*") if d.is_dir()}:
                _make_bnp_logs(option_dir, options)
        except Exception as err:  # pylint: disable=broad-except
            pool.terminate()
            raise Exception(
                f"There was an error generating change logs for your mod. {str(err)}"
            )

        _clean_sarcs(tmp_dir, hashes, pool)
        for folder in {d for d in tmp_dir.glob("options/*") if d.is_dir()}:
            _clean_sarcs(folder, hashes, pool)

    print("Cleaning any junk files...")
    for file in {f for f in tmp_dir.rglob("**/*") if f.is_file()}:
        if "logs" in file.parts:
            continue
        if (
            file.suffix in {".yml", ".json", ".bak", ".tmp", ".old"}
            and file.stem != "info"
        ):
            file.unlink()

    print("Removing blank folders...")
    for folder in reversed(list(tmp_dir.rglob("**/*"))):
        if folder.is_dir() and not list(folder.glob("*")):
            shutil.rmtree(folder)

    print(f"Saving output file to {str(output)}...")
    x_args = [install.ZPATH, "a", str(output), f'{str(tmp_dir / "*")}']
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
    shutil.rmtree(tmp_dir, ignore_errors=True)
    print("Conversion complete.")


def process_cp_mod(mod: Path):
    def nx2u(nx_text: str) -> str:
        return (
            nx_text.replace("\\\\", "/")
            .replace("\\", "/")
            .replace("01007EF00011E000/romfs", "content")
            .replace("01007EF00011F001/romfs", "aoc/0010")
        )

    def u2nx(u_text: str) -> str:
        return (
            u_text.replace("\\\\", "/")
            .replace("\\", "/")
            .replace("content", "01007EF00011E000/romfs")
            .replace("aoc/0010", "01007EF00011F001/romfs")
        )

    wiiu = (mod / "content").exists() or (mod / "aoc").exists()
    if wiiu == util.get_settings("wiiu"):
        return
    if (mod / "logs").exists() and len({d for d in mod.glob("*") if d.is_dir()}) == 1:
        return
    easy_logs = [
        mod / "logs" / "packs.json",
        mod / "logs" / "rstb.log",
        mod / "logs" / "deepmerge.yml",
    ]

    if util.get_settings("wiiu") and not wiiu:
        if (mod / "01007EF00011E000").exists():
            shutil.move(mod / "01007EF00011E000" / "romfs", mod / "content")
            shutil.rmtree(mod / "01007EF00011E000")
        if (mod / "01007EF00011F001").exists():
            (mod / "aoc").mkdir(parents=True, exist_ok=True)
            shutil.move(mod / "01007EF00011F001" / "romfs", mod / "aoc" / "0010")
            shutil.rmtree(mod / "01007EF00011F001")
        for log in easy_logs:
            if log.exists():
                log.write_text(nx2u(log.read_text()))

    elif not util.get_settings("wiiu") and wiiu:
        if (mod / "content").exists():
            (mod / "01007EF00011E000").mkdir(parents=True, exist_ok=True)
            shutil.move(mod / "content", mod / "01007EF00011E000" / "romfs")
        if (mod / "aoc").exists():
            (mod / "01007EF00011F001").mkdir(parents=True, exist_ok=True)
            shutil.move(mod / "aoc" / "0010", mod / "01007EF00011F001" / "romfs")
            shutil.rmtree(mod / "aoc")
        for log in easy_logs:
            if log.exists():
                log.write_text(u2nx(log.read_text()))

    aamp_log: Path = mod / "logs" / "deepmerge.aamp"
    if aamp_log.exists() and util.get_settings("wiiu") != wiiu:
        pio = oead.aamp.ParameterIO.from_binary(aamp_log.read_bytes())
        from_content = (
            "content"
            if wiiu and not util.get_settings("wiiu")
            else "01007EF00011E000/romfs"
        )
        to_content = (
            "01007EF00011E000/romfs"
            if wiiu and not util.get_settings("wiiu")
            else "content"
        )
        from_dlc = (
            "aoc/0010"
            if wiiu and not util.get_settings("wiiu")
            else "01007EF00011F001/romfs"
        )
        to_dlc = (
            "01007EF00011F001/romfs"
            if wiiu and not util.get_settings("wiiu")
            else "aoc/0010"
        )
        for file_num, file in pio.objects["FileTable"].params.items():
            old_path = file.v
            new_path = old_path.replace(from_content, to_content).replace(
                from_dlc, to_dlc
            )
            pio.objects["FileTable"].params[file_num] = oead.aamp.Parameter(new_path)
            pio.lists[new_path] = deepcopy(pio.lists[old_path])
            del pio.lists[old_path]
        aamp_log.write_bytes(pio.to_binary())

    if (mod / "options").exists():
        for opt in {d for d in (mod / "options").glob("*") if d.is_dir()}:
            process_cp_mod(opt)
