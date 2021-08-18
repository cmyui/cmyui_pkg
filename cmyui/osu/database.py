""" Tools for working with osu!'s .db file formats """

# NOTE: overall this is quite a rough draft, and was written in ~2 hours
#       the naming scheme probably needs some improvement lol

import os
import struct
from datetime import datetime
from typing import Optional
from typing import Union

from cmyui.osu.mods import Mods

__all__ = ('BeatmapsDatabase', 'CollectionsDatabase', 'ScoresDatabase')

StrOrBytesPath = Union[str, bytes, os.PathLike[str], os.PathLike[bytes]]

# TODO: this can be moved and used for other
# stuff like replay parsing & even bancho stuff
class osuReader:
    __slots__ = ('body_view',)
    def __init__(self, body_view: memoryview) -> None:
        self.body_view = body_view # readonly

    def read_i8(self) -> int:
        val = self.body_view[0]
        self.body_view = self.body_view[1:]
        return val - 256 if val > 127 else val

    def read_u8(self) -> int:
        val = self.body_view[0]
        self.body_view = self.body_view[1:]
        return val

    def read_i16(self) -> int:
        val = int.from_bytes(self.body_view[:2], 'little', signed=True)
        self.body_view = self.body_view[2:]
        return val

    def read_u16(self) -> int:
        val = int.from_bytes(self.body_view[:2], 'little', signed=False)
        self.body_view = self.body_view[2:]
        return val

    def read_i32(self) -> int:
        val = int.from_bytes(self.body_view[:4], 'little', signed=True)
        self.body_view = self.body_view[4:]
        return val

    def read_u32(self) -> int:
        val = int.from_bytes(self.body_view[:4], 'little', signed=False)
        self.body_view = self.body_view[4:]
        return val

    def read_i64(self) -> int:
        val = int.from_bytes(self.body_view[:8], 'little', signed=True)
        self.body_view = self.body_view[8:]
        return val

    def read_u64(self) -> int:
        val = int.from_bytes(self.body_view[:8], 'little', signed=False)
        self.body_view = self.body_view[8:]
        return val

    # floating-point types

    def read_f16(self) -> float:
        val, = struct.unpack_from('<e', self.body_view[:2])
        self.body_view = self.body_view[2:]
        return val

    def read_f32(self) -> float:
        val, = struct.unpack_from('<f', self.body_view[:4])
        self.body_view = self.body_view[4:]
        return val

    def read_f64(self) -> float:
        val, = struct.unpack_from('<d', self.body_view[:8])
        self.body_view = self.body_view[8:]
        return val

    # complex types

    # XXX: some osu! packets use i16 for
    # array length, while others use i32
    def read_i32_list_i16l(self) -> tuple[int]:
        length = int.from_bytes(self.body_view[:2], 'little')
        self.body_view = self.body_view[2:]

        val = struct.unpack(f'<{"I" * length}', self.body_view[:length * 4])
        self.body_view = self.body_view[length * 4:]
        return val

    def read_i32_list_i32l(self) -> tuple[int]:
        length = int.from_bytes(self.body_view[:4], 'little')
        self.body_view = self.body_view[4:]

        val = struct.unpack(f'<{"I" * length}', self.body_view[:length * 4])
        self.body_view = self.body_view[length * 4:]
        return val

    def read_string(self) -> str:
        exists = self.body_view[0] == 0x0b
        self.body_view = self.body_view[1:]

        if not exists:
            # no string sent.
            return ''

        # non-empty string, decode str length (uleb128)
        length = shift = 0

        while True:
            b = self.body_view[0]
            self.body_view = self.body_view[1:]

            length |= (b & 127) << shift
            if (b & 128) == 0:
                break

            shift += 7

        val = self.body_view[:length].tobytes().decode() # copy
        self.body_view = self.body_view[length:]
        return val

class osuDatabase(osuReader):
    def _read(self) -> None: ... # TODO: can probably make the impl generic

    @classmethod
    def from_data(cls, data: bytes) -> 'osuDatabase':
        self = cls(memoryview(data).toreadonly())
        self._read()
        return self

    @classmethod
    def from_file(cls, path: StrOrBytesPath) -> Optional['osuDatabase']:
        if os.path.exists(path):
            with open(path, 'rb') as f:
                return cls.from_data(f.read())

# osu!.db

class BeatmapsDatabaseBeatmap:
    __slots__ = (
        'artist', 'artist_unicode', 'title', 'title_unicode', 'creator',
        'version', 'audio_file', 'map_md5', 'osu_file', 'ranked_status',
        'num_circles', 'num_sliders', 'num_spinners', 'last_edit_time',
        'diff_ar', 'diff_cs', 'diff_hp', 'diff_od', 'slider_velocity',
        'star_ratings', 'drain_time', 'total_time', 'audio_preview',
        'timing_points', 'map_id', 'set_id', 'thread_id',
        'osu_grade', 'taiko_grade', 'catch_grade', 'mania_grade',
        'local_offset', 'stack_leniency', 'game_mode', 'source', 'tags',
        'online_offset', 'title_font', 'is_unplayed', 'last_played',
        'is_osz2', 'folder_name', 'last_checked_against_osu_repo',
        'ignore_beatmap_sound', 'ignore_beatmap_skin',
        'disable_storyboard', 'disable_video', 'visual_override',
        'last_modification', 'mania_scroll_speed',
    )
    def __init__(
        self, artist: str, artist_unicode: str, title: str, title_unicode: str,
        creator: str, version: str, audio_file: str, map_md5: str, osu_file: str,
        ranked_status: int, num_circles: int, num_sliders: int, num_spinners: int,
        last_edit_time: int, diff_ar: float, diff_cs: float, diff_hp: float, diff_od: float,
        slider_velocity: float, star_ratings: list[Optional[dict[Mods, float]]],
        drain_time: int, total_time: int, audio_preview: int,
        timing_points: list['BeatmapsDatabaseTimingPoint'],
        map_id: int, set_id: int, thread_id: int,
        osu_grade: int, taiko_grade: int, catch_grade: int, mania_grade: int, # TODO: class
        local_offset: int, stack_leniency: float, game_mode: int,
        source: str, tags: list[str], online_offset: int, title_font: str,
        is_unplayed: bool, last_played: int, is_osz2: bool, folder_name: str,
        last_checked_against_osu_repo: int, ignore_beatmap_sound: bool,
        ignore_beatmap_skin: bool, disable_storyboard: bool, disable_video: bool,
        visual_override: bool, last_modification: int, mania_scroll_speed: int
    ) -> None:
        self.artist = artist
        self.artist_unicode = artist_unicode
        self.title = title
        self.title_unicode = title_unicode
        self.creator = creator
        self.version = version
        self.audio_file = audio_file
        self.map_md5 = map_md5
        self.osu_file = osu_file
        self.ranked_status = ranked_status
        self.num_circles = num_circles
        self.num_sliders = num_sliders
        self.num_spinners = num_spinners
        self.last_edit_time = last_edit_time
        self.diff_ar = diff_ar
        self.diff_cs = diff_cs
        self.diff_hp = diff_hp
        self.diff_od = diff_od
        self.slider_velocity = slider_velocity
        self.star_ratings = star_ratings
        self.drain_time = drain_time
        self.total_time = total_time
        self.audio_preview = audio_preview
        self.timing_points = timing_points
        self.map_id = map_id
        self.set_id = set_id
        self.thread_id = thread_id
        self.osu_grade = osu_grade
        self.taiko_grade = taiko_grade
        self.catch_grade = catch_grade
        self.mania_grade = mania_grade
        self.local_offset = local_offset
        self.stack_leniency = stack_leniency
        self.game_mode = game_mode
        self.source = source
        self.tags = tags
        self.online_offset = online_offset
        self.title_font = title_font
        self.is_unplayed = is_unplayed
        self.last_played = last_played
        self.is_osz2 = is_osz2
        self.folder_name = folder_name
        self.last_checked_against_osu_repo = last_checked_against_osu_repo
        self.ignore_beatmap_sound = ignore_beatmap_sound
        self.ignore_beatmap_skin = ignore_beatmap_skin
        self.disable_storyboard = disable_storyboard
        self.disable_video = disable_video
        self.visual_override = visual_override
        self.last_modification = last_modification
        self.mania_scroll_speed = mania_scroll_speed

class BeatmapsDatabaseTimingPoint:
    __slots__ = ('bpm', 'offset', 'uninherited')
    def __init__(self, bpm: float, offset: float, uninherited: bool) -> None:
        self.bpm = bpm
        self.offset = offset
        self.uninherited = uninherited

class BeatmapsDatabase(osuDatabase):
    __slots__ = (
        'game_version', 'folder_count', 'account_unlocked', 'account_unlock_date',
        'player_name', 'num_maps', 'beatmaps', 'user_privileges'
    )
    def __init__(self, body_view: memoryview) -> None:
        self.game_version: int = 0
        self.folder_count: int = 0
        self.account_unlocked: bool = True
        self.account_unlock_date: Optional[datetime] = None
        self.player_name: str = ''
        self.num_maps: int = 0
        self.beatmaps: list[BeatmapsDatabaseBeatmap] = []
        self.user_privileges: int = 0
        super().__init__(body_view)

    def read_timing_point(self) -> BeatmapsDatabaseTimingPoint:
        bpm = self.read_f64()
        offset = self.read_f64()
        uninherited = self.read_i8()
        return BeatmapsDatabaseTimingPoint(bpm, offset, uninherited)

    def read_star_rating_pair(self) -> tuple[int, float]:
        assert self.read_i8() == 0x08
        val1 = Mods(self.read_i32())
        assert self.read_i8() == 0x0d
        val2 = self.read_f64()
        return (val1, val2)

    def read_beatmap(self) -> BeatmapsDatabaseBeatmap:
        if self.game_version < 2019_11_06:
            self.read_i32() # entry size in bytes
        artist = self.read_string()
        artist_unicode = self.read_string()
        title = self.read_string()
        title_unicode = self.read_string()
        creator = self.read_string()
        version = self.read_string()
        audio_file = self.read_string()
        map_md5 = self.read_string()
        osu_file = self.read_string()
        ranked_status = self.read_i8()
        num_circles = self.read_i16()
        num_sliders = self.read_i16()
        num_spinners = self.read_i16()
        last_edit_time = self.read_i64() # TODO: datetime
        if self.game_version < 2014_06_09:
            diff_ar = self.read_i8()
            diff_cs = self.read_i8()
            diff_hp = self.read_i8()
            diff_od = self.read_i8()
        else:
            diff_ar = self.read_f32()
            diff_cs = self.read_f32()
            diff_hp = self.read_f32()
            diff_od = self.read_f32()
        slider_velocity = self.read_f64()
        if self.game_version >= 2014_06_09:
            star_ratings = [dict(
                self.read_star_rating_pair()
                for _ in range(self.read_i32())
            ) for mode in range(4)]
        else:
            star_ratings = [None, None, None, None]
        drain_time = self.read_i32()
        total_time = self.read_i32()
        audio_preview = self.read_i32()
        timing_points = [self.read_timing_point()
                         for _ in range(self.read_i32())]
        map_id = self.read_i32()
        set_id = self.read_i32()
        thread_id = self.read_i32()
        osu_grade = self.read_i8()
        taiko_grade = self.read_i8()
        catch_grade = self.read_i8()
        mania_grade = self.read_i8()
        local_offset = self.read_i16()
        stack_leniency = self.read_f32()
        game_mode = self.read_i8()
        source = self.read_string()
        tags = self.read_string().split(' ')
        online_offset = self.read_i16()
        title_font = self.read_string()
        is_unplayed = self.read_i8() == 1
        last_played = self.read_i64()
        is_osz2 = self.read_i8() == 1
        folder_name = self.read_string()
        last_checked_against_osu_repo = self.read_i64() # ???
        ignore_beatmap_sound = self.read_i8() == 1
        ignore_beatmap_skin = self.read_i8() == 1
        disable_storyboard = self.read_i8() == 1
        disable_video = self.read_i8() == 1
        visual_override = self.read_i8() == 1
        if self.game_version < 2014_06_09:
            self.read_i16()
        last_modification = self.read_i32()
        mania_scroll_speed = self.read_i8()

        return BeatmapsDatabaseBeatmap(
            artist,
            artist_unicode,
            title,
            title_unicode,
            creator,
            version,
            audio_file,
            map_md5,
            osu_file,
            ranked_status,
            num_circles,
            num_sliders,
            num_spinners,
            last_edit_time,
            diff_ar,
            diff_cs,
            diff_hp,
            diff_od,
            slider_velocity,
            star_ratings,
            drain_time,
            total_time,
            audio_preview,
            timing_points,
            map_id,
            set_id,
            thread_id,
            osu_grade,
            taiko_grade,
            catch_grade,
            mania_grade,
            local_offset,
            stack_leniency,
            game_mode,
            source,
            tags,
            online_offset,
            title_font,
            is_unplayed,
            last_played,
            is_osz2,
            folder_name,
            last_checked_against_osu_repo,
            ignore_beatmap_sound,
            ignore_beatmap_skin,
            disable_storyboard,
            disable_video,
            visual_override,
            last_modification,
            mania_scroll_speed
        )

    def _read(self) -> None:
        self.game_version = self.read_i32()
        self.folder_count = self.read_i32()
        self.account_unlocked = self.read_i8() == 1
        self.account_unlock_date = self.read_i64()
        self.player_name = self.read_string()
        self.beatmaps = [self.read_beatmap() for _ in range(self.read_i32())]
        self.user_privileges = self.read_i32()

# collection.db

class CollectionsDatabaseCollection:
    __slots__ = ('name', 'num_maps', 'map_md5s')
    def __init__(self, name: str, num_maps: int, map_md5s: list[str]) -> None:
        self.name = name
        self.num_maps = num_maps
        self.map_md5s = map_md5s

class CollectionsDatabase(osuDatabase):
    __slots__ = ('game_version', 'collections')
    def __init__(self, body_view: memoryview) -> None:
        self.game_version: int = 0
        self.collections: list[CollectionsDatabaseCollection] = []
        super().__init__(body_view)

    def read_collection(self) -> CollectionsDatabaseCollection:
        collection_name = self.read_string()
        num_maps = self.read_i32()
        map_md5s = [self.read_string() for _ in range(num_maps)]
        return CollectionsDatabaseCollection(
            collection_name,
            num_maps,
            map_md5s
        )

    def _read(self) -> None:
        self.game_version = self.read_i32()
        self.collections.extend([
            self.read_collection()
            for _ in range(self.read_i32())
        ])

# scores.db

class ScoresDatabaseScore:
    __slots__ = (
        'game_mode', 'game_version', 'map_md5', 'player_name', 'replay_md5',
        'n300', 'n100', 'n50', 'ngeki', 'nkatu', 'nmiss',
        'score', 'max_combo', 'perfect', 'mods',
        'time_played', 'score_id', 'additional_mod_info')
    def __init__(
        self, game_mode: int, game_version: int,
        map_md5: str, player_name: str, replay_md5: str,
        n300: int, n100: int, n50: int, ngeki: int, nkatu: int, nmiss: int,
        score: int, max_combo: int, perfect: bool, mods: int,
        time_played: int, score_id: int, additional_mod_info: Optional[float]
    ) -> None:
        self.game_mode = game_mode
        self.game_version = game_version
        self.map_md5 = map_md5
        self.player_name = player_name
        self.replay_md5 = replay_md5
        self.n300 = n300
        self.n100 = n100
        self.n50 = n50
        self.ngeki = ngeki
        self.nkatu = nkatu
        self.nmiss = nmiss
        self.score = score
        self.max_combo = max_combo
        self.perfect = perfect
        self.mods = mods
        self.time_played = time_played
        self.score_id = score_id
        self.additional_mod_info = additional_mod_info

class ScoresDatabaseBeatmap:
    __slots__ = ('md5', 'num_scores', 'scores')
    def __init__(self, md5: str, num_scores: int,
                 scores: list[ScoresDatabaseScore]) -> None:
        self.md5 = md5
        self.num_scores = num_scores
        self.scores = scores

class ScoresDatabase(osuDatabase):
    __slots__ = ('game_version', 'beatmaps')
    def __init__(self, body_view: memoryview) -> None:
        self.game_version: int = 0
        self.beatmaps: list[ScoresDatabaseBeatmap] = []
        super().__init__(body_view)

    def read_score(self) -> ScoresDatabaseScore:
        game_mode = self.read_i8()
        game_version = self.read_i32()
        map_md5 = self.read_string()
        player_name = self.read_string()
        replay_md5 = self.read_string()
        n300 = self.read_i16()
        n100 = self.read_i16()
        n50 = self.read_i16()
        ngeki = self.read_i16()
        nkatu = self.read_i16()
        nmiss = self.read_i16()
        score = self.read_i32()
        max_combo = self.read_i16()
        perfect = self.read_i8() == 1
        mods = Mods(self.read_i32())
        self.read_string() # empty
        time_played = self.read_i64()
        self.read_i32() # -1
        score_id = self.read_i64()
        if mods & Mods.TARGET:
            additional_mod_info = self.read_f64()
        else:
            additional_mod_info = None

        return ScoresDatabaseScore(
            game_mode, game_version, map_md5, player_name, replay_md5,
            n300, n100, n50, ngeki, nkatu, nmiss,
            score, max_combo, perfect, mods, time_played,
            score_id, additional_mod_info
        )

    def read_beatmap(self) -> ScoresDatabaseBeatmap:
        map_md5 = self.read_string()
        num_scores = self.read_i32()
        scores = [self.read_score() for _ in range(num_scores)]
        return ScoresDatabaseBeatmap(
            md5=map_md5,
            num_scores=num_scores,
            scores=scores
        )

    def _read(self) -> None:
        self.game_version = self.read_i32()
        num_maps = self.read_i32()
        self.beatmaps.extend([
            self.read_beatmap()
            for _ in range(num_maps)
        ])

if __name__ == '__main__':
    # TODO: is there a nice way to find the currently logged
    #       in windows user's name or windows user path?
    import time

    from cmyui.utils import magnitude_fmt_time

    t1 = time.perf_counter_ns()

    # osu!.db
    beatmaps_db = BeatmapsDatabase.from_file('/mnt/c/Users/cmyui/AppData/Local/osu!/osu!.db')
    print(f'read osu!.db in {magnitude_fmt_time((t2 := time.perf_counter_ns()) - t1)}')

    # collections.db
    collections_db = CollectionsDatabase.from_file('/mnt/c/Users/cmyui/AppData/Local/osu!/collection.db')
    print(f'read collection.db in {magnitude_fmt_time((t3 := time.perf_counter_ns()) - t2)}')

    # scores.db
    scores_db = ScoresDatabase.from_file('/mnt/c/Users/cmyui/AppData/Local/osu!/scores.db')
    print(f'read scores.db in {magnitude_fmt_time(time.perf_counter_ns() - t3)}')
