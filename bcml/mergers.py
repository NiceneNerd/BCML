""" Provides abstracted merging objects """
from abc import ABCMeta
from pathlib import Path
from typing import List, Union
from bcml import util

class Merger(metaclass=ABCMeta):
    """
    An abstract base class that represents a collection of merging functions for BCML. It can
    be subclassed to represent a single kind of merge, e.g. merging packs, game data, maps, etc.
    """
    NAME: str
    _friendly_name: str
    _description: str
    _log_name: str
    _options: dict

    def __init__(self, friendly_name: str, description: str, log_name: str,
                 options: dict = None):
        self._friendly_name = friendly_name
        self._description = description
        self._log_name = log_name
        if options:
            self._options = options
        else:
            self._options = {}

    def friendly_name(self) -> str:
        """ The name of this merger in the UI """
        return self._friendly_name

    def description(self) -> str:
        """ The description of this merger in the UI """
        return self._description

    def log_name(self) -> str:
        """ The name of the log file created by this merger """
        return self._log_name

    def set_options(self, options: dict):
        """ Sets custom options for this merger """
        self._options = options

    def generate_diff(self, mod_dir: Path, modded_files: List[Union[str, Path]]):
        """ Detects changes made to a modded file or files from the base game """
        raise NotImplementedError

    def log_diff(self, mod_dir: Path, diff_material: Union[dict, List[Path]]):
        """ Saves generated diffs to a log file """
        raise NotImplementedError

    def is_mod_logged(self, mod: util.BcmlMod) -> bool:
        """ Checks if a mod is logged for this merge """
        return (mod.path / 'logs' / self._log_name).exists()

    def get_mod_diff(self, mod: util.BcmlMod):
        """ Gets the logged diff for this merge in a given mod """
        raise NotImplementedError

    def get_all_diffs(self):
        """ Loads the installed diffs for this merge from all installed mods """
        raise NotImplementedError

    def consolidate_diffs(self, diffs: list):
        """ Combines and orders a collection of diffs into a single set of patches """
        raise NotImplementedError

    @staticmethod
    def can_partial_remerge() -> bool:
        """ Checks whether this merger can perform a partial remerge """
        return False

    @staticmethod
    def is_bootup_injector() -> bool:
        """ Checks whether this merger needs to inject a file into `Bootup.pack` """
        return False

    def get_bootup_injection(self) -> (str, bytes):
        """ Gets whatever file this merger needs to inject into `Bootup.pack` """
        raise NotImplementedError

    def get_mod_affected(self, mod: util.BcmlMod) -> []:
        """ Gets a list of files affected by a mod, if merger supports partial remerge """
        raise NotImplementedError

    def perform_merge(self):
        """ Applies one or more patches to the current mod installation """
        raise NotImplementedError

    def get_checkbox_options(self) -> List[tuple]:
        """ Gets the options for this merge as a tuple of internal name and UI description """
        return []


def get_mergers() -> List[Merger]:
    """ Retrieves all available types of mod mergers """

    from bcml import pack
    from bcml import texts
    from bcml import merge
    from bcml import data
    from bcml import mubin
    from bcml import events
    from bcml import rstable

    return [
        pack.PackMerger,
        merge.DeepMerger,
        texts.TextsMerger,
        data.ActorInfoMerger,
        mubin.DungeonStaticMerger,
        mubin.MapMerger,
        data.GameDataMerger,
        data.SaveDataMerger,
        events.EventInfoMerger,
        rstable.RstbMerger
    ]


def sort_mergers(mergers: List[Merger]) -> List[Merger]:
    return sorted(mergers, key=lambda merger: merger.NAME == 'rstb', reverse=False)
