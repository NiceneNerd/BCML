# pylint: disable=unsupported-assignment-operation,no-member
import multiprocessing
import shutil
import subprocess
from base64 import urlsafe_b64encode
from fnmatch import fnmatch
from functools import partial
from json import dumps, loads
from multiprocessing import Pool
from pathlib import Path
from platform import system
from tempfile import TemporaryDirectory
from typing import Optional, Union, List, Tuple
from zlib import crc32

import oead
import xxhash  # pylint: disable=wrong-import-order
from botw_havok import Havok

from bcml import util, install
from bcml.util import BYML_EXTS, SARC_EXTS, TempSettingsContext
from bcml.mergers.pack import SPECIAL

EXCLUDE_EXTS = {".yml", ".yaml", ".bak", ".txt", ".json", ".old", ".bnp"}


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


def _package_code(tmp_dir: Path, meta: dict):
    patch_file: Optional[Path] = None
    if (tmp_dir / "patches.txt").exists():
        patch_file = tmp_dir / "patches.txt"
    elif list(tmp_dir.glob("patch_*.asm")):
        patch_file = list(tmp_dir.glob("patch_*.asm"))[0]
    if not patch_file and not (tmp_dir / "patches").exists():
        return
    (tmp_dir / "patches").mkdir(exist_ok=True)
    shutil.move(patch_file, tmp_dir / "patches" / patch_file.name)
    if not (tmp_dir / "patches" / "rules.txt").exists():
        rules = {
            "titleIds": "00050000101C9300,00050000101C9400,00050000101C9500",
            "name": meta["name"] + " - Executable Patch",
            "path": f'"The Legend of Zelda: Breath of the Wild/Mods/{meta["name"]} Patch (BCML)"',
            "description": f"Contains executable patch(es) for {meta['name']}",
            "version": 4,
        }
        nl = "\n"
        (tmp_dir / "patches" / "rules.txt").write_text(
            f"[Definition]{nl}{nl.join(f'{k} = {v}' for k, v in rules.items())}"
        )


def _pack_sarcs(tmp_dir: Path, hashes: dict, pool: multiprocessing.pool.Pool):
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
            if file_name not in old_files or (xhash != old_hash):
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


CLEAN_EXTS = util.SARC_EXTS - {".beventpack", ".sbeventpack"}


def _clean_sarcs(tmp_dir: Path, hashes: dict, pool: multiprocessing.pool.Pool):
    sarc_files = {
        file
        for file in tmp_dir.rglob("**/*")
        if file.suffix in CLEAN_EXTS
        and all(ex not in file.name for ex in SPECIAL)
        and "options" not in file.relative_to(tmp_dir).parts
    }
    if sarc_files:
        print("Creating partial packs...")
        pool.map(partial(_clean_sarc_file, hashes=hashes, tmp_dir=tmp_dir), sarc_files)

    final_packs = {
        file
        for file in tmp_dir.rglob("**/*")
        if file.suffix in CLEAN_EXTS
        and all(ex not in file.name for ex in SPECIAL)
        and "options" not in file.relative_to(tmp_dir).parts
    }
    if final_packs:
        print("Updating pack log...")
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
            if (
                ext in CLEAN_EXTS
                and nest_file in old_files
                and all(ex not in nest_file for ex in SPECIAL)
            ):
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
                if ext.startswith(".s") and ext != ".sarc":
                    file_data = util.compress(file_data)
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

    if (tmp_dir / "logs" / "mainstatic.yml").exists():
        print("Removing MainField/Static.smubin...")
        for file in tmp_dir.rglob("MainField/Static.smubin"):
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
        (
            tmp_dir / util.get_content_path() / "Actor" / "ActorInfo.product.sbyml"
        ).unlink()

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


def create_bnp_mod(mod: Path, output: Path, meta: dict, options: Optional[dict] = None):
    if isinstance(mod, str):
        mod = Path(mod)
    if not options:
        options = {"options": {}, "disable": []}

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
        or (tmp_dir / "patches").exists()
    ):
        if (tmp_dir.parent / util.get_content_path()).exists():
            tmp_dir = tmp_dir.parent
        elif util.get_settings("wiiu") and (tmp_dir / "Content").exists():
            (tmp_dir / "Content").rename(tmp_dir / "content")
        elif not util.get_settings("wiiu") and (
            (tmp_dir / "base").exists() or (tmp_dir / "dlc").exists()
        ):
            if (tmp_dir / "base").exists():
                (tmp_dir / "base").rename(tmp_dir / "01007EF00011E000")
            if (tmp_dir / "dlc").exists():
                (tmp_dir / "dlc").rename(tmp_dir / "01007EF00011F001")
        else:
            raise FileNotFoundError(
                f"This mod does not appear to have a valid folder structure. " +
                f"BCML could not find {mod.name}{'/' if mod.suffix else ''}/{util.get_content_path()} " +
                f"or {mod.name}{'/' if mod.suffix else ''}/{util.get_dlc_path()}"
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
    if options["options"].get("general", {}).get("base_priority", False):
        meta["priority"] = "base"
    (tmp_dir / "info.json").write_text(
        dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    _package_code(tmp_dir, meta)

    with util.start_pool() as pool:
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

        if not util.get_settings("strip_gfx"):
            _clean_sarcs(tmp_dir, hashes, pool)
            for folder in {d for d in tmp_dir.glob("options/*") if d.is_dir()}:
                _clean_sarcs(folder, hashes, pool)

    print("Cleaning any junk files...")
    for file in {f for f in tmp_dir.rglob("**/*") if f.is_file()}:
        if "logs" in file.parts:
            continue
        if (
            file.suffix in {".yml", ".json", ".bak", ".tmp", ".old", ".bnp"}
            and file.stem != "info"
        ):
            file.unlink()

    print("Removing blank folders...")
    for folder in reversed(list(tmp_dir.rglob("**/*"))):
        if folder.is_dir() and not list(folder.glob("*")):
            shutil.rmtree(folder)

    print(f"Saving output file to {str(output)}...")
    if output.exists():
        output.unlink()
    x_args = [util.get_7z_path(), "a", str(output), f'{str(tmp_dir / "*")}']
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
    shutil.rmtree(tmp_dir, ignore_errors=True)
    print("Conversion complete.")


NO_CONVERT_EXTS = {
    ".sbfres",
    ".bfres",
    ".bcamanim",
    ".sbcamanim",
    ".hkcl",
    ".hkrg",
    ".sesetlist",
    ".sbfarc",
    ".shknm2",
    ".shktmrb",
    ".bfstm",
    ".bars",
    ".sbreviewtex",
    ".sbitemico",
    ".sstats",
    ".sbstftex",
    ".sblarc",
    ".bfsar",
    ".sbmapopen",
    ".sbmaptex",
}


def _convert_actorpack(actor_pack: Path, to_wiiu: bool) -> Union[None, str]:
    error = None
    sarc = oead.Sarc(util.unyaz_if_needed(actor_pack.read_bytes()))
    new_sarc = oead.SarcWriter.from_sarc(sarc)
    new_sarc.set_endianness(oead.Endianness.Big if to_wiiu else oead.Endianness.Little)
    for file in sarc.get_files():
        if "Physics/" in file.name and "Actor/" not in file.name:
            ext = file.name[file.name.rindex(".") :]
            if ext in NO_CONVERT_EXTS:
                if not util.is_file_modded(
                    util.get_canon_name(file.name, allow_no_source=True),
                    file.data,
                    count_new=True,
                ):
                    actor_name = file.name[
                        file.name.rindex("/") : file.name.rindex(".")
                    ]
                    try:
                        pack_path = util.get_game_file(
                            f"Actor/Pack/{actor_name}.sbactorpack"
                        )
                        stock_data = util.get_nested_file_bytes(
                            f"{str(pack_path)}//{file.name}"
                        )
                        if stock_data:
                            new_sarc.files[file.name] = stock_data
                        else:
                            raise FileNotFoundError(file.name)
                    except (FileNotFoundError, AttributeError):
                        error = (
                            "This mod contains a Havok file not supported by the "
                            f"converter: {file.name}"
                        )
                else:
                    error = (
                        "This mod contains a Havok file not supported by the"
                        f" converter: {file.name}"
                    )
            else:
                if file.data[0:4] == b"AAMP":
                    continue
                try:
                    hk = Havok.from_bytes(bytes(file.data))
                except:  # pylint: disable=bare-except
                    return f"Could not parse Havok file {file.name}"
                if to_wiiu:
                    hk.to_wiiu()
                else:
                    hk.to_switch()
                hk.serialize()
                new_sarc.files[file.name] = hk.to_bytes()
        elif file.data[0:2] in {b"BY", b"YB"}:
            by = oead.byml.from_binary(file.data)
            new_sarc.files[file.name] = oead.byml.to_binary(by, big_endian=to_wiiu)
    actor_pack.write_bytes(util.compress(new_sarc.write()[1]))
    return error


def _convert_sarc_file(pack: Path, to_wiiu: bool) -> list:
    data = pack.read_bytes()
    if not data:
        return []
    sarc = oead.Sarc(util.unyaz_if_needed(data))
    new_bytes, error = _convert_sarc(sarc, to_wiiu)
    pack.write_bytes(
        util.compress(new_bytes)
        if pack.suffix.startswith(".s") and pack.suffix != ".sarc"
        else new_bytes
    )
    return error


def _convert_sarc(sarc: oead.Sarc, to_wiiu: bool) -> Tuple[bytes, List[str]]:
    error = []
    new_sarc = oead.SarcWriter.from_sarc(sarc)
    new_sarc.set_endianness(oead.Endianness.Big if to_wiiu else oead.Endianness.Little)
    for file in sarc.get_files():
        ext = file.name[file.name.rindex(".") :]
        if ext in NO_CONVERT_EXTS:
            error.append(
                f"This mod contains a file not supported by the converter: {file.name}"
            )
        elif ext in BYML_EXTS:
            byml = oead.byml.from_binary(util.unyaz_if_needed(file.data))
            data = oead.byml.to_binary(byml, big_endian=to_wiiu)
            if ext.startswith(".s"):
                data = util.compress(data)
            new_sarc.files[file.name] = data
        elif ext in SARC_EXTS and ext not in NO_CONVERT_EXTS:
            nest = oead.Sarc(util.unyaz_if_needed(file.data))
            new_bytes, errs = _convert_sarc(nest, to_wiiu)
            new_sarc.files[file.name] = (
                new_bytes
                if not (ext.startswith(".s") and ext != ".sarc")
                else util.compress(new_bytes)
            )
            error.extend(errs)
    return new_sarc.write()[1], error


def convert_mod(mod: Path, to_wiiu: bool, warn_only: bool = False) -> list:
    warnings = []

    def handle_warning(warning: Union[str, list]) -> None:
        if not warn_only:
            raise ValueError(warning)
        elif isinstance(warning, list):
            for warning_ in warning:
                warnings.append(warning_)
        else:
            warnings.append(warning)

    to_content: str
    from_content: str
    to_aoc: str
    from_aoc: str
    if to_wiiu:
        to_content = "content"
        from_content = "01007EF00011E000/romfs"
        to_aoc = "aoc/0010"
        from_aoc = "01007EF00011F001/romfs"
    else:
        to_content = "01007EF00011E000/romfs"
        from_content = "content"
        to_aoc = "01007EF00011F001/romfs"
        from_aoc = "aoc/0010"

    special_files = {"ActorInfo.product.sbyml"}
    all_files = {
        f for f in mod.rglob("*.*") if f.is_file() and f not in (mod / "options").rglob("*.*")
    }

    for file in all_files:
        if file.suffix in NO_CONVERT_EXTS:
            handle_warning(
                "This mod contains a file which the platform converter does not support:"
                f" {str(file.relative_to(mod)) if 'options' not in mod.parts else str(file.relative_to(mod.parent))}"
            )

    actorinfo_log = mod / "logs" / "actorinfo.yml"
    if actorinfo_log.exists():
        actorinfo = oead.byml.from_text(actorinfo_log.read_text("utf-8"))
        from bcml.mergers.actors import get_stock_actorinfo

        profiles = {
            str(crc32(actor["name"].encode("utf-8"))): actor["profile"]
            for actor in get_stock_actorinfo()["Actors"]
        }
        profile_ratios = {
            "ComplexTag": 1.58580,
            "ArmorLower": 2.77174,
            "MapConstActive": 2.62619,
            "Horse": 1.57119,
            "MapConstPassive": 3.34795,
            "Prey": 1.90845,
            "MapDynamicActive": 2.54314,
            "Anchor": 1.54027,
            "NPC": 1.75036,
            "DemoNPC": 2.44085,
            "MapDynamicPassive": 2.87003,
            "OptionalWeapon": 3.32726,
            "ArmorUpper": 2.11312,
            "ArmorHead": 2.27533,
            "Item": 2.59118,
            "WeaponBow": 2.43674,
            "Enemy": 1.70107,
            "CookResult": 1.47792,
            "HorseSaddle": 2.41971,
            "System": 1.59686,
            "WeaponShield": 2.58867,
            "MergedDungeonParts": 2.26925,
            "NoCalcActor": 1.56243,
            "SoundProxy": 1.57575,
            "WeaponSmallSword": 2.56363,
            "SiteBoss": 1.61253,
            "ActorReaction": 1.95015,
            "WeaponLargeSword": 2.40451,
            "EffectLocater": 1.68679,
            "Beam": 1.58558,
            "SoleTag": 1.60180,
            "GelEnemy": 1.69351,
            "PlayerItem": 1.82444,
            "WeaponSpear": 2.41490,
            "Bullet": 2.12249,
            "LinkTag": 1.67059,
            "ActorOption": 1.47986,
            "GiantEnemy": 1.64212,
            "EventSystem": 1.58667,
            "Dummy": 1.57355,
            "Rope": 2.45780,
            "Guardian": 2.00911,
            "Swarm": 2.29493,
            "GiantArmor": 2.74482,
            "Dragon": 1.62425,
            "GuardianComponent": 2.75823,
            "Remains": 2.23782,
            "CapturedActor": 2.33165,
            "ArmorExtra1": 3.64020,
            "AreaManagementForOthers": 1.56662,
            "SpotBgmTag": 1.54055,
            "Area": 1.57014,
            "AreaManagementForPlayer": 1.57471,
            "LineBeam": 1.58024,
            "EnvSeEmitPoint": 1.59169,
            "DemoEquipment": 2.78588,
            "SoundSystemActor": 1.66232,
            "HorseObject": 1.96967,
            "Motorcycle": 1.89353,
            "Sandworm": 1.66948,
            "GameBlanceLocater": 2.71996,
            "HorseReins": 2.78040,
            "AirWall": 1.55907,
            "NoWork": 1.55033,
            "Weapon": 2.47555,
            "SweepCollision": 1.53318,
            "ArmorExtra0": 3.24801,
            "Player": 1.44917,
            "EnemySwarm": 2.03859,
            "ArmorExtra2": 2.81442,
            "WolfLink": 1.87220,
            "PauseMenuPlayer": 1.86665,
            "LastBoss": 1.68402,
            "StaticAnchor": 1.53173,
            "EditCamera": 1.59361,
            "EventTag": 1.59889,
            "GlobalParameter": 1.55041,
            "Camera": 1.53002,
        }
        for hash_id, actor in [
            (hash_id, actor)
            for hash_id, actor in actorinfo.items()
            if "instSize" in actor
        ]:
            profile = dict(actor).get("profile", profiles.get(hash_id))
            if not profile:
                handle_warning(
                    f"Could not detect profile for actor with hash {hash_id}. "
                    "The instSize value was not converted."
                )
                continue
            ratio = profile_ratios[profile]
            actor["instSize"] = oead.S32(
                int(
                    (
                        (actor["instSize"].v * ratio)
                        if not to_wiiu
                        else (actor["instSize"].v / ratio)
                    )
                    * 1.1 # safety buffer, since we're dealing with averages
                )
            )
        actorinfo_log.write_text(oead.byml.to_text(actorinfo))

    for log in {"drops.json", "packs.json"}:
        log_path = mod / "logs" / log
        if log_path.exists():
            text = log_path.read_text("utf-8").replace("\\\\", "/").replace("\\", "/")
            log_path.write_text(
                text.replace(from_content, to_content).replace(from_aoc, to_aoc),
                "utf-8",
            )

    for log in {"deepmerge.aamp", "shop.aamp", "aslist.aamp"}:
        log_path = mod / "logs" / log
        if log_path.exists():
            pio = oead.aamp.ParameterIO.from_binary(log_path.read_bytes())
            if "deepmerge" in log:
                table = oead.aamp.get_default_name_table()
                for i in range(len(pio.objects["FileTable"].params)):
                    table.add_name(f"File{i}")
            text = pio.to_text().replace("\\\\", "/").replace("\\", "/")
            log_path.write_bytes(
                oead.aamp.ParameterIO.from_text(
                    text.replace(from_content, to_content).replace(from_aoc, to_aoc)
                ).to_binary()
            )

    for file in {
        f for f in all_files if f.suffix in BYML_EXTS and f.name not in special_files
    }:
        byml = oead.byml.from_binary(util.unyaz_if_needed(file.read_bytes()))
        data = oead.byml.to_binary(byml, big_endian=to_wiiu)
        if file.suffix.startswith(".s"):
            data = util.compress(data)
        file.write_bytes(data)

    with util.start_pool() as pool:
        errs = pool.map(
            partial(_convert_actorpack, to_wiiu=to_wiiu),
            {f for f in all_files if f.suffix == ".sbactorpack"},
        )
        for err in errs:
            if err:
                handle_warning(err)

        errs = pool.map(
            partial(_convert_sarc_file, to_wiiu=to_wiiu),  # type: ignore
            {
                f
                for f in all_files
                if f.suffix in SARC_EXTS
                if f.suffix != ".sbactorpack"
            },
        )
        for err in errs:
            if err:
                handle_warning(err)

        if (mod / from_content).exists():
            shutil.move(mod / from_content, mod / to_content)  # type: ignore

        if (mod / from_aoc).exists():
            shutil.move(mod / from_aoc, mod / to_aoc)  # type: ignore

        with TempSettingsContext({"wiiu": to_wiiu}):
            rstb_log = mod / "logs" / "rstb.json"
            if rstb_log.exists():
                # pylint: disable=import-outside-toplevel
                rstb_log.unlink()
                from bcml.install import find_modded_files
                from bcml.mergers.rstable import RstbMerger

                files = find_modded_files(mod, pool)
                merger = RstbMerger()
                merger.set_pool(pool)
                merger.log_diff(mod, files)

    if (mod / "options").exists():
        for folder in {d for d in (mod / "options").glob("*") if d.is_dir()}:
            option_warnings = convert_mod(folder, to_wiiu=to_wiiu, warn_only=warn_only)
            handle_warning(option_warnings)
    
    if (mod / "info.json").exists():
        meta = loads((mod / "info.json").read_text("utf-8"))
        meta["platform"] = "wiiu" if to_wiiu else "switch"
        (mod / "info.json").write_text(dumps(meta, indent=2, ensure_ascii=False), "utf-8")

    return warnings
