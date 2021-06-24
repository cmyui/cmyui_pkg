# -*- coding: utf-8 -*-

# a thin wrapper around oppai-ng's c89 static library

import ctypes
import functools
from types import TracebackType
from typing import Type
from typing import TYPE_CHECKING
from typing import Optional

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ('OppaiWrapper',)

class OppaiWrapper:
    """Lightweight wrapper around oppai-ng's C library."""
    __slots__  = ('static_lib', '_ez')

    def __init__(self, lib_path: str):
        self.static_lib = self.load_static_library(lib_path)
        self._ez = 0

    def __enter__(self) -> 'OppaiWrapper':
        self._ez = self.static_lib.ezpp_new()
        return self

    def __exit__(self, exc_type: Optional[Type[BaseException]],
                 exc_value: Optional[BaseException],
                 traceback: Optional[TracebackType]) -> bool:
        self.static_lib.ezpp_free(self._ez)
        self._ez = 0
        return False

    @staticmethod
    @functools.cache
    def load_static_library(lib_path: str) -> ctypes.CDLL:
        """Load the oppai-ng static library,
           and register c types to it's api."""
        static_lib = ctypes.cdll.LoadLibrary(lib_path)

        # main api
        ezpp_new = static_lib.ezpp_new
        ezpp_new.argtypes = ()
        ezpp_new.restype = ctypes.c_int

        ezpp_free = static_lib.ezpp_free
        ezpp_free.argtypes = ()
        ezpp_free.restype = ctypes.c_void_p

        ezpp = static_lib.ezpp
        ezpp.argtypes = (ctypes.c_int, ctypes.c_char_p)
        ezpp.restype = ctypes.c_int

        ezpp_data = static_lib.ezpp_data
        ezpp_data.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int)
        ezpp_data.restype = ctypes.c_int

        ezpp_dup = static_lib.ezpp_dup
        ezpp_dup.argtypes = (ctypes.c_int, ctypes.c_char_p)
        ezpp_dup.restype = ctypes.c_int

        ezpp_data_dup = static_lib.ezpp_data_dup
        ezpp_data_dup.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int)

        # getting internals
        ezpp_pp = static_lib.ezpp_pp
        ezpp_pp.argtypes = (ctypes.c_int,)
        ezpp_pp.restype = ctypes.c_float

        ezpp_stars = static_lib.ezpp_stars
        ezpp_stars.argtypes = (ctypes.c_int,)
        ezpp_stars.restype = ctypes.c_float

        ezpp_mode = static_lib.ezpp_mode
        ezpp_mode.argtypes = (ctypes.c_int,)
        ezpp_mode.restype = ctypes.c_int

        ezpp_combo = static_lib.ezpp_combo
        ezpp_combo.argtypes = (ctypes.c_int,)
        ezpp_combo.restype = ctypes.c_int

        ezpp_max_combo = static_lib.ezpp_max_combo
        ezpp_max_combo.argtypes = (ctypes.c_int,)
        ezpp_max_combo.restype = ctypes.c_int

        ezpp_mods = static_lib.ezpp_mods
        ezpp_mods.argtypes = (ctypes.c_int,)
        ezpp_mods.restype = ctypes.c_int

        ezpp_score_version = static_lib.ezpp_score_version
        ezpp_score_version.argtypes = (ctypes.c_int,)
        ezpp_score_version.restype = ctypes.c_int

        ezpp_aim_stars = static_lib.ezpp_aim_stars
        ezpp_aim_stars.argtypes = (ctypes.c_int,)
        ezpp_aim_stars.restype = ctypes.c_float

        ezpp_speed_stars = static_lib.ezpp_speed_stars
        ezpp_speed_stars.argtypes = (ctypes.c_int,)
        ezpp_speed_stars.restype = ctypes.c_float

        ezpp_aim_pp = static_lib.ezpp_aim_pp
        ezpp_aim_pp.argtypes = (ctypes.c_int,)
        ezpp_aim_pp.restype = ctypes.c_float

        ezpp_speed_pp = static_lib.ezpp_speed_pp
        ezpp_speed_pp.argtypes = (ctypes.c_int,)
        ezpp_speed_pp.restype = ctypes.c_float

        ezpp_acc_pp = static_lib.ezpp_acc_pp
        ezpp_acc_pp.argtypes = (ctypes.c_int,)
        ezpp_acc_pp.restype = ctypes.c_float

        ezpp_accuracy_percent = static_lib.ezpp_accuracy_percent
        ezpp_accuracy_percent.argtypes = (ctypes.c_int,)
        ezpp_accuracy_percent.restype = ctypes.c_float

        ezpp_n300 = static_lib.ezpp_n300
        ezpp_n300.argtypes = (ctypes.c_int,)
        ezpp_n300.restype = ctypes.c_int

        ezpp_n100 = static_lib.ezpp_n100
        ezpp_n100.argtypes = (ctypes.c_int,)
        ezpp_n100.restype = ctypes.c_int

        ezpp_n50 = static_lib.ezpp_n50
        ezpp_n50.argtypes = (ctypes.c_int,)
        ezpp_n50.restype = ctypes.c_int

        ezpp_nmiss = static_lib.ezpp_nmiss
        ezpp_nmiss.argtypes = (ctypes.c_int,)
        ezpp_nmiss.restype = ctypes.c_int

        ezpp_title = static_lib.ezpp_title
        ezpp_title.argtypes = (ctypes.c_int,)
        ezpp_title.restype = ctypes.c_char_p

        ezpp_title_unicode = static_lib.ezpp_title_unicode
        ezpp_title_unicode.argtypes = (ctypes.c_int,)
        ezpp_title_unicode.restype = ctypes.c_char_p

        ezpp_artist = static_lib.ezpp_artist
        ezpp_artist.argtypes = (ctypes.c_int,)
        ezpp_artist.restype = ctypes.c_char_p

        ezpp_artist_unicode = static_lib.ezpp_artist_unicode
        ezpp_artist_unicode.argtypes = (ctypes.c_int,)
        ezpp_artist_unicode.restype = ctypes.c_char_p

        ezpp_creator = static_lib.ezpp_creator
        ezpp_creator.argtypes = (ctypes.c_int,)
        ezpp_creator.restype = ctypes.c_char_p

        ezpp_version = static_lib.ezpp_version
        ezpp_version.argtypes = (ctypes.c_int,)
        ezpp_version.restype = ctypes.c_char_p

        ezpp_ncircles = static_lib.ezpp_ncircles
        ezpp_ncircles.argtypes = (ctypes.c_int,)
        ezpp_ncircles.restype = ctypes.c_int

        ezpp_nsliders = static_lib.ezpp_nsliders
        ezpp_nsliders.argtypes = (ctypes.c_int,)
        ezpp_nsliders.restype = ctypes.c_int

        ezpp_nspinners = static_lib.ezpp_nspinners
        ezpp_nspinners.argtypes = (ctypes.c_int,)
        ezpp_nspinners.restype = ctypes.c_int

        ezpp_nobjects = static_lib.ezpp_nobjects
        ezpp_nobjects.argtypes = (ctypes.c_int,)
        ezpp_nobjects.restype = ctypes.c_int

        ezpp_ar = static_lib.ezpp_ar
        ezpp_ar.argtypes = (ctypes.c_int,)
        ezpp_ar.restype = ctypes.c_float

        ezpp_cs = static_lib.ezpp_cs
        ezpp_cs.argtypes = (ctypes.c_int,)
        ezpp_cs.restype = ctypes.c_float

        ezpp_od = static_lib.ezpp_od
        ezpp_od.argtypes = (ctypes.c_int,)
        ezpp_od.restype = ctypes.c_float

        ezpp_hp = static_lib.ezpp_hp
        ezpp_hp.argtypes = (ctypes.c_int,)
        ezpp_hp.restype = ctypes.c_float

        ezpp_odms = static_lib.ezpp_odms
        ezpp_odms.argtypes = (ctypes.c_int,)
        ezpp_odms.restype = ctypes.c_float

        ezpp_autocalc = static_lib.ezpp_autocalc
        ezpp_autocalc.argtypes = (ctypes.c_int,)
        ezpp_autocalc.restype = ctypes.c_int

        ezpp_time_at = static_lib.ezpp_time_at
        ezpp_time_at.argtypes = (ctypes.c_int, ctypes.c_int)
        ezpp_time_at.restype = ctypes.c_int

        ezpp_strain_at = static_lib.ezpp_strain_at
        ezpp_strain_at.argtypes = (ctypes.c_int, ctypes.c_int, ctypes.c_int)
        ezpp_strain_at.restype = ctypes.c_float

        ezpp_strain_at = static_lib.ezpp_strain_at
        ezpp_strain_at.argtypes = (ctypes.c_int, ctypes.c_int, ctypes.c_int)
        ezpp_strain_at.restype = ctypes.c_float

        ezpp_ntiming_points = static_lib.ezpp_ntiming_points
        ezpp_ntiming_points.argtypes = (ctypes.c_int,)
        ezpp_ntiming_points.restype = ctypes.c_int

        ezpp_timing_time = static_lib.ezpp_timing_time
        ezpp_timing_time.argtypes = (ctypes.c_int, ctypes.c_int)
        ezpp_timing_time.restype = ctypes.c_float

        ezpp_timing_ms_per_beat = static_lib.ezpp_timing_ms_per_beat
        ezpp_timing_ms_per_beat.argtypes = (ctypes.c_int, ctypes.c_int)
        ezpp_timing_ms_per_beat.restype = ctypes.c_float

        ezpp_timing_change = static_lib.ezpp_timing_change
        ezpp_timing_change.argtypes = (ctypes.c_int, ctypes.c_int)
        ezpp_timing_change.restype = ctypes.c_int

        # setting internals
        ezpp_set_aim_stars = static_lib.ezpp_set_aim_stars
        ezpp_set_aim_stars.argtypes = (ctypes.c_int, ctypes.c_float)
        ezpp_set_aim_stars.restype = ctypes.c_void_p

        ezpp_set_speed_stars = static_lib.ezpp_set_speed_stars
        ezpp_set_speed_stars.argtypes = (ctypes.c_int, ctypes.c_float)
        ezpp_set_speed_stars.restype = ctypes.c_void_p

        ezpp_set_base_ar = static_lib.ezpp_set_base_ar
        ezpp_set_base_ar.argtypes = (ctypes.c_int, ctypes.c_float)
        ezpp_set_base_ar.restype = ctypes.c_void_p

        ezpp_set_base_od = static_lib.ezpp_set_base_od
        ezpp_set_base_od.argtypes = (ctypes.c_int, ctypes.c_float)
        ezpp_set_base_od.restype = ctypes.c_void_p

        ezpp_set_base_hp = static_lib.ezpp_set_base_hp
        ezpp_set_base_hp.argtypes = (ctypes.c_int, ctypes.c_float)
        ezpp_set_base_hp.restype = ctypes.c_void_p

        ezpp_set_mode = static_lib.ezpp_set_mode
        ezpp_set_mode.argtypes = (ctypes.c_int, ctypes.c_int)
        ezpp_set_mode.restype = ctypes.c_void_p

        ezpp_set_combo = static_lib.ezpp_set_combo
        ezpp_set_combo.argtypes = (ctypes.c_int, ctypes.c_int)
        ezpp_set_combo.restype = ctypes.c_void_p

        ezpp_set_score_version = static_lib.ezpp_set_score_version
        ezpp_set_score_version.argtypes = (ctypes.c_int, ctypes.c_int)
        ezpp_set_score_version.restype = ctypes.c_void_p

        ezpp_set_accuracy_percent = static_lib.ezpp_set_accuracy_percent
        ezpp_set_accuracy_percent.argtypes = (ctypes.c_int, ctypes.c_float)
        ezpp_set_accuracy_percent.restype = ctypes.c_void_p

        ezpp_set_autocalc = static_lib.ezpp_set_autocalc
        ezpp_set_autocalc.argtypes = (ctypes.c_int, ctypes.c_int)
        ezpp_set_autocalc.restype = ctypes.c_void_p

        ezpp_set_mods = static_lib.ezpp_set_mods
        ezpp_set_mods.argtypes = (ctypes.c_int, ctypes.c_int)
        ezpp_set_mods.restype = ctypes.c_void_p

        # (clobber_setter)
        ezpp_set_base_cs = static_lib.ezpp_set_base_cs
        ezpp_set_base_cs.argtypes = (ctypes.c_int, ctypes.c_float)
        ezpp_set_base_cs.restype = ctypes.c_void_p

        ezpp_set_mode_override = static_lib.ezpp_set_mode_override
        ezpp_set_mode_override.argtypes = (ctypes.c_int, ctypes.c_int)
        ezpp_set_mode_override.restype = ctypes.c_void_p

        # (acc_clobber_setter)
        ezpp_set_nmiss = static_lib.ezpp_set_nmiss
        ezpp_set_nmiss.argtypes = (ctypes.c_int, ctypes.c_int)
        ezpp_set_nmiss.restype = ctypes.c_void_p

        ezpp_set_end = static_lib.ezpp_set_end
        ezpp_set_end.argtypes = (ctypes.c_int, ctypes.c_int)
        ezpp_set_end.restype = ctypes.c_void_p

        ezpp_set_end_time = static_lib.ezpp_set_end_time
        ezpp_set_end_time.argtypes = (ctypes.c_int, ctypes.c_float)
        ezpp_set_end_time.restype = ctypes.c_void_p

        ezpp_set_accuracy = static_lib.ezpp_set_accuracy
        ezpp_set_accuracy.argtypes = (ctypes.c_int, ctypes.c_int, ctypes.c_int)
        ezpp_set_accuracy.restype = ctypes.c_void_p

        return static_lib

    # get stuff

    def get_pp(self) -> float:
        return self.static_lib.ezpp_pp(self._ez)

    def get_sr(self) -> float:
        return self.static_lib.ezpp_stars(self._ez)

    # set stuff

    def set_mode(self, mode: int) -> None:
        self.static_lib.ezpp_set_mode(self._ez, mode)

    # set_mode_override?

    def set_combo(self, combo: int) -> None:
        self.static_lib.ezpp_set_combo(self._ez, combo)

    def set_accuracy_percent(self, acc: float) -> None:
        self.static_lib.ezpp_set_accuracy_percent(self._ez, acc)

    def set_mods(self, mods: int) -> None:
        self.static_lib.ezpp_set_mods(self._ez, mods)

    def set_nmiss(self, nmiss: int) -> None:
        self.static_lib.ezpp_set_nmiss(self._ez, nmiss)

    # misc

    def calculate(self, osu_file_path: 'Path') -> None: # .osu file path
        # XXX: bytes(Path) implementation is
        #      rather cursed and does the same
        osu_file_path_bytestr = str(osu_file_path).encode()
        self.static_lib.ezpp(self._ez, osu_file_path_bytestr)

    def calculate_data(self, osu_file_contents: bytes) -> None: # .osu file data
        self.static_lib.ezpp_data(self._ez, osu_file_contents, len(osu_file_contents))
