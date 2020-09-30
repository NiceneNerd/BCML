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
from bcml.util import ZPATH

EXCLUDE_TEXTS = [
    "ErrorMessage",
    "StaffRoll",
    "LayoutMsg/MessageTipsRunTime_00",
    "LayoutMsg/OptionWindow_00",
    "LayoutMsg/SystemWindow_00",
]

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

MSYT_PATH = str(
    util.get_exec_dir()
    / "helpers"
    / "msyt{}".format(".exe" if system() == "Windows" else "")
)


@lru_cache(2)
def get_text_hashes(language: str = None) -> {}:
    hashes = json.loads(
        util.decompress(
            (util.get_exec_dir() / "data" / "hashes" / "msyts.sjson").read_bytes()
        ).decode("utf8")
    )
    if language:
        return hashes[language if not language.endswith("en") else "XXen"]
    else:
        return hashes


def get_user_languages() -> set:
    langs = set()
    for file in (util.get_update_dir() / "Pack").glob("Bootup_????.pack"):
        langs.add(util.get_file_language(file.name))
    return langs


def match_language(lang: str, log_dir: Path) -> str:
    logged_langs = set([util.get_file_language(l) for l in log_dir.glob("*texts*")])
    if lang in logged_langs:
        return lang
    elif lang[2:4] in [l[2:4] for l in logged_langs]:
        return [l for l in logged_langs if l[2:4] == lang[2:4]][0]
    else:
        return [l for l in LANGUAGES if l in logged_langs][0]


def msbt_to_msyt(folder: Path, pool: multiprocessing.Pool = None):
    """ Converts MSBTs in given temp dir to MSYTs """
    if system() == "Windows":
        subprocess.run(
            [MSYT_PATH, "export", "-d", str(folder)],
            creationflags=util.CREATE_NO_WINDOW,
            check=False,
        )
    else:
        subprocess.run([MSYT_PATH, "export", "-d", str(folder)], check=False)
    fix_msbts = [
        msbt
        for msbt in folder.rglob("**/*.msbt")
        if not msbt.with_suffix(".msyt").exists()
    ]
    if fix_msbts:
        print("Some MSBTs failed to convert. Trying again individually...")
        this_pool = pool or multiprocessing.Pool()
        this_pool.map(partial(_msyt_file), fix_msbts)
        fix_msbts = [
            msbt
            for msbt in folder.rglob("**/*.msbt")
            if not msbt.with_suffix(".msyt").exists()
        ]
        if not pool:
            this_pool.close()
            this_pool.join()
    if fix_msbts:
        print(f"{len(fix_msbts)} MSBT files failed to convert. They will not be merged.")
        util.vprint(fix_msbts)
    for msbt_file in folder.rglob("**/*.msbt"):
        Path(msbt_file).unlink()
    return fix_msbts


def _msyt_file(file, output: Path = None):
    m_args = [MSYT_PATH, "export", str(file)]
    if output:
        m_args += ["--output", str(output)]
    if system() == "Windows":
        result = subprocess.run(
            m_args,
            creationflags=util.CREATE_NO_WINDOW,
            capture_output=True,
            text=True,
            check=False,
        )
    else:
        result = subprocess.run(m_args, capture_output=True, text=True, check=False)
    if result.stderr:
        raise ValueError(
            f"The MSBT file <code>{file}</code> could not be read."
            "Please contact the mod developer for assistance."
        ) from RuntimeError(
            (
                result.stderr.replace("an error occurred - see below for details", "")
                .replace("\n", " ")
                .capitalize()
            )
        )


def read_msbt(file: Union[Path, ByteString]):
    tmp_file = Path(NamedTemporaryFile(suffix=".msyt").name)
    if not isinstance(file, Path):
        tmp_file.with_suffix(".msbt").write_bytes(file)
        file = tmp_file.with_suffix(".msbt")
    _msyt_file(file, tmp_file)
    tmp_text = tmp_file.read_text("utf-8")
    tmp_file.unlink()
    return json.loads(tmp_text, encoding="utf-8")


def extract_refs(language: str, tmp_dir: Path, files: set = None):
    x_args = [
        ZPATH,
        "x",
        str(util.get_exec_dir() / "data" / "text_refs.7z"),
        f'-o{str(tmp_dir / "refs")}',
    ]
    if files:
        x_args.extend(files)
    else:
        x_args.append(language)
    result: subprocess.CompletedProcess
    if system() == "Windows":
        result = subprocess.run(
            x_args,
            capture_output=True,
            creationflags=util.CREATE_NO_WINDOW,
            check=False,
            text=True,
        )
    else:
        result = subprocess.run(x_args, capture_output=True, text=True, check=False)
    if result.stderr:
        raise RuntimeError(result.stderr)


def diff_msyt(msyt: Path, hashes: dict, mod_out: Path, ref_dir: Path):
    diff = {}
    filename = msyt.relative_to(mod_out).as_posix()
    if any(ex in filename for ex in EXCLUDE_TEXTS):
        msyt.unlink()
        return {}
    data = msyt.read_bytes()
    xxh = xxhash.xxh64_intdigest(data)
    if filename in hashes and hashes[filename] == xxh:
        pass
    else:
        text = data.decode("utf8")
        if filename not in hashes:
            diff[filename] = json.loads(text, encoding="utf-8")["entries"]
        else:
            ref_text = (ref_dir / filename).read_text("utf-8")
            if "".join(text.split()) != "".join(ref_text.split()):
                ref_contents = json.loads(ref_text, encoding="utf-8")
                contents = json.loads(text, encoding="utf-8")
                diff[filename] = {
                    entry: value
                    for entry, value in contents["entries"].items()
                    if (
                        entry not in ref_contents["entries"]
                        or value != ref_contents["entries"][entry]
                    )
                }
            else:
                pass
            del ref_text
            del text
    msyt.unlink()
    del data
    return diff


def diff_language(bootup: Path, pool: multiprocessing.Pool = None) -> {}:
    diff = {}
    language = bootup.name[7:-5]
    bootup_sarc = oead.Sarc(bootup.read_bytes())
    msg_sarc = oead.Sarc(
        util.decompress(
            bootup_sarc.get_file(f"Message/Msg_{language}.product.ssarc").data
        )
    )

    with TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        mod_out = tmp_dir / "mod"
        print("Extracting mod texts...")
        for file in msg_sarc.get_files():
            out = mod_out / file.name
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(file.data)
        del msg_sarc

        print("Converting texts to MSYT...")
        msbt_to_msyt(mod_out, pool=pool)
        hashes = get_text_hashes(language)
        ref_lang = "XXen" if language.endswith("en") else language
        print("Extracting reference texts...")
        extract_refs(ref_lang, tmp_dir)
        ref_dir = tmp_dir / "refs" / ref_lang

        this_pool = pool or multiprocessing.Pool()
        print("Identifying modified text files...")
        results = this_pool.map(
            partial(diff_msyt, ref_dir=ref_dir, hashes=hashes, mod_out=mod_out),
            mod_out.rglob("**/*.msyt"),
        )
        if not pool:
            this_pool.close()
            this_pool.join()
        for result in results:
            diff.update(result)
    return diff


def merge_msyt(file_data: tuple, tmp_dir: Path):
    filename: str = file_data[0]
    changes: dict = file_data[1]
    out = tmp_dir / filename
    if out.exists():
        text_data = json.loads(out.read_text("utf-8"), encoding="utf-8")
        text_data["entries"].update(changes)
        out.write_text(json.dumps(text_data, ensure_ascii=False), encoding="utf-8")
    else:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(
                {
                    "group_count": len(changes),
                    "atr1_unknown": 0 if "EventFlowMsg" not in filename else 4,
                    "entries": changes,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )


class TextsMerger(mergers.Merger):
    # pylint: disable=abstract-method
    """ A merger for game texts """
    NAME: str = "texts"

    def __init__(self, all_langs: bool = True):
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
            print(f"Logging text changes for {language}...")
            language_diffs[language] = diff_language(
                mod_dir / util.get_content_path() / "Pack" / f"Bootup_{language}.pack",
                pool=self._pool,
            )

        return {
            save_lang: language_diffs[map_lang]
            for save_lang, map_lang in language_map.items()
        }

    def log_diff(self, mod_dir: Path, diff_material):
        if isinstance(diff_material, List):
            diff_material = self.generate_diff(mod_dir, diff_material)
        if diff_material:
            (mod_dir / "logs" / self._log_name).write_text(
                json.dumps(diff_material, ensure_ascii=False, indent=2), encoding="utf-8",
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
                    diff, json.loads((opt / "logs" / self._log_name).read_text("utf-8")),
                    overwrite_lists=True
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
            else get_user_languages()
        )
        for lang in langs:
            print("Loading text mods...")
            diffs = self.consolidate_diffs(self.get_all_diffs())
            if not diffs or lang not in diffs:
                print("No text merge necessary")
                for bootup in util.get_master_modpack_dir().rglob("**/Bootup_????.pack"):
                    bootup.unlink()
                return
            util.vprint(
                {
                    lang: {
                        file: list(entries.keys())
                        for file, entries in diffs[lang].items()
                    }
                }
            )

            print(f"Merging modded texts for {lang}...")
            saved_files = set()
            with TemporaryDirectory() as tmp:
                tmp_dir = Path(tmp)
                ref_lang = "XXen" if lang.endswith("en") else lang
                extract_refs(ref_lang, tmp_dir)
                tmp_dir = tmp_dir / "refs" / ref_lang
                this_pool = self._pool or multiprocessing.Pool()
                this_pool.map(partial(merge_msyt, tmp_dir=tmp_dir), diffs[lang].items())
                if not self._pool:
                    this_pool.close()
                    this_pool.join()

                m_args = [
                    MSYT_PATH,
                    "create",
                    "-d",
                    str(tmp_dir),
                    "-p",
                    "wiiu" if util.get_settings("wiiu") else "switch",
                    "-o",
                    str(tmp_dir),
                ]
                result: subprocess.CompletedProcess
                if system() == "Windows":
                    result = subprocess.run(
                        m_args,
                        capture_output=True,
                        creationflags=util.CREATE_NO_WINDOW,
                        check=False,
                        text=True,
                    )

                else:
                    result = subprocess.run(
                        m_args, capture_output=True, check=False, text=True,
                    )
                if result.stderr:
                    raise RuntimeError(
                        f"There was an error merging game texts. {result.stderr}"
                    )

                msg_sarc = oead.SarcWriter(
                    endian=oead.Endianness.Big
                    if util.get_settings("wiiu")
                    else oead.Endianness.Little
                )
                for file in tmp_dir.rglob("**/*.msbt"):
                    msg_sarc.files[
                        file.relative_to(tmp_dir).as_posix()
                    ] = file.read_bytes()
                    saved_files.add(file.relative_to(tmp_dir).as_posix())
            bootup_sarc = oead.SarcWriter(
                endian=oead.Endianness.Big
                if util.get_settings("wiiu")
                else oead.Endianness.Little
            )
            bootup_sarc.files[f"Message/Msg_{lang}.product.ssarc"] = util.compress(
                msg_sarc.write()[1]
            )

            bootup_path = (
                util.get_master_modpack_dir()
                / util.get_content_path()
                / "Pack"
                / f"Bootup_{lang}.pack"
            )
            bootup_path.parent.mkdir(parents=True, exist_ok=True)
            bootup_path.write_bytes(bootup_sarc.write()[1])
            del bootup_sarc
            del msg_sarc
            print(f"{lang} texts merged successfully")

    def get_checkbox_options(self) -> List[tuple]:
        return [
            ("all_langs", "Merge texts for all game languages"),
        ]
