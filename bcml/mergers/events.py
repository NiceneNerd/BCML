"""Provides features for diffing and merging EventInfo.product.sbyml """
# Copyright 2020 Nicene Nerd <macadamiadaze@gmail.com>
# Licensed under GPLv3+
from pathlib import Path
from typing import List, Union

import oead
import rstb
from bcml import util, mergers
from bcml.util import BcmlMod
from bcml.mergers import rstable


def get_stock_eventinfo() -> oead.byml.Hash:
    if not hasattr(get_stock_eventinfo, "event_info"):
        get_stock_eventinfo.event_info = oead.byml.to_text(
            oead.byml.from_binary(
                util.get_nested_file_bytes(
                    str(util.get_game_file("Pack/Bootup.pack"))
                    + "//Event/EventInfo.product.sbyml",
                    unyaz=True,
                )
            )
        )
    return oead.byml.from_text(get_stock_eventinfo.event_info)


def get_modded_events(event_info: oead.byml.Hash) -> oead.byml.Hash:
    stock_events = get_stock_eventinfo()
    modded_events = oead.byml.Hash(
        {
            event: data
            for event, data in event_info.items()
            if (event not in stock_events or stock_events[event] != data)
        }
    )
    del stock_events
    return modded_events


class EventInfoMerger(mergers.Merger):
    NAME: str = "eventinfo"

    def __init__(self):
        super().__init__(
            "event info",
            "Merges changes to EventInfo.product.byml",
            "eventinfo.yml",
            options={},
        )

    def generate_diff(self, mod_dir: Path, modded_files: List[Union[Path, str]]):
        if (
            f"{util.get_content_path()}/Pack/Bootup.pack//Event/EventInfo.product.sbyml"
            in modded_files
        ):
            print("Logging modded events...")
            bootup_sarc = oead.Sarc(
                (mod_dir / util.get_content_path() / "Pack" / "Bootup.pack").read_bytes()
            )
            event_info = oead.byml.from_binary(
                util.decompress(
                    bootup_sarc.get_file("Event/EventInfo.product.sbyml").data
                )
            )
            diff = get_modded_events(event_info)
            del bootup_sarc
            del event_info
            return diff
        else:
            return {}

    def log_diff(self, mod_dir: Path, diff_material):
        if isinstance(diff_material, List):
            diff_material = self.generate_diff(mod_dir, diff_material)
        if diff_material:
            (mod_dir / "logs" / self._log_name).write_text(
                oead.byml.to_text(diff_material), encoding="utf-8"
            )
            del diff_material

    def get_mod_diff(self, mod: BcmlMod):
        diffs = {}
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
        for mod in util.get_installed_mods():
            diff = self.get_mod_diff(mod)
            if diff:
                diffs.append(diff)
        return diffs

    def consolidate_diffs(self, diffs: list):
        if not diffs:
            return {}
        all_diffs = oead.byml.Hash()
        for diff in diffs:
            util.dict_merge(all_diffs, diff, shallow=True)
        return all_diffs

    @util.timed
    def perform_merge(self):
        merged_events = util.get_master_modpack_dir() / "logs" / "eventinfo.byml"
        event_merge_log = util.get_master_modpack_dir() / "logs" / "eventinfo.log"

        print("Loading event info mods...")
        modded_events = self.consolidate_diffs(self.get_all_diffs())
        event_mod_hash = hash(str(modded_events))
        if not modded_events:
            print("No event info merging necessary")
            if merged_events.exists():
                merged_events.unlink()
                event_merge_log.unlink()
                try:
                    stock_eventinfo = util.get_nested_file_bytes(
                        (
                            str(util.get_game_file("Pack/Bootup.pack"))
                            + "//Event/EventInfo.product.sbyml"
                        ),
                        unyaz=False,
                    )
                    util.inject_file_into_sarc(
                        "Event/EventInfo.product.sbyml",
                        stock_eventinfo,
                        "Pack/Bootup.pack",
                    )
                except FileNotFoundError:
                    pass
            return
        if event_merge_log.exists() and event_merge_log.read_text() == event_mod_hash:
            print("No event info merging necessary")
            return

        new_events = get_stock_eventinfo()
        for event, data in modded_events.items():
            new_events[event] = data
        del modded_events

        print("Writing new event info...")
        event_bytes = oead.byml.to_binary(
            new_events, big_endian=util.get_settings("wiiu")
        )
        del new_events
        util.inject_file_into_sarc(
            "Event/EventInfo.product.sbyml",
            util.compress(event_bytes),
            "Pack/Bootup.pack",
            create_sarc=True,
        )
        print("Saving event info merge log...")
        event_merge_log.parent.mkdir(parents=True, exist_ok=True)
        event_merge_log.write_text(str(event_mod_hash))
        merged_events.write_bytes(event_bytes)

        print("Updating RSTB...")
        rstb_size = rstb.SizeCalculator().calculate_file_size_with_ext(
            bytes(event_bytes), True, ".byml"
        )
        del event_bytes
        rstable.set_size("Event/EventInfo.product.byml", rstb_size)

    def get_checkbox_options(self):
        return []

    @staticmethod
    def is_bootup_injector():
        return True

    def get_bootup_injection(self):
        tmp_sarc = util.get_master_modpack_dir() / "logs" / "eventinfo.byml"
        if tmp_sarc.exists():
            return (
                "Event/EventInfo.product.sbyml",
                util.compress(tmp_sarc.read_bytes()),
            )
        else:
            return

    def get_mod_edit_info(self, mod: util.BcmlMod) -> set:
        return self.get_mod_diff(mod).keys()
