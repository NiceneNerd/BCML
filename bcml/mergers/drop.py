import json
import re
from functools import partial
from multiprocessing import Pool
from pathlib import Path
from typing import Union, List

import oead
from oead.aamp import ParameterIO, ParameterList, ParameterObject, Name, Parameter
from bcml import mergers, util


def _drop_to_dict(drop: ParameterIO) -> dict:
    return {
        str(table.v): {
            "repeat_num_min": drop.objects[str(table.v)].params["RepeatNumMin"].v,
            "repeat_num_max": drop.objects[str(table.v)].params["RepeatNumMax"].v,
            "approach_type": drop.objects[str(table.v)].params["ApproachType"].v,
            "occurrence_speed_type": drop.objects[str(table.v)]
            .params["OccurrenceSpeedType"]
            .v,
            "items": {
                str(drop.objects[str(table.v)].params[f"ItemName{i:02}"].v): drop.objects[
                    str(table.v)
                ]
                .params[f"ItemProbability{i:02}"]
                .v
                for i in range(
                    1, int((len(drop.objects[str(table.v)].params) - 5) / 2) + 1
                )
                if f"ItemName{i:02}" in drop.objects[str(table.v)].params
            },
        }
        for param, table in drop.objects["Header"].params.items()
        if param != "TableNum" and str(table.v) in drop.objects
    }


def _dict_to_drop(drop_dict: dict) -> ParameterIO:
    pio = ParameterIO()
    pio.type = "xml"
    header = ParameterObject()
    header.params["TableNum"] = Parameter(len(drop_dict))
    for i, table in enumerate(drop_dict.keys()):
        header.params[f"Table{i + 1:02}"] = Parameter(oead.FixedSafeString64(table))
    pio.objects["Header"] = header
    for i, (table, contents) in enumerate(drop_dict.items()):
        header.params[f"Table{i:02}"] = table
        table_obj = ParameterObject()
        table_obj.params["RepeatNumMin"] = Parameter(contents["repeat_num_min"])
        table_obj.params["RepeatNumMax"] = Parameter(contents["repeat_num_max"])
        table_obj.params["ApproachType"] = Parameter(contents["approach_type"])
        table_obj.params["OccurrenceSpeedType"] = Parameter(
            contents["occurrence_speed_type"]
        )
        table_obj.params["ColumnNum"] = Parameter(len(contents["items"]))
        for i, item in enumerate(contents["items"]):
            table_obj.params[f"ItemName{i + 1:02}"] = Parameter(
                oead.FixedSafeString64(item)
            )
            table_obj.params[f"ItemProbability{i + 1:02}"] = Parameter(
                contents["items"][item]
            )
        pio.objects[table] = table_obj
    return pio


def log_drop_file(file: str, mod_dir: Path):
    drop = ParameterIO.from_binary(util.get_nested_file_bytes(str(mod_dir) + "/" + file))
    drop_table = _drop_to_dict(drop)
    del drop
    try:
        base_file = file[: file.index("//")]
        sub_file = file[file.index("//") :]
        ref_drop = ParameterIO.from_binary(
            util.get_nested_file_bytes(str(util.get_game_file(base_file)) + sub_file)
        )
        ref_table = _drop_to_dict(ref_drop)
        del ref_drop
        for table, contents in drop_table.items():
            if table not in ref_table:
                continue
            for item, prob in {
                (i, p)
                for i, p in contents["items"].items()
                if i in ref_table[table]["items"]
            }:
                if prob == ref_table[table]["items"][item]:
                    drop_table[table]["items"][item] = util.UNDERRIDE
        del ref_table
    except (
        FileNotFoundError,
        oead.InvalidDataError,
        AttributeError,
        RuntimeError,
        ValueError,
    ):
        util.vprint(f"Could not load stock {file}")
    return {file: drop_table}


def merge_drop_file(file: str, drop_table: dict):
    base_path = file[: file.index("//")]
    sub_path = file[file.index("//") :]
    try:
        ref_drop = _drop_to_dict(
            ParameterIO.from_binary(
                util.get_nested_file_bytes(str(util.get_game_file(base_path)) + sub_path)
            )
        )
        for table in set(ref_drop.keys()):
            if table not in drop_table:
                del ref_drop[table]
            else:
                for item in set(ref_drop[table]["items"].keys()):
                    if item not in drop_table[table]["items"]:
                        del ref_drop[table]["items"][item]
        util.dict_merge(ref_drop, drop_table)
        drop_table = ref_drop
    except (FileNotFoundError, AttributeError, RuntimeError):
        pass
    actor_name = re.search(r"Pack\/(.+)\.sbactorpack", file).groups()[0]
    pio = _dict_to_drop(drop_table)
    util.inject_files_into_actor(actor_name, {file.split("//")[-1]: pio.to_binary()})


class DropMerger(mergers.Merger):
    NAME: str = "drops"

    def __init__(self):
        super().__init__(
            "drop merger", "Merges changes to drop tables", "drops.json", options={}
        )

    def generate_diff(self, mod_dir: Path, modded_files: List[Union[str, Path]]):
        drops = {f for f in modded_files if isinstance(f, str) and f.endswith(".bdrop")}
        if not drops:
            return {}
        print("Logging changes to drop tables...")
        pool = self._pool or Pool()
        diffs = {}
        for result in pool.map(partial(log_drop_file, mod_dir=mod_dir), drops):
            diffs.update(result)
        return diffs

    def log_diff(self, mod_dir: Path, diff_material):
        if isinstance(diff_material, list):
            diff_material = self.generate_diff(mod_dir, diff_material)
        if not diff_material:
            return
        (mod_dir / "logs" / self._log_name).write_text(
            json.dumps(diff_material, indent=2), encoding="utf-8"
        )

    def get_mod_diff(self, mod: util.BcmlMod):
        diff = {}
        if self.is_mod_logged(mod):
            util.dict_merge(
                diff, json.loads((mod.path / "logs" / self._log_name).read_text("utf-8"))
            )
        for opt in {d for d in (mod.path / "options").glob("*") if d.is_dir()}:
            if (opt / "logs" / self._log_name).exists():
                util.dict_merge(
                    diff, json.loads((opt / "logs" / self._log_name).read_text("utf-8"))
                )
        return diff

    def get_all_diffs(self):
        diffs = []
        for mod in util.get_installed_mods():
            diff = self.get_mod_diff(mod)
            if diff:
                diffs.append(diff)
        return diffs

    def consolidate_diffs(self, diffs):
        consolidated = {}
        for diff in diffs:
            util.dict_merge(consolidated, diff)
        return consolidated

    @util.timed
    def perform_merge(self):
        print("Loading drop table edits...")
        diffs = self.consolidate_diffs(self.get_all_diffs())
        if not diffs:
            print("No drop table merging necessary")
            return
        print("Merging drop table edits...")
        pool = self._pool or Pool()
        pool.starmap(merge_drop_file, diffs.items())
        if not self._pool:
            pool.close()
            pool.join()
        print("Finished merging drop tables")

    def get_mod_edit_info(self, mod: util.BcmlMod):
        return set(self.get_mod_diff(mod).keys())

    def get_checkbox_options(self):
        return []
