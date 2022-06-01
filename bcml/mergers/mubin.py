"""Handles diffing and merging map files"""
# Copyright 2020 Nicene Nerd <macadamiadaze@gmail.com>
# Licensed under GPLv3+
import multiprocessing
import shutil
from collections import namedtuple
from functools import partial
from multiprocessing import Pool
from pathlib import Path
from typing import Dict, Union, List, Tuple
from zlib import crc32

import oead
from oead.byml import Hash, Array  # pylint: disable=import-error
import rstb
import rstb.util

from bcml import bcml as rsext
from bcml import util, mergers

Map = namedtuple("Map", "section type")


def consolidate_map_files(modded_maps: List[Path]) -> List[Map]:
    return sorted(
        {
            Map(*(path.stem.split("_")))
            for path in modded_maps
            if not any(part.startswith("_") for part in Path(path).parts)
        }
    )


def get_stock_map(map_unit: Union[Map, tuple], force_vanilla: bool = False) -> Hash:
    if isinstance(map_unit, tuple):
        map_unit = Map(*map_unit)
    try:
        aoc_dir = util.get_aoc_dir()
    except FileNotFoundError:
        force_vanilla = True
    map_bytes = None
    map_path: Union[str, Path]
    if force_vanilla:
        try:
            if util.get_settings("wiiu"):
                update = util.get_update_dir()
            else:
                update = util.get_game_dir()
            map_path = (
                update / "Map/MainField/"
                f"{map_unit.section}/{map_unit.section}_{map_unit.type}.smubin"
            )
            if not map_path.exists():
                map_path = (
                    util.get_game_dir() / "Map/MainField/"
                    f"{map_unit.section}/{map_unit.section}_{map_unit.type}.smubin"
                )
            map_bytes = map_path.read_bytes()
        except FileNotFoundError:
            try:
                title_pack = oead.Sarc(
                    util.get_game_file("Pack/TitleBG.pack").read_bytes()
                )
                map_bytes = title_pack.get_file(
                    f"Map/MainField/{map_unit.section}/{map_unit.section}_{map_unit.type}"
                    ".smubin"
                ).data
            except (KeyError, RuntimeError, AttributeError):
                map_bytes = None
    else:
        if (aoc_dir / "Pack" / "AocMainField.pack").exists():
            try:
                map_pack = oead.Sarc(
                    (aoc_dir / "Pack" / "AocMainField.pack").read_bytes()
                )
                map_bytes = map_pack.get_file(
                    f"Map/MainField/{map_unit.section}/{map_unit.section}_{map_unit.type}"
                    ".smubin"
                ).data
            except (KeyError, RuntimeError, AttributeError):
                map_bytes = None
        if not map_bytes:
            map_path = f"Map/MainField/{map_unit.section}/{map_unit.section}_{map_unit.type}.smubin"
            try:
                map_bytes = util.get_game_file(map_path, aoc=True).read_bytes()
            except FileNotFoundError:
                try:
                    map_bytes = util.get_game_file(map_path).read_bytes()
                except FileNotFoundError:
                    try:
                        title_pack = oead.Sarc(
                            util.get_game_file("Pack/TitleBG.pack").read_bytes()
                        )
                        map_bytes = bytes(
                            title_pack.get_file(
                                f"Map/MainField/{map_unit.section}/"
                                f"{map_unit.section}_{map_unit.type}.smubin"
                            ).data
                        )
                    except (KeyError, RuntimeError, AttributeError):
                        map_bytes = None
    if not map_bytes:
        raise FileNotFoundError(
            f"The stock map file {map_unit.section}_{map_unit.type}.smubin could not be found."
        )
    map_bytes = util.decompress(map_bytes)
    return oead.byml.from_binary(map_bytes)


def get_modded_map(map_unit: Union[Map, tuple], tmp_dir: Path) -> Hash:
    if isinstance(map_unit, tuple):
        map_unit = Map(*map_unit)
    map_bytes = None
    aoc_dir = (
        tmp_dir
        / util.get_dlc_path()
        / ("0010/content" if util.get_settings("wiiu") else "")
    )
    if not aoc_dir.exists():
        aoc_dir = tmp_dir / util.get_dlc_path() / "content" / "0010"
        if not aoc_dir.exists():
            aoc_dir = tmp_dir / util.get_dlc_path() / "0010"
    if (aoc_dir / "Pack" / "AocMainField.pack").exists():
        try:
            map_pack = oead.Sarc((aoc_dir / "Pack" / "AocMainField.pack").read_bytes())
        except (RuntimeError, ValueError, oead.InvalidDataError):
            pass
        else:
            try:
                map_bytes = bytes(
                    map_pack.get_file(
                        f"Map/MainField/{map_unit.section}/"
                        f"{map_unit.section}_{map_unit.type}.smubin"
                    ).data
                )
            except AttributeError:
                pass
    if not map_bytes:
        if (
            aoc_dir
            / "Map"
            / "MainField"
            / map_unit.section
            / f"{map_unit.section}_{map_unit.type}.smubin"
        ).exists():
            map_bytes = (
                aoc_dir
                / "Map"
                / "MainField"
                / map_unit.section
                / f"{map_unit.section}_{map_unit.type}.smubin"
            ).read_bytes()
        elif (
            tmp_dir
            / util.get_content_path()
            / "Map"
            / "MainField"
            / map_unit.section
            / f"{map_unit.section}_{map_unit.type}.smubin"
        ).exists():
            map_bytes = (
                tmp_dir
                / util.get_content_path()
                / "Map"
                / "MainField"
                / map_unit.section
                / f"{map_unit.section}_{map_unit.type}.smubin"
            ).read_bytes()
    if not map_bytes:
        raise FileNotFoundError(
            f"Oddly, the modded map {map_unit.section}_{map_unit.type}.smubin "
            "could not be found."
        )
    map_bytes = util.decompress(map_bytes)
    return oead.byml.from_binary(map_bytes)


def get_map_diff(map_unit: Map, tmp_dir: Path, new_hashes: bool = False) -> Hash:
    mod_map = get_modded_map(map_unit, tmp_dir)
    stock_map = True
    for obj in mod_map["Objs"]:
        str_obj = oead.byml.to_text(obj)
        if "IsHardModeActor" in str_obj or "AoC_HardMode_Enabled" in str_obj:
            stock_map = False
            break
    base_map = get_stock_map(map_unit, force_vanilla=stock_map)

    def diff_objs() -> Hash:
        base_hashes = [int(obj["HashId"]) for obj in base_map["Objs"]]
        mod_hashes = [int(obj["HashId"]) for obj in mod_map["Objs"]]

        diffs = Hash()
        diffs["add"] = Array(
            [obj for obj in mod_map["Objs"] if int(obj["HashId"]) not in base_hashes]
        )
        diffs["mod"] = Hash(
            {
                str(obj["HashId"]): obj
                for obj in mod_map["Objs"]
                if int(obj["HashId"]) in base_hashes
                and obj != base_map["Objs"][base_hashes.index(int(obj["HashId"]))]
            }
        )
        diffs["del"] = Array(
            [
                oead.U32(h)
                for h in {
                    hash_id for hash_id in base_hashes if hash_id not in mod_hashes
                }
            ]
        )

        if new_hashes:
            hash_map: Dict[int, int] = {}
            for obj in diffs["add"]:
                new_hash = crc32(oead.byml.to_text(obj).encode("utf8"))
                hash_map[obj["HashId"].v] = new_hash
                obj["HashId"] = oead.U32(new_hash)
            for obj in [*diffs["add"], *[v for k, v in diffs["mod"].items()]]:
                if "LinksToObj" in obj:
                    for link in obj["LinksToObj"]:
                        if link["DestUnitHashId"].v in hash_map:
                            link["DestUnitHashId"] = oead.U32(
                                hash_map[link["DestUnitHashId"].v]
                            )
        return diffs

    def diff_rails() -> Hash:
        base_hashes = [int(rail["HashId"]) for rail in base_map["Rails"]]
        mod_hashes = [int(rail["HashId"]) for rail in mod_map["Rails"]]

        diffs = Hash()
        diffs["add"] = Array(
            [
                rail
                for rail in mod_map["Rails"]
                if int(rail["HashId"]) not in base_hashes
            ]
        )
        diffs["mod"] = Hash(
            {
                str(rail["HashId"]): rail
                for rail in mod_map["Rails"]
                if int(rail["HashId"]) in base_hashes
                and rail != base_map["Rails"][base_hashes.index(int(rail["HashId"]))]
            }
        )
        diffs["del"] = Array(
            [
                oead.U32(h)
                for h in {
                    hash_id for hash_id in base_hashes if hash_id not in mod_hashes
                }
            ]
        )
        return diffs

    return (
        "_".join(map_unit),
        oead.byml.to_text(
            Hash(
                {
                    "Objs": diff_objs(),
                    "Rails": diff_rails() if map_unit.type == "Static" else Hash(),
                }
            )
        ),
    )


def generate_modded_map_log(
    tmp_dir: Path,
    modded_mubins: List[Path],
    pool: multiprocessing.pool.Pool = None,
    new_hashes: bool = False,
) -> Hash:
    modded_maps = consolidate_map_files(modded_mubins)
    this_pool = pool or Pool(maxtasksperchild=500)
    diffs = oead.byml.Hash(
        {
            map_unit: oead.byml.from_text(diff)
            for map_unit, diff in this_pool.imap_unordered(
                partial(get_map_diff, tmp_dir=tmp_dir, new_hashes=new_hashes),
                modded_maps,
            )
        }
    )
    if not pool:
        this_pool.close()
        this_pool.join()
    return diffs


def merge_map(
    map_pair: tuple, rstb_calc: rstb.SizeCalculator
) -> Dict[str, Tuple[str, int]]:
    map_unit, changes = map_pair[0], map_pair[1]
    util.vprint(f'Merging {len(changes)} versions of {"_".join(map_unit)}...')
    new_map = get_stock_map(map_unit)
    stock_obj_hashes = [int(obj["HashId"]) for obj in new_map["Objs"]]
    for hash_id, actor in changes["Objs"]["mod"].items():
        try:
            new_map["Objs"][stock_obj_hashes.index(int(hash_id))] = actor
        except ValueError:
            changes["Objs"]["add"].append(actor)
    for map_del in sorted(
        changes["Objs"]["del"],
        key=lambda change: stock_obj_hashes.index(change)
        if change in stock_obj_hashes
        else -1,
        reverse=True,
    ):
        if int(map_del) in stock_obj_hashes:
            try:
                new_map["Objs"].pop(stock_obj_hashes.index(map_del))
            except IndexError:
                try:
                    obj_to_delete = next(
                        iter(
                            [
                                actor
                                for actor in new_map["Objs"]
                                if actor["HashId"] == map_del
                            ]
                        )
                    )
                    new_map["Objs"].remove(obj_to_delete)
                except (StopIteration, ValueError):
                    util.vprint(f"Could not delete actor with HashId {map_del}")
    new_map["Objs"].extend(
        [
            change
            for change in changes["Objs"]["add"]
            if int(change["HashId"]) not in stock_obj_hashes
        ]
    )
    new_map["Objs"] = sorted(new_map["Objs"], key=lambda actor: int(actor["HashId"]))

    if len(new_map["Rails"]):
        stock_rail_hashes = [int(rail["HashId"]) for rail in new_map["Rails"]]
        for hash_id, rail in changes["Rails"]["mod"].items():
            try:
                new_map["Rails"][stock_rail_hashes.index(int(hash_id))] = rail
            except ValueError:
                changes["Rails"]["add"].append(rail)
        for map_del in sorted(
            changes["Rails"]["del"],
            key=lambda change: stock_rail_hashes.index(int(change))
            if int(change) in stock_rail_hashes
            else -1,
            reverse=True,
        ):
            if int(map_del) in stock_rail_hashes:
                try:
                    new_map["Rails"].pop(stock_rail_hashes.index(int(map_del)))
                except IndexError:
                    try:
                        obj_to_delete = next(
                            iter(
                                [
                                    rail
                                    for rail in new_map["Rails"]
                                    if rail["HashId"] == map_del
                                ]
                            )
                        )
                        new_map["Rails"].remove(obj_to_delete)
                    except (StopIteration, ValueError):
                        util.vprint(f"Could not delete rail with HashId {map_del}")
        new_map["Rails"].extend(
            [
                change
                for change in changes["Rails"]["add"]
                if int(change["HashId"]) not in stock_rail_hashes
            ]
        )
        new_map["Rails"] = sorted(
            new_map["Rails"], key=lambda rail: int(rail["HashId"])
        )

    aoc_out: Path = (
        util.get_master_modpack_dir()
        / util.get_dlc_path()
        / ("0010" if util.get_settings("wiiu") else "")
        / "Map"
        / "MainField"
        / map_unit.section
        / f"{map_unit.section}_{map_unit.type}.smubin"
    )
    aoc_out.parent.mkdir(parents=True, exist_ok=True)
    aoc_bytes = oead.byml.to_binary(new_map, big_endian=util.get_settings("wiiu"))
    aoc_out.write_bytes(util.compress(aoc_bytes))
    new_map["Objs"] = [
        obj
        for obj in new_map["Objs"]
        if not str(obj["UnitConfigName"]).startswith("DLC")
    ]
    (
        util.get_master_modpack_dir()
        / util.get_content_path()
        / "Map"
        / "MainField"
        / map_unit.section
    ).mkdir(parents=True, exist_ok=True)
    base_out = (
        util.get_master_modpack_dir()
        / util.get_content_path()
        / "Map"
        / "MainField"
        / map_unit.section
        / f"{map_unit.section}_{map_unit.type}.smubin"
    )
    base_out.parent.mkdir(parents=True, exist_ok=True)
    base_bytes = oead.byml.to_binary(new_map, big_endian=util.get_settings("wiiu"))
    base_out.write_bytes(util.compress(base_bytes))
    return {
        util.get_dlc_path(): (
            f"Aoc/0010/Map/MainField/{map_unit.section}/{map_unit.section}_{map_unit.type}.mubin",
            rstb_calc.calculate_file_size_with_ext(
                bytes(aoc_bytes), util.get_settings("wiiu"), ".mubin"
            ),
        ),
        "main": (
            f"Map/MainField/{map_unit.section}/{map_unit.section}_{map_unit.type}.mubin",
            rstb_calc.calculate_file_size_with_ext(
                bytes(base_bytes), util.get_settings("wiiu"), ".mubin"
            ),
        ),
    }


def get_dungeonstatic_diff(mod_pos: Array) -> dict:
    try:
        base_pos = oead.byml.from_binary(
            util.decompress(
                (util.get_aoc_dir() / "Map" / "CDungeon" / "Static.smubin").read_bytes()
            )
        )["StartPos"]
    except FileNotFoundError:
        base_pos = oead.byml.from_binary(
            util.get_nested_file_bytes(
                f"{util.get_game_file('Pack/Bootup.pack')}//Map/CDungeon/Static.smubin"
            )
        )["StartPos"]

    base_dungeons = [str(dungeon["Map"]) for dungeon in base_pos]
    diffs = {}
    for dungeon in mod_pos:
        if str(dungeon["Map"]) not in base_dungeons:
            diffs[dungeon["Map"]] = dungeon
        else:
            base_dungeon = base_pos[base_dungeons.index(str(dungeon["Map"]))]
            if dungeon["Rotate"] != base_dungeon["Rotate"]:
                diffs[dungeon["Map"]] = {"Rotate": dungeon["Rotate"]}
            if dungeon["Translate"] != base_dungeon["Translate"]:
                if dungeon["Map"] not in diffs:
                    diffs[dungeon["Map"]] = {}
                diffs[dungeon["Map"]]["Translate"] = dungeon["Translate"]

    return diffs


def merge_dungeonstatic(diffs: dict = None):
    """Merges all changes to the CDungeon Static.smubin"""
    if not diffs:
        try:
            (util.get_master_modpack_dir() / "logs" / "dungeonstatic.smubin").unlink()
        except:
            pass
        return

    try:
        new_static = oead.byml.from_binary(
            util.decompress(
                (util.get_aoc_dir() / "Map" / "CDungeon" / "Static.smubin").read_bytes()
            )
        )
    except FileNotFoundError:
        new_static = oead.byml.from_binary(
            util.get_nested_file_bytes(
                f"{util.get_game_file('Pack/Bootup.pack')}//Map/CDungeon/Static.smubin"
            )
        )

    base_dungeons = [str(dungeon["Map"]) for dungeon in new_static["StartPos"]]
    for dungeon, diff in diffs.items():
        if dungeon not in base_dungeons:
            new_static["StartPos"].append(diff)
        else:
            for key, value in diff.items():
                new_static["StartPos"][base_dungeons.index(dungeon)][key] = value

    data = util.compress(
        oead.byml.to_binary(new_static, big_endian=util.get_settings("wiiu"))
    )
    try:
        util.get_aoc_dir()
        output_static = (
            util.get_master_modpack_dir()
            / util.get_dlc_path()
            / ("0010" if util.get_settings("wiiu") else "")
            / "Map"
            / "CDungeon"
            / "Static.smubin"
        )
    except FileNotFoundError:
        output_static = util.get_master_modpack_dir() / "logs" / "dungeonstatic.smubin"
        util.inject_file_into_sarc(
            "Map/CDungeon/Static.smubin",
            data,
            "Pack/Bootup.pack",
            create_sarc=True,
        )
    output_static.parent.mkdir(parents=True, exist_ok=True)
    output_static.write_bytes(data)


def parse_legacy_diff(text: str) -> Hash:
    diff = oead.byml.from_text(text)
    return Hash(
        {
            unit: Hash({"Objs": changes, "Rails": Hash()})
            for unit, changes in diff.items()
        }
    )


class MapMerger(mergers.Merger):
    # pylint: disable=abstract-method
    NAME: str = "maps"

    def __init__(self):
        super().__init__(
            "maps", "Merges changes to actors in mainfield map units", "map.yml"
        )

    def generate_diff(self, mod_dir: Path, modded_files: List[Union[Path, str]]):
        modded_mubins = [
            file
            for file in modded_files
            if isinstance(file, Path)
            and "MainField" in file.parts
            and file.suffix == ".smubin"
            and not file.name.startswith("_")
            and "_" in file.name
        ]
        if modded_mubins:
            print("Logging changes to mainfield maps...")
            return generate_modded_map_log(
                mod_dir,
                modded_mubins,
                pool=self._pool,
                new_hashes=self._options.get("new_hashes", False),
            )
        return {}

    def log_diff(self, mod_dir: Path, diff_material):
        if isinstance(diff_material, List):
            diff_material = self.generate_diff(mod_dir, diff_material)
        if diff_material:
            (mod_dir / "logs" / self._log_name).write_text(
                oead.byml.to_text(diff_material), encoding="utf-8"
            )

    def get_mod_diff(self, mod: util.BcmlMod):
        diffs = []
        if self.is_mod_logged(mod):
            diff_text = (mod.path / "logs" / self._log_name).read_text(encoding="utf-8")
            diff: Hash
            if not ("Rails" in diff_text and "Objs" in diff_text):
                diff = parse_legacy_diff(diff_text)
            else:
                diff = oead.byml.from_text(diff_text)
            diffs.append(diff)
        for opt in {d for d in (mod.path / "options").glob("*") if d.is_dir()}:
            if (opt / "logs" / self._log_name).exists():
                diff_text = (opt / "logs" / self._log_name).read_text(encoding="utf-8")
                if not ("Rails" in diff_text and "Objs" in diff_text):
                    diff = parse_legacy_diff(diff_text)
                else:
                    diff = oead.byml.from_text(diff_text)
                diffs.append(diff)
        return diffs

    def get_all_diffs(self):
        diffs = []
        for mod in util.get_installed_mods():
            diffs.extend(self.get_mod_diff(mod))
        return diffs

    def consolidate_diffs(self, diffs: list):
        a_diffs = Hash()
        for mod_diff in diffs:
            for file, diff in mod_diff.items():
                # a_map = Map(*file.split("_"))
                if file not in a_diffs:
                    a_diffs[file] = Array()
                a_diffs[file].append(diff)
        c_diffs = Hash()
        for file, mods in a_diffs.items():
            c_diffs[file] = Hash(
                {
                    "Objs": Hash(
                        {
                            "add": Array(),
                            "mod": Hash(),
                            "del": Array(
                                [
                                    oead.U32(h)
                                    for h in set(
                                        [
                                            hash_id.v
                                            for hashes in [
                                                mod["Objs"]["del"]
                                                for mod in mods
                                                if "Objs" in mod
                                                and "del" in mod["Objs"]
                                            ]
                                            for hash_id in hashes
                                        ]
                                    )
                                ]
                            ),
                        }
                    ),
                    "Rails": Hash(
                        {
                            "add": Array(),
                            "mod": Hash(),
                            "del": Array(
                                [
                                    oead.U32(h)
                                    for h in set(
                                        [
                                            hash_id.v
                                            for hashes in [
                                                mod["Rails"]["del"]
                                                for mod in mods
                                                if "Rails" in mod
                                                and "del" in mod["Rails"]
                                            ]
                                            for hash_id in hashes
                                        ]
                                    )
                                ]
                            ),
                        }
                    ),
                }
            )
            for mod in [m for m in mods if "Objs" in m and "mod" in m["Objs"]]:
                for hash_id, actor in mod["Objs"]["mod"].items():
                    c_diffs[file]["Objs"]["mod"][hash_id] = actor
            for mod in [m for m in mods if "Rails" in m and "mod" in m["Rails"]]:
                for hash_id, actor in mod["Rails"]["mod"].items():
                    c_diffs[file]["Rails"]["mod"][hash_id] = actor
            add_obj_hashes = []
            add_rail_hashes = []
            for mod in reversed(mods):
                if "add" in mod["Objs"]:
                    for actor in mod["Objs"]["add"]:
                        if actor["HashId"] not in add_obj_hashes:
                            add_obj_hashes.append(actor["HashId"])
                            c_diffs[file]["Objs"]["add"].append(actor)
                if "add" in mod["Rails"]:
                    for actor in mod["Rails"]["add"]:
                        if actor["HashId"] not in add_rail_hashes:
                            add_rail_hashes.append(actor["HashId"])
                            c_diffs[file]["Rails"]["add"].append(actor)
        return c_diffs

    @util.timed
    def perform_merge(self):
        shutil.rmtree(
            str(
                util.get_master_modpack_dir()
                / util.get_dlc_path()
                / ("0010" if util.get_settings("wiiu") else "")
                / "Map"
                / "MainField"
            ),
            ignore_errors=True,
        )
        shutil.rmtree(
            str(
                util.get_master_modpack_dir()
                / util.get_content_path()
                / "Map"
                / "MainField"
            ),
            ignore_errors=True,
        )
        log_path = util.get_master_modpack_dir() / "logs" / "map.log"
        if log_path.exists():
            log_path.unlink()
        print("Loading map mods...")
        map_diffs = self.consolidate_diffs(self.get_all_diffs())
        if not map_diffs:
            print("No map merge necessary")
            return
        aoc_pack = (
            util.get_master_modpack_dir()
            / util.get_dlc_path()
            / ("0010" if util.get_settings("wiiu") else "")
            / "Pack"
            / "AocMainField.pack"
        )
        if not aoc_pack.exists() or aoc_pack.stat().st_size > 0:
            print("Emptying AocMainField.pack...")
            aoc_pack.parent.mkdir(parents=True, exist_ok=True)
            aoc_pack.write_bytes(b"")

        rstb_vals = rsext.mergers.maps.merge_maps(oead.byml.to_binary(map_diffs, True))
        # rstb_calc = rstb.SizeCalculator()
        print("Merging modded map units...")

        # pool = self._pool or Pool(maxtasksperchild=500)
        # rstb_results = pool.map(
        # partial(merge_map, rstb_calc=rstb_calc),
        # map_diffs.items(),
        # )
        # for result in rstb_results:
        # rstb_vals[result[util.get_dlc_path()][0]] = result[util.get_dlc_path()][1]
        # rstb_vals[result["main"][0]] = result["main"][1]
        # if not self._pool:
        # pool.close()
        # pool.join()

        stock_static = [m for m in map_diffs if m[1] == "Static"]
        if stock_static:
            title_path = (
                util.get_master_modpack_dir()
                / util.get_content_path()
                / "Pack"
                / "TitleBG.pack"
            )
            if not title_path.exists():
                title_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(util.get_game_file("Pack/TitleBG.pack"), title_path)
            title_bg: oead.SarcWriter = oead.SarcWriter.from_sarc(
                oead.Sarc(title_path.read_bytes())
            )
            for static in stock_static:
                del title_bg.files[
                    f"Map/MainField/{static[0]}/{static[0]}_Static.smubin"
                ]
            title_path.write_bytes(title_bg.write()[1])
        print("Adjusting RSTB...")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("w", encoding="utf-8") as l_file:
            for canon, val in rstb_vals.items():
                l_file.write(f"{canon},{val}\n")
        print("Map merge complete")

    def get_checkbox_options(self):
        return [
            ("new_hashes", "Generate unique hashes for added map actors"),
        ]

    def get_mod_edit_info(self, mod: util.BcmlMod) -> set:
        return {
            f"{key.section}_{key.type}"
            for key in self.consolidate_diffs(self.get_mod_diff(mod))
        }


class DungeonStaticMerger(mergers.Merger):
    # pylint: disable=abstract-method
    NAME: str = "dungeonstatic"

    def __init__(self):
        super().__init__(
            "shrine entrances",
            "Merges changes to shrine entrance coordinates",
            "dstatic.yml",
            options={},
        )

    def generate_diff(self, mod_dir: Path, modded_files: List[Union[Path, str]]):
        dstatic_path = (
            mod_dir
            / util.get_dlc_path()
            / "0010"
            / "Map"
            / "CDungeon"
            / "Static.smubin"
        )
        if dstatic_path.exists():
            print("Logging changes to shrine entry coordinates...")
            return get_dungeonstatic_diff(
                oead.byml.from_binary(util.decompress(dstatic_path.read_bytes()))[
                    "StartPos"
                ]
            )
        elif (
            f"{util.get_content_path()}/Pack/Bootup.pack//Map/CDungeon/Static.smubin"
            in modded_files
        ):
            return get_dungeonstatic_diff(
                oead.byml.from_binary(
                    util.get_nested_file_bytes(
                        f"{mod_dir}/{util.get_content_path()}/Pack/Bootup.pack//Map/CDungeon/Static.smubin"
                    )
                )["StartPos"]
            )
        else:
            return {}

    def log_diff(self, mod_dir: Path, diff_material):
        if isinstance(diff_material, List):
            diff_material = self.generate_diff(mod_dir, diff_material)
        if diff_material:
            (mod_dir / "logs" / self._log_name).write_text(
                oead.byml.to_text(diff_material), encoding="utf-8"
            )

    def get_mod_diff(self, mod: util.BcmlMod):
        diffs = Hash()
        if self.is_mod_logged(mod):
            util.dict_merge(
                diffs,
                oead.byml.from_text(
                    (mod.path / "logs" / self._log_name).read_text(encoding="utf-8")
                ),
                overwrite_lists=True,
            )
        for opt in {d for d in (mod.path / "options").glob("*") if d.is_dir()}:
            if (opt / "logs" / self._log_name).exists():
                util.dict_merge(
                    diffs,
                    oead.byml.from_text(
                        (opt / "logs" / self._log_name).read_text("utf-8")
                    ),
                    overwrite_lists=True,
                )
        return diffs

    def get_all_diffs(self):
        diffs = []
        for mod in [
            mod for mod in util.get_installed_mods() if self.is_mod_logged(mod)
        ]:
            diffs.append(self.get_mod_diff(mod))
        return diffs

    def consolidate_diffs(self, diffs: list):
        all_diffs = {}
        for diff in diffs:
            all_diffs.update(diff)
        return all_diffs

    @util.timed
    def perform_merge(self):
        merge_dungeonstatic(self.consolidate_diffs(self.get_all_diffs()))

    def get_checkbox_options(self):
        return []

    @staticmethod
    def is_bootup_injector():
        try:
            util.get_aoc_dir()
            return False
        except FileNotFoundError:
            return True

    def get_bootup_injection(self):
        tmp_sarc = util.get_master_modpack_dir() / "logs" / "dungeonstatic.smubin"
        if tmp_sarc.exists():
            return (
                "Map/CDungeon/Static.smubin",
                tmp_sarc,
            )
        return

    def get_mod_edit_info(self, mod: util.BcmlMod) -> set:
        return set(self.get_mod_diff(mod).keys())
