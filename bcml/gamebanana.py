import json
import shlex
import sys
from time import time
from typing import Tuple

import requests

from bcml import util

GB_DATA = util.get_data_dir() / "gb.json"
CAT_EXCLUDES = {
    "Request",
    "Question",
    "Tutorial",
    "Blog",
    "Contest",
    "News",
    "Poll",
    "Project",
    "Thread",
    "Wip",
    "Tool",
    "Script",
    "Concept",
}
FIELD_MAP = {
    "Preview().sStructuredDataFullsizeUrl()": "preview",
    "Files().aFiles()": "files",
    "Game().name": "game",
    "Owner().name": "owner",
    "udate": "updated",
}


class GameBananaDb:
    _data: dict
    _gameid: str

    def __init__(self) -> None:
        self._gameid = "5866" if util.get_settings("wiiu") else "6386"
        if not GB_DATA.exists():
            GB_DATA.write_bytes(
                util.decompress(
                    (util.get_exec_dir() / "data" / "gb.sjson").read_bytes()
                )
            )
        self._data = json.loads(GB_DATA.read_text("utf-8"))

    def search(self, search: str) -> Tuple[list, list]:
        search = search.lower().replace("'", "\\'")
        terms = [t for t in shlex.split(search) if len(t) > 2 and t != "the"]
        special = {}
        for term in terms.copy():
            if ":" in term:
                terms.remove(term)
                key_val = term.split(":")
                special[key_val[0]] = key_val[1]
        title_matches = [
            m
            for m in self.mods
            if (
                any(t in (m["description"] + m["name"]).lower() for t in terms)
                or not terms
            )
            and (
                all(k in m and v == m[k].lower() for k, v in special.items())
                or not special
            )
        ]
        desc_matches = [
            m
            for m in self.mods
            if (any(t in m["text"].lower() for t in terms) or not terms)
            and (
                all(k in m and v == m[k].lower() for k, v in special.items())
                or not special
            )
            and m not in title_matches
        ]
        return title_matches, desc_matches

    def _send_request(self, url: str, params: dict) -> dict:
        params["format"] = "json_min"
        req = f"https://api.gamebanana.com/{url}?" + "&".join(
            f"{k}={v}" for k, v in params.items()
        )
        res = requests.get(req)
        return res.json()

    def reset_update_time(self, wiiu: bool):
        self._data["last_update"] = sorted(
            {
                m["updated"]
                for m in self._data["mods"].values()
                if ("WiiU" in m["game"] if wiiu else "Switch" in m["game"])
            },
            reverse=True,
        )[0]
        self.save_db()

    def update_db(self):
        page = 1
        max_age = (
            157680000
            if self._data["last_update"] == 0
            else time() - self._data["last_update"]
        )
        mods = {}
        while True:
            try:
                res = self._send_request(
                    "Core/List/New",
                    {
                        "gameid": self._gameid,
                        "page": page,
                        "max_age": int(max_age),
                        "include_updated": 1,
                    },
                )
            except:  # pylint: disable=bare-except
                return
            if not res:
                break
            mods.update(
                {m[1]: {"category": m[0]} for m in res if m[0] not in CAT_EXCLUDES}
            )
            page += 1

        error_count = 0
        for mod, info in mods.copy().items():
            try:
                data = self._get_mod_data(mod, info["category"])
                assert data
                mods[mod].update(data)
            except:
                error_count += 1
                del mods[mod]
        self._data["mods"].update(mods)
        self._data["last_update"] = int(time())
        self.save_db()
        if error_count > 0:
            raise Exception(
                f"The metadata for {error_count} mods could not be updated. "
                "This is probably a problem with your internet connection or, much "
                "more likely, with GameBanana's servers."
            )

    def _get_mod_data(self, mod_id: str, category: str) -> dict:
        data = {}
        try:
            res = self._send_request(
                "Core/Item/Data",
                {
                    "itemtype": category,
                    "itemid": mod_id,
                    "return_keys": 1,
                    "fields": "name,authors,Game().name,creator,Trash().bIsTrashed(),likes,"
                    "date,description,downloads,udate,Withhold().bIsWithheld(),Owner().name"
                    ",Preview().sStructuredDataFullsizeUrl(),Files().aFiles(),text"
                    f"{',screenshots' if category != 'Sound' else ''}",
                },
            )
            if "error" in res:
                raise RuntimeError(
                    f"Error getting info for {category} mod #{mod_id}: {res['error']}"
                )
        except (requests.exceptions.BaseHTTPError, RuntimeError) as err:
            sys.__stdout__.write(str(err))
            return {}
        res["itemid"] = mod_id
        if res["Withhold().bIsWithheld()"] or res["Trash().bIsTrashed()"]:
            return {}

        files = json.dumps(res["Files().aFiles()"])
        if not (
            "info.json" in files
            or (
                "rules.txt" in files
                and ("content" in files or "aoc" in files or "logs" in files)
            )
        ):
            return {}

        for key, val in res.items():
            if key not in {"Withhold().bIsWithheld()", "Trash().bIsTrashed()"}:
                if key in {"authors", "screenshots"}:
                    val = json.loads(val)
                if key == "Files().aFiles()":
                    val = list(val.values())
                data[FIELD_MAP.get(key, key)] = val
        return data

    def save_db(self):
        GB_DATA.write_text(json.dumps(self._data))

    @property
    def mods(self):
        return [
            m
            for m in self._data["mods"].values()
            if (
                (
                    "WiiU" in m["game"]
                    if self._gameid == "5866"
                    else "Switch" in m["game"]
                )
                and (
                    util.get_settings("nsfw")
                    or all(
                        nsfw not in (m["name"] + m["description"] + m["text"]).lower()
                        for nsfw in {"nsfw", "thicc", "boob", "cosplay"}
                    )
                )
            )
        ]

    def get_mod_by_id(self, mod_id: str) -> dict:
        return self._data["mods"][mod_id]

    def update_mod(self, mod_id: str):
        data = self._get_mod_data(mod_id, self._data["mods"][mod_id]["category"])
        if data:
            self._data["mods"][mod_id].update(data)
            self.save_db()
