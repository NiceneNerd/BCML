from pathlib import Path
from typing import List, Union

import oead
import rstb
from bcml import util, mergers
from bcml.mergers import rstable


def get_stock_effects() -> oead.byml.Hash:
    bootup_sarc = oead.Sarc(util.get_game_file("Pack/Bootup.pack").read_bytes())
    return oead.byml.from_binary(
        util.decompress(bootup_sarc.get_file("Ecosystem/StatusEffectList.sbyml").data)
    )[0]


class StatusEffectMerger(mergers.Merger):
    NAME: str = "effects"

    def __init__(self):
        super().__init__(
            "status effect",
            "Merges changes to StatusEffectList.byml",
            "effects.yml",
            options={},
        )

    def generate_diff(self, mod_dir: Path, modded_files: List[Union[str, Path]]):
        needle = f"{util.get_content_path()}/Pack/Bootup.pack//Ecosystem/StatusEffectList.sbyml"
        if needle not in modded_files:
            return {}
        print("Logging changes to effect status levels...")
        stock_effects = get_stock_effects()
        bootup_sarc = oead.Sarc(
            (mod_dir / util.get_content_path() / "Pack" / "Bootup.pack").read_bytes()
        )
        mod_effects = oead.byml.from_binary(
            util.decompress(bootup_sarc.get_file("Ecosystem/StatusEffectList.sbyml").data)
        )[0]
        diff = oead.byml.Hash(
            {
                effect: params
                for effect, params in mod_effects.items()
                if stock_effects[effect] != params
            }
        )
        del stock_effects
        del mod_effects

    def log_diff(self, mod_dir: Path, diff_material):
        if isinstance(diff_material, list):
            diff_material = self.generate_diff(mod_dir, diff_material)
        if diff_material:
            (mod_dir / "logs" / self._log_name).write_text(
                oead.byml.to_text(diff_material), encoding="utf-8"
            )
            del diff_material

    def get_mod_diff(self, mod: util.BcmlMod):
        diff = oead.byml.Hash()
        if self.is_mod_logged(mod):
            diff = oead.byml.from_text(
                (mod.path / "logs" / self._log_name).read_text("utf-8")
            )
        for opt in {d for d in (mod.path / "options").glob("*") if d.is_dir()}:
            if (opt / "logs" / self._log_name).exists():
                util.dict_merge(
                    diff,
                    oead.byml.from_text(
                        (opt / "logs" / self._log_name).read_text("utf-8")
                    ),
                    overwrite_lists=True,
                )
        return diff

    def get_all_diffs(self):
        diffs = []
        for m in util.get_installed_mods():
            diff = self.get_mod_diff(m)
            if diff:
                diffs.append(diff)
        return diffs

    def consolidate_diffs(self, diffs):
        if not diffs:
            return {}
        all_diffs = oead.byml.Hash()
        for diff in diffs:
            util.dict_merge(all_diffs, diff, overwrite_lists=True)
            del diff
        return all_diffs

    @util.timed
    def perform_merge(self):
        merged_effects = util.get_master_modpack_dir() / "logs" / "effects.byml"
        print("Loading status effect mods...")
        diffs = self.consolidate_diffs(self.get_all_diffs())
        if not diffs:
            print("No status effect merging necessary...")
            if merged_effects.exists():
                merged_effects.unlink()
                try:
                    stock_effects = util.get_nested_file_bytes(
                        (
                            str(util.get_game_file("Pack/Bootup.pack"))
                            + "//Ecosystem/StatusEffectList.sbyml"
                        ),
                        unyaz=False,
                    )
                    util.inject_file_into_sarc(
                        "Ecosystem/StatusEffectList.sbyml",
                        stock_effects,
                        "Pack/Bootup.pack",
                    )
                    del stock_effects
                except FileNotFoundError:
                    pass
            return

        effects = get_stock_effects()
        util.dict_merge(effects, diffs, overwrite_lists=True)
        del diffs

        print("Writing new effects list...")
        effect_bytes = oead.byml.to_binary(
            oead.byml.Array([effects]), big_endian=util.get_settings("wiiu")
        )
        del effects
        util.inject_file_into_sarc(
            "Ecosystem/StatusEffectList.sbyml",
            util.compress(effect_bytes),
            "Pack/Bootup.pack",
            create_sarc=True,
        )
        print("Saving status effect merge log...")
        merged_effects.parent.mkdir(parents=True, exist_ok=True)
        merged_effects.write_bytes(effect_bytes)

        print("Updating RSTB...")
        rstb_size = rstb.SizeCalculator().calculate_file_size_with_ext(
            effect_bytes, True, ".byml"
        )
        del effect_bytes
        rstable.set_size("Ecosystem/StatusEffectList.byml", rstb_size)

    def get_checkbox_options(self):
        return []

    @staticmethod
    def is_bootup_injector():
        return True

    def get_bootup_injection(self):
        tmp_sarc = util.get_master_modpack_dir() / "logs" / "effects.byml"
        if tmp_sarc.exists():
            return (
                "Ecosystem/StatusEffectList.sbyml",
                util.compress(tmp_sarc.read_bytes()),
            )
        return

    def get_mod_edit_info(self, mod: util.BcmlMod) -> set:
        return self.get_mod_diff(mod).keys()
