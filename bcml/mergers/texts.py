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
from typing import List, Union, ByteString

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
        languages = {
            util.get_file_language(file)
            for file in modded_files
            if (
                isinstance(file, Path)
                and "Bootup_" in file.name
                and "Graphic" not in file.name
            )
        }
        if not languages:
            return None
        util.vprint(f'Languages: {",".join(languages)}')

        language_map = {}
        save_langs = (
            LANGUAGES
            if self._options.get("all_langs", False)
            else [util.get_settings("lang")]
        )
        for lang in save_langs:
            if lang in languages:
                language_map[lang] = lang
            elif lang[2:4] in [l[2:4] for l in languages]:
                language_map[lang] = [l for l in languages if l[2:4] == lang[2:4]][0]
            else:
                language_map[lang] = [l for l in LANGUAGES if l in languages][0]
        util.vprint(f"Language map:")
        util.vprint(language_map)

        language_diffs = {}
        for language in set(language_map.values()):
            try:
                print(f"Logging text changes for {language}...")
                language_diffs[language] = rsext.mergers.texts.diff_language(
                    str(
                        mod_dir
                        / util.get_content_path()
                        / "Pack"
                        / f"Bootup_{language}.pack"
                    ),
                    str(util.get_game_file(f"Pack/Bootup_{language}.pack")),
                )
            except FileNotFoundError:
                util.vprint(f"Skipping language {language}, not in dump")

        return {
            save_lang: language_diffs[map_lang]
            for save_lang, map_lang in language_map.items()
        }

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
        langs = (
            {util.get_settings("lang")}
            if not self._options["all_langs"]
            else util.get_user_languages()
        )
        for lang in langs:
            print("Loading text mods...")
            diffs = self.consolidate_diffs(self.get_all_diffs())
            if not diffs or lang not in diffs:
                print("No text merge necessary")
                for bootup in util.get_master_modpack_dir().rglob(
                    "**/Bootup_????.pack"
                ):
                    bootup.unlink()
                return

            print(f"Merging modded texts for {lang}...")
            rsext.mergers.texts.merge_language(
                json.dumps(diffs[lang]),
                str(util.get_game_file(f"Pack/Bootup_{lang}.pack")),
                str(
                    util.get_master_modpack_dir()
                    / util.get_content_path()
                    / "Pack"
                    / f"Bootup_{lang}.pack"
                ),
                util.get_settings("wiiu"),
            )
            print(f"{lang} texts merged successfully")

    def get_checkbox_options(self) -> List[tuple]:
        return [
            ("all_langs", "Merge texts for all game languages"),
        ]
