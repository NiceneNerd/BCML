import json
from time import time
from pathlib import Path
import requests
import shlex
import sys

from bcml import util

GB_DATA = util.get_data_dir() / "gb.json"


class GameBananaDb:
    _data: dict
    _gameid: str

    def __init__(self) -> None:
        self._gameid = "5866" if util.get_settings("wiiu") else "6386"
        if not GB_DATA.exists():
            GB_DATA.write_bytes(
                util.decompress((util.get_exec_dir() / "data" / "gb.sjson").read_bytes())
            )
        self._data = json.loads(GB_DATA.read_text("utf-8"))
        self.update_db()

    def search(self, search: str) -> list:
        search = search.lower()
        terms = shlex.split(search)
        special = {}
        for t in terms.copy():
            if ":" in t:
                terms.remove(t)
                kv = t.split(":")
                special[kv[0]] = kv[1]
        return [
            m
            for m in self.mods
            if (
                any(
                    t in (m["description"] + m["name"] + m["text"].lower())
                    for t in terms
                )
                or not terms
            )
            and (
                all(k in m and v == m[k].lower() for k, v in special.items())
                or not special
            )
        ]

    def _send_request(self, url: str, params: dict) -> dict:
        params["format"] = "json_min"
        req = f"https://api.gamebanana.com/{url}?" + "&".join(
            f"{k}={v}" for k, v in params.items()
        )
        return requests.get(
            req,
            headers={"Authorization": "NiceneNerdRocks"},
        ).json()

    def update_db(self):
        EXCLUDES = {
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
            except:
                return
            if not res:
                break
            mods.update({m[1]: {"category": m[0]} for m in res if m[0] not in EXCLUDES})
            page += 1

        for mod, info in mods.copy().items():
            data = self._get_mod_data(mod, info["category"])
            if data:
                mods[mod].update(data)
            else:
                del mods[mod]
        self._data["mods"].update(mods)
        self._data["last_update"] = int(time())
        self.save_db()

    def _get_mod_data(self, mod_id: str, category: str) -> dict:
        FIELD_MAP = {
            "Preview().sStructuredDataFullsizeUrl()": "preview",
            "Files().aFiles()": "files",
            "Game().name": "game",
            "Owner().name": "owner",
            "udate": "updated",
        }
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
        except Exception as err:
            sys.__stdout__.write(str(err))
            return {}
        res["itemid"] = mod_id
        if res["Withhold().bIsWithheld()"] or res["Trash().bIsTrashed()"]:
            return {}

        def find_meta(data: dict, name: str) -> bool:
            for v in data.values():
                if isinstance(v, str) and v == name:
                    return True
                if isinstance(v, list) and name in v:
                    return True
                if isinstance(v, dict) and find_meta(v, name):
                    return True
            return False

        files = json.dumps(res["Files().aFiles()"])
        if not (
            "info.json" in files
            or ("rules.txt" in files and ("content" in files or "aoc" in files))
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
            if ("WiiU" in m["game"] if self._gameid == "5866" else "Switch" in m["game"])
        ]

    def update_mod(self, mod_id: str):
        pass
