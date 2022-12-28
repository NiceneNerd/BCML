"""Provides functions for diffing and merging BotW game text files"""
# Copyright 2020 Nicene Nerd <macadamiadaze@gmail.com>
# Licensed under GPLv3+
import json
import multiprocessing
import subprocess
from functools import partial, lru_cache
from pathlib import Path
from platform import system
from tempfile import TemporaryDirectory, NamedTemporaryFile
from typing import List, Union, Set, ByteString

import oead
import xxhash

from bcml import mergers, util
from bcml import bcml as rsext
from bcml.util import get_7z_path

LANGUAGES = [
    "USen",
    "EUen",
    "USfr",
    "USes",
    "EUde",
    "EUes",
    "EUfr",
    "EUit",
    "EUnl",
    "EUru",
    "CNzh",
    "JPja",
    "KRko",
    "TWzh",
]


def swap_region(mod_pack: Path, user_lang: str) -> Path:
    mod_sarc = oead.Sarc(mod_pack.read_bytes())
    mod_msg_data = mod_sarc.get_file(0).data
    new_pack = oead.SarcWriter(
        endian=oead.Endianness.Big
        if util.get_settings("wiiu")
        else oead.Endianness.Little
    )
    new_pack.files[f"Message/Msg_{user_lang}.product.ssarc"] = oead.Bytes(mod_msg_data)
    new_pack_path = mod_pack.with_name(f"Bootup_{user_lang}.temppack")
    new_pack_path.write_bytes(new_pack.write()[1])
    return new_pack_path


def map_languages(dest_langs: Set[str], src_langs: Set[str]) -> dict:
    """
    Function to map languages from one set to another

    Parameter: dest_langs: Set[str] - The languages to be mapped to
    - For diffing: the languages our mod has packs for, to diff with
    - For merging: the languages the user has, that we want to merge into

    Parameter: src_langs: Set[str] - The languages that will serve as the source
    - For diffing: the languages our dumps have packs for, to diff against
    - For merging: the languages our mod has logs for, to merge with

    Returns: Dict[str, str] - A dict where the keys are from dest_lang,
        and the values are the languages most closely mapped to them
    """
    lang_map: dict = {}
    for dest_lang in dest_langs:
        if dest_lang in src_langs:
            lang_map[dest_lang] = dest_lang
        else:
            for src_lang in [l for l in src_langs if l[2:4] == dest_lang[2:4]]:
                lang_map[dest_lang] = src_lang
                break
            if dest_lang in lang_map:
                continue
            for src_lang in [l for l in src_langs if l[2:4] == "en"]:
                lang_map[dest_lang] = src_lang
                break
            if dest_lang in lang_map:
                continue
            lang_map[dest_lang] = next(iter(src_langs))
    return lang_map


class TextsMerger(mergers.Merger):
    # pylint: disable=abstract-method
    """A merger for game texts"""
    NAME: str = "texts"

    def __init__(self, all_langs: bool = False):
        super().__init__(
            "game texts",
            "Merges changes to game texts",
            "texts.json",
            options={"all_langs": all_langs},
        )

    def generate_diff(self, mod_dir: Path, modded_files: List[Union[str, Path]]):
        print("Checking for modified languages...")
        mod_langs = {
            util.get_file_language(file)
            for file in modded_files
            if (
                isinstance(file, Path)
                and "Bootup_" in file.name
                and "Graphic" not in file.name
            )
        }
        if not mod_langs:
            return None
        util.vprint(f'Languages: {",".join(mod_langs)}')

        # find a user lang for each mod lang
        language_map = map_languages(mod_langs, util.get_user_languages())
        util.vprint("Language map:")
        util.vprint(language_map)

        language_diffs = {}
        for mod_lang, user_lang in language_map.items():
            print(f"Logging text changes for {user_lang}...")
            mod_pack = (
                mod_dir / util.get_content_path() / "Pack" / f"Bootup_{mod_lang}.pack"
            )
            if not user_lang == mod_lang:
                mod_pack = swap_region(mod_pack, user_lang)
            ref_pack = util.get_game_file(f"Pack/Bootup_{user_lang}.pack")
            language_diffs[user_lang] = rsext.mergers.texts.diff_language(
                str(mod_pack), str(ref_pack), user_lang[2:4] != mod_lang[2:4]
            )
            if not user_lang == mod_lang:
                mod_pack.unlink()

        return language_diffs

    def log_diff(self, mod_dir: Path, diff_material):
        if isinstance(diff_material, List):
            diff_material = self.generate_diff(mod_dir, diff_material)
        if diff_material:
            (mod_dir / "logs" / self._log_name).write_text(
                json.dumps(diff_material, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def get_mod_diff(self, mod: util.BcmlMod):
        diff = {}
        if self.is_mod_logged(mod):
            util.dict_merge(
                diff,
                json.loads((mod.path / "logs" / self._log_name).read_text("utf-8")),
            )
        for opt in {d for d in (mod.path / "options").glob("*") if d.is_dir()}:
            if (opt / "logs" / self._log_name).exists():
                util.dict_merge(
                    diff,
                    json.loads((opt / "logs" / self._log_name).read_text("utf-8")),
                    overwrite_lists=True,
                )
        return diff

    def get_mod_edit_info(self, mod: util.BcmlMod) -> set:
        diffs = set()
        if self.is_mod_logged(mod):
            for files in self.get_mod_diff(mod).values():
                diffs |= set(files.keys())
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
        main_diff = diffs[0]
        for diff in diffs[1:]:
            for lang, content in diff.items():
                if lang not in main_diff:
                    main_diff[lang] = content
                else:
                    for file, entries in content.items():
                        if file not in main_diff[lang]:
                            main_diff[lang][file] = entries
                        else:
                            for entry, msg in entries.items():
                                main_diff[lang][file][entry] = msg
        return main_diff

    @util.timed
    def perform_merge(self):
        # pylint: disable=unsupported-assignment-operation
        user_langs = (
            {util.get_settings("lang")}
            if not self._options["all_langs"]
            else util.get_user_languages()
        )
        print("Loading text mods...")
        diffs = self.consolidate_diffs(self.get_all_diffs())
        if not diffs:
            print("No text merge necessary")
            for bootup in util.get_master_modpack_dir().rglob("**/Bootup_????.pack"):
                bootup.unlink()
            return

        # find a mod lang for each user lang
        lang_map = map_languages(user_langs, set(diffs.keys()))
        for user_lang, mod_lang in lang_map.items():
            print(f"Merging modded texts for {mod_lang} into {user_lang}...")
            rsext.mergers.texts.merge_language(
                json.dumps(diffs[mod_lang]),
                str(util.get_game_file(f"Pack/Bootup_{user_lang}.pack")),
                str(
                    util.get_master_modpack_dir()
                    / util.get_content_path()
                    / "Pack"
                    / f"Bootup_{user_lang}.pack"
                ),
                util.get_settings("wiiu"),
            )
            print(f"{user_lang} texts merged successfully")

    def get_checkbox_options(self) -> List[tuple]:
        return [
            ("all_langs", "Merge texts for all game languages"),
        ]
