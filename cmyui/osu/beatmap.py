""" Tools for working with osu!'s .osu file format """
# -*- coding: utf-8 -*-

import os
from enum import IntEnum
from enum import IntFlag
from enum import unique
from functools import cache
from functools import cached_property
from typing import Callable
from typing import NamedTuple
from typing import Optional
from typing import Union

from cmyui import utils
from cmyui import logging
from cmyui.osu.replay import ReplayFrame

__all__ = ('Beatmap', 'HitObject', 'HitCircle', 'Slider', 'Spinner', 'ManiaHold',
           'CurveType', 'HitSound', 'HitSample', 'SampleSet', 'TimingPoint',
           'Colour', 'OverlayPosition', 'Colour', 'Event', 'Background',
           'Video', 'Break')

"""A relatively complete pure-py (slow) beatmap parser for osu!.

This is an active work in progress, and everything is subject
to major refactoring. Some portions may be implemented as c
extensions to help with the speed issue, since (in my opinion)
it isn't currently fit for use in any large scale web applications.
"""

# TODO: reduce overall inconsistencies in object types

StrOrBytesPath = Union[str, bytes, os.PathLike[str], os.PathLike[bytes]]

class TimingPoint:
    __slots__ = (
        'time', 'beat_length', 'meter', 'sample_set', 'sample_index',
        'volume', 'uninherited', 'effects', '__dict__'
    )

    def __init__(
        self, time: int, beat_length: float,
        meter: int, sample_set: int, sample_index: int,
        volume: int, uninherited: bool, effects: int
    ) -> None:
        self.time = time
        self.beat_length = beat_length
        self.meter = meter
        self.sample_set = sample_set
        self.sample_index = sample_index
        self.volume = volume
        self.uninherited = uninherited
        self.effects = effects

    @cached_property
    def bpm(self) -> float:
        return 1 / self.beat_length * 1000 * 60

    @classmethod
    def from_str(cls, s: str) -> 'TimingPoint':
        tp_split = s.split(',')

        # TODO: find version where this changed
        #       and use it for the check instead
        split_len = len(tp_split)

        try: # TODO: find version with the change?
            if split_len == 8:
                return cls(
                    time=int(tp_split[0]),
                    beat_length=float(tp_split[1]),
                    meter=int(tp_split[2]),
                    sample_set=int(tp_split[3]),
                    sample_index=int(tp_split[4]),
                    volume=int(tp_split[5]),
                    uninherited=tp_split[6] == '1',
                    effects=int(tp_split[7])
                )
            elif split_len == 2:
                return cls(
                    time=int(tp_split[0]),
                    beat_length=float(tp_split[1])
                )
        except ValueError:
            # failed to cast something
            return

@unique
class SampleSet(IntEnum):
    NONE = 0
    NORMAL = 1
    SOFT = 2
    DRUM = 3

    def __str__(self) -> str:
        return self.name.lower()

class HitSample:
    __slots__ = ('normal_set', 'addition_set', 'index', 'volume', 'filename')

    def __init__(
        self, normal_set: SampleSet, addition_set: SampleSet,
        index: int, volume: int, filename: str
    ) -> None:
        self.normal_set = normal_set
        self.addition_set = addition_set
        self.index = index
        self.volume = volume
        self.filename = filename

    @classmethod
    @cache
    def from_str(cls, s: str) -> 'HitSample':
        if len(hs_split := s.split(':')) != 5:
            return

        if all(map(str.isdecimal, hs_split[:-1])):
            return cls(
                normal_set=SampleSet(int(hs_split[0])),
                addition_set=SampleSet(int(hs_split[1])),
                index=int(hs_split[2]),
                volume=int(hs_split[3]),
                filename=hs_split[4]
            )

class ObjectType:
    HIT_CIRCLE = 1 << 0
    SLIDER = 1 << 1
    NEW_COMBO = 1 << 2
    SPINNER = 1 << 3

    SKIP_ONE = 1 << 4
    SKIP_TWO = 1 << 5
    SKIP_THREE = 1 << 6

    MANIA_HOLD = 1 << 7

@unique
class HitSound(IntFlag):
    NORMAL = 1 << 0
    WHISTLE = 1 << 1
    FINISH = 1 << 2
    CLAP = 1 << 3

    def __str__(self) -> str:
        return self.name.lower()

class HitObject:
    __slots__ = ('x', 'y', 'time',
                 'child_tp', 'parent_tp',
                 'hit_sound', 'hit_sample')

    def __init__(
        self,
        x: int,
        y: int,
        time: int,
        child_tp: TimingPoint,
        parent_tp: TimingPoint,
        hit_sound: HitSound,
        hit_sample: Optional[HitSample] = None
    ) -> None:
        self.x = x
        self.y = y
        self.time = time

        self.child_tp = child_tp
        self.parent_tp = parent_tp

        # very closely related
        # XXX: i could actually refactor these to
        # be in a single class (and may), but i think
        # it might confuse people who are reading osu!'s
        # implementation to make sense of it? idk man lol
        self.hit_sound = hit_sound
        self.hit_sample = hit_sample

    def determine_judgement(
        self,
        keypress_frame: ReplayFrame,
        hit_windows: dict[int, float]
    ) -> 'Judgement':
        hit_error = keypress_frame.time - self.time

        if isinstance(self, HitCircle):
            if abs(hit_error) <= hit_windows[300]:
                return Judgement300(self, keypress_frame)
            elif abs(hit_error) <= hit_windows[100]:
                return Judgement100(self, keypress_frame)
            elif abs(hit_error) <= hit_windows[50]:
                return Judgement50(self, keypress_frame)
            else:
                return JudgementMiss(self, keypress_frame)
        elif isinstance(self, Slider): # TODO
            return Judgement300(self, keypress_frame)
        elif isinstance(self, Spinner): # TODO
            return Judgement300(self, keypress_frame)
        else:
            breakpoint()
            print()

class Judgement:
    __slots__ = ('hitobj', 'keypress_frame', 'hit_error')
    def __init__(self, hitobj: HitObject,
                 keypress_frame: ReplayFrame) -> None:
        self.hitobj = hitobj
        self.keypress_frame = keypress_frame

        self.hit_error = keypress_frame.time - hitobj.time

class Judgement300(Judgement):
    def __repr__(self) -> str:
        return (f'{logging.Ansi.LCYAN!r}300{logging.Ansi.RESET!r} on {self.hitobj} - '
                f'{{{self.keypress_frame.x:.2f} {self.keypress_frame.y:.2f}}}')
class Judgement100(Judgement):
    def __repr__(self) -> str:
        return (f'{logging.Ansi.LGREEN!r}100{logging.Ansi.RESET!r} on {self.hitobj} - '
                f'{{{self.keypress_frame.x:.2f} {self.keypress_frame.y:.2f}}}')
class Judgement50(Judgement):
    def __repr__(self) -> str:
        return (f'{logging.Ansi.LMAGENTA!r}50{logging.Ansi.RESET!r} on {self.hitobj} - '
                f'{{{self.keypress_frame.x:.2f} {self.keypress_frame.y:.2f}}}')
class JudgementMiss(Judgement):
    def __repr__(self) -> str:
        return (f'{logging.Ansi.LRED!r}Miss{logging.Ansi.RESET!r} on {self.hitobj} - '
                f'{{{self.keypress_frame.x:.2f} {self.keypress_frame.y:.2f}}}')

class HitCircle(HitObject):
    # hitcircle is simple, nothing extra,
    # so we don't have to write constructor

    def __repr__(self) -> str:
        return f'Circle @ {{{self.x} {self.y}}}'

    @classmethod
    def from_str(cls, s: str, **kwargs):
        if s != '0:0:0:0:':
            kwargs['hit_sample'] = HitSample.from_str(s)

        return cls(**kwargs)

@unique
class CurveType(IntEnum):
    Bezier = 0
    Catmull = 1
    Linear = 2
    Perfect = 3

    @staticmethod
    @cache
    def from_str(s: str) -> 'CurveType':
        return {
            'B': CurveType.Bezier, 'C': CurveType.Catmull,
            'L': CurveType.Linear, 'P': CurveType.Perfect
        }[s]

    #def __str__(self) -> str:
    #    # first char of character
    #    return self.name[0]

class Slider(HitObject):
    __slots__ = (
        'curve_type', 'curve_points', 'slides',
        'length', 'edge_sounds', 'edge_sets'
    )

    def __init__(
        self, curve_type: CurveType,
        curve_points: list[tuple[int, int]],
        slides: int,
        length: float,
        edge_sounds: list[int] = [],
        edge_sets: list[list[int, int]] = [],
        **kwargs
    ) -> None:
        self.curve_type = curve_type
        self.curve_points = curve_points
        self.slides = slides
        self.length = length
        self.edge_sounds = edge_sounds
        self.edge_sets = edge_sets

        super().__init__(**kwargs)

    def __repr__(self) -> str:
        return f'Slider [{self.curve_type.name}] @ {{{self.x} {self.y}}}'

    @classmethod
    def from_str(cls, s: str, **kwargs):
        if len(split := s.split(',')) < 3:
            return

        _curve, _slides, _slen, *_extra = split
        ctype, cpoints = _curve.split('|', 1)

        if _extra:
            assert len(_extra) == 3
            kwargs['edge_sounds'] = list(map(int, _extra[0].split('|')))
            kwargs['edge_sets'] = [x.split(':', 1) for x in _extra[1].split('|')]
            kwargs['hit_sample'] = HitSample.from_str(_extra[2])

        curve_points = []
        for entry in cpoints.split('|'):
            split = entry.split(':', maxsplit=1)
            curve_points.append((int(split[0]), int(split[1])))

        return cls(
            curve_type=CurveType.from_str(ctype),
            curve_points=curve_points,
            slides=int(_slides),
            length=float(_slen),
            **kwargs
        )

class Spinner(HitObject):
    __slots__ = ('end_time',)

    def __init__(self, end_time: int, **kwargs) -> None:
        self.end_time = end_time

        super().__init__(**kwargs)

    @classmethod
    def from_str(cls, s, **kwargs):
        if len(split := s.split(',')) != 2:
            return

        if split[0].isdecimal():
            if split[1] != '0:0:0:0:':
                kwargs['hit_sample'] = HitSample.from_str(split[1])

            return cls(end_time=int(split[0]), **kwargs)

class ManiaHold(HitObject):
    __slots__ = ('end_time',)

    def __init__(self, end_time: int, **kwargs) -> None:
        self.end_time = end_time

        super().__init__(**kwargs)

        # `self.x` determines the column the hold will be in;
        # it can be determined with floor(x * columnCount / 512)
        # clamped between 0 and columnCount - 1
        # y will default to the centre of playfield, 192

    @classmethod
    def from_str(cls, s, **kwargs):
        if len(split := s.split(':')) != 2:
            return

        if split[0].isdecimal():
            if split[1] != '0:0:0:0:':
                kwargs['hit_sample'] = HitSample.from_str(split[1])

            return cls(end_time=int(split[0]), **kwargs)

class Colour(NamedTuple):
    r: int
    g: int
    b: int

    @classmethod
    def from_str(cls, s: str):
        if len(split := s.split(',')) != 3:
            return

        if all(map(str.isdecimal, split)):
            return cls(
                r=int(split[0]),
                g=int(split[1]),
                b=int(split[2])
            )

@unique
class OverlayPosition(IntEnum):
    No_Change = 0
    Below = 1
    Above = 2

# TODO: events get quite a bit crazier
#       if we want to support storyboards.
class Event:
    __slots__ = ('start_time',)

    def __init__(self, start_time: int) -> None:
        self.start_time = start_time

    @staticmethod
    def from_str(s: str):
        if len(split := s.split(',', 2)) != 3:
            return

        if split[1].isdecimal():
            # a bit unsafe but w/e
            _type = split[0]

            if _type.isdecimal():
                ev_map = (Background, Video, Break)
                _type = int(_type)
            else:
                ev_map = {'Video': Video, 'Break': Break}

            if _type in ev_map:
                cls = ev_map[_type]
                return cls.from_str(split[2], start_time=int(split[1]))

class Background(Event):
    __slots__ = ('filename', 'x_offset', 'y_offset')

    def __init__(
        self, filename: str,
        x_offset: Optional[int] = None,
        y_offset: Optional[int] = None,
        **kwargs
    ) -> None:
        self.filename = filename
        self.x_offset = x_offset
        self.y_offset = y_offset

        super().__init__(**kwargs)

    @classmethod
    def from_str(cls, s: str, **kwargs):
        split = s.split(',', 2)
        lsplit = len(split)

        if lsplit == 3:
            x_off, y_off = split[1:3]
            if not (x_off.isdecimal() and y_off.isdecimal()):
                return

            kwargs['x_offset'] = int(x_off)
            kwargs['y_offset'] = int(y_off)
        elif lsplit != 1:
            raise Exception('Invalid arg count for a background.')

        kwargs['filename'] = split[0].strip('"')

        return cls(**kwargs)

# TODO: this is the exact same as Background lol
class Video(Event):
    __slots__ = ('filename', 'x_offset', 'y_offset')

    def __init__(
        self, filename: str,
        x_offset: Optional[int] = None,
        y_offset: Optional[int] = None,
        **kwargs
    ) -> None:
        self.filename = filename
        self.x_offset = x_offset
        self.y_offset = y_offset

        super().__init__(**kwargs)

    @classmethod
    def from_str(cls, s: str, **kwargs):
        split = s.split(',', 2)
        lsplit = len(split)

        if lsplit == 3:
            x_off, y_off = split[1:3]
            if not (x_off.isdecimal() and y_off.isdecimal()):
                return

            kwargs['x_offset'] = int(x_off)
            kwargs['y_offset'] = int(y_off)
        elif lsplit != 1:
            raise Exception('Invalid arg count for a background.')

        kwargs['filename'] = split[0].strip('"')

        return cls(**kwargs)

class Break(Event):
    __slots__ = ('end_time',)

    def __init__(self, end_time: int, **kwargs) -> None:
        self.end_time = end_time

        super().__init__(**kwargs)

    @classmethod
    def from_str(cls, s: str, **kwargs):
        if s.isdecimal():
            return cls(end_time=int(s), **kwargs)

# TODO: storyboards?

class Beatmap:
    __slots__ = (
        'file_version', 'audio_filename', 'audio_leadin',
        'preview_time', 'countdown', 'sample_set', 'stack_leniency', 'mode',
        'letterbox_in_breaks', 'use_skin_sprites', 'overlay_position',
        'skin_preference', 'epilepsy_warning', 'countdown_offset',
        'special_style', 'widescreen_storyboard', 'samples_match_playback_rate',
        'bookmarks', 'distance_spacing', 'beat_divisor', 'grid_size',
        'timeline_zoom', 'title', 'title_unicode', 'artist', 'artist_unicode',
        'creator', 'version', 'source', 'tags', 'id', 'set_id', 'diff_hp',
        'diff_cs', 'diff_od', 'diff_ar', 'slider_multiplier',
        'slider_tick_rate', 'backgrounds', 'breaks', 'videos', 'storyboards',
        'timing_points', 'colours', 'hit_objects', '_data', '_offset',

        # deprecated stuff
        #'audio_hash', 'storyfire_in_front',
        #'always_show_playback', 'storyboards'
    )

    def __init__(self, data: str) -> None:
        self._data = data
        self._offset = 0

        self.file_version: Optional[int] = None

        """ general """
        self.audio_filename: Optional[str] = None
        self.audio_leadin: Optional[int] = None
        #self.audio_hash: Optional[str] = None # deprecated
        self.preview_time: Optional[int] = None
        self.countdown: Optional[int] = None
        self.sample_set: Optional[str] = None
        self.stack_leniency: Optional[float] = None
        self.mode: Optional[int] = None
        self.letterbox_in_breaks: Optional[bool] = None
        #self.storyfire_in_front: Optional[bool] = None # deprecated
        self.use_skin_sprites: Optional[bool] = None
        #self.always_show_playback: Optional[bool] = None # deprecated
        self.overlay_position: Optional[str] = None
        self.skin_preference: Optional[str] = None
        self.epilepsy_warning: Optional[bool] = None
        self.countdown_offset: Optional[int] = None
        self.special_style: Optional[bool] = None
        self.widescreen_storyboard: Optional[bool] = None
        self.samples_match_playback_rate: Optional[bool] = None

        """ editor """
        self.bookmarks: Optional[list[int]] = None
        self.distance_spacing: Optional[float] = None
        self.beat_divisor: Optional[float] = None
        self.grid_size: Optional[int] = None
        self.timeline_zoom: Optional[float] = None

        """ metadata """
        self.title: Optional[str] = None
        self.title_unicode: Optional[str] = None
        self.artist: Optional[str] = None
        self.artist_unicode: Optional[str] = None
        self.creator: Optional[str] = None
        self.version: Optional[str] = None
        self.source: Optional[str] = None
        self.tags: Optional[list[str]] = None
        self.id: Optional[int] = None
        self.set_id: Optional[int] = None

        """ difficulty """
        self.diff_hp: Optional[float] = None
        self.diff_cs: Optional[float] = None
        self.diff_od: Optional[float] = None
        self.diff_ar: Optional[float] = None
        self.slider_multiplier: Optional[float] = None
        self.slider_tick_rate: Optional[float] = None

        """ events """
        self.backgrounds: Optional[list[Background]] = None
        self.breaks: Optional[list[Break]] = None
        self.videos: Optional[list[Video]] = None
        #self.storyboards: Optional[list[Storyboard]] = None # TODO

        """ timing points, colours & hit objects """
        self.timing_points: Optional[list[TimingPoint]] = None
        self.colours: Optional[dict[str, Colour]] = None
        self.hit_objects: Optional[list[HitObject]] = None


    def __repr__(self) -> str:
        return (
            f'{self.artist} - {self.title} ({self.creator}) [{self.version}]'
        )

    @property
    def data(self) -> str:
        # return all data starting from
        # the internal offset of the reader.
        return self._data[self._offset:]

    @classmethod
    def from_data(cls, data: str) -> Optional['Beatmap']:
        b = cls(data)
        b._parse()

        if b.file_version is None:
            # failed to parse the map.
            # this will also log the error to stdout
            return

        return b

    @classmethod
    def from_file(cls, path: StrOrBytesPath) -> Optional['Beatmap']:
        if os.path.exists(path):
            with open(path, 'r') as f:
                return Beatmap.from_data(f.read())

    def _parse(self) -> None:
        sec_start = self.data.find('\n\n')
        self._offset += len('osu file format v')

        ver_str = self.data[:sec_start - self._offset]
        if not ver_str.isdecimal():
            logging.log('Failed to parse version string.', logging.Ansi.LRED)
            return

        self.file_version = int(ver_str)

        for name, func in (
            ('General', self._parse_general),
            ('Editor', self._parse_editor),
            ('Metadata', self._parse_metadata),
            ('Difficulty', self._parse_difficulty),
            ('Events', self._parse_events),
            ('TimingPoints', self._parse_timing_points),
            ('Colours', self._parse_colours),
            ('HitObjects', self._parse_hit_objects)
        ):
            self._parse_section(name, func)

        # TODO
        # parsing file completed, now
        # construct any additional info
        # now that we have everything.
        #self._parse_end()

    def _parse_section(
        self, name: str,
        parse_method: Callable[['Beatmap'], None]
    ) -> None:
        to_find = f'\n\n[{name}]\n'
        offs = self.data.find(to_find)

        if offs == -1:
            # skip any sections not found - the beatmap
            # object will simply have `None` attributes
            # if not parsed from the file.
            return

        self._offset += offs + len(to_find)
        parse_method()

    def _parse_general(self) -> None:
        end_of_section = self.data.find('\n\n')

        for line in self.data[:end_of_section].splitlines():
            key, val = line.split(':', maxsplit=1)
            val = val.lstrip()

            # how should i clean this.. lol

            if key == 'AudioFilename':
                self.audio_filename = val
            elif key == 'AudioLeadIn':
                if val.isdecimal():
                    self.audio_leadin = int(val)
            # deprecated
            #elif key == 'AudioHash':
            #    self.audio_hash = val
            elif key == 'PreviewTime':
                if val.isdecimal():
                    self.preview_time = int(val)
            elif key == 'Countdown':
                if val.isdecimal():
                    self.countdown = int(val)
            elif key == 'SampleSet':
                if val in ('Normal', 'Soft', 'Drum'):
                    self.sample_set = {
                        'Normal': SampleSet.NORMAL,
                        'Soft': SampleSet.SOFT,
                        'Drum': SampleSet.DRUM
                    }[val]
            elif key == 'StackLeniency':
                if utils._isdecimal(val, _float=True):
                    self.stack_leniency = float(val)
            elif key == 'Mode':
                if val.isdecimal():
                    self.mode = int(val)
            elif key == 'LetterboxInBreaks':
                self.letterbox_in_breaks = val == '1'
            # deprecated
            #elif key == 'StoryFireInFront':
            #    self.story_fire_in_front = val == '1'
            elif key == 'UseSkinSprites':
                self.use_skin_sprites = val == '1'
            # deprecated
            #elif key == 'AlwaysShowPlayfield':
            #    self.always_show_playfield = val == '1'
            elif key == 'OverlayPosition':
                if val in ('NoChange', 'Below', 'Above'):
                    self.overlay_position = {
                        'NoChange': OverlayPosition.No_Change,
                        'Below': OverlayPosition.Below,
                        'Above': OverlayPosition.Above
                    }[val]
            elif key == 'SkinPreference':
                self.skin_preference = val
            elif key == 'EpilepsyWarning':
                self.epilepsy_warning = val == '1'
            elif key == 'CountdownOffset':
                if val.isdecimal():
                    self.countdown_offset = int(val)
            elif key == 'SpecialStyle':
                self.special_style = val == '1'
            elif key == 'WidescreenStoryboard':
                self.widescreen_storyboard = val == '1'
            elif key == 'SamplesMatchPlaybackRate':
                self.samples_match_playback_rate = val == '1'
            else:
                logging.log(
                    f'Unknown [General] key {key}',
                    logging.Ansi.LYELLOW
                )

        self._offset += end_of_section

    def _parse_editor(self) -> None:
        e_end = self.data.find('\n\n')

        for line in self.data[:e_end].splitlines():
            key, val = line.split(':', maxsplit=1)
            val = val.lstrip()

            if key == 'Bookmarks':
                bookmarks_str = val.split(',')
                if all(map(str.isdecimal, bookmarks_str)):
                    self.bookmarks = list(map(int, bookmarks_str))
            elif key == 'DistanceSpacing':
                if utils._isdecimal(val, _float=True):
                    self.distance_spacing = float(val)
            elif key == 'BeatDivisor':
                if utils._isdecimal(val, _float=True):
                    self.beat_divisor = float(val)
            elif key == 'GridSize':
                if val.isdecimal():
                    self.grid_size = int(val)
            elif key == 'TimelineZoom':
                if utils._isdecimal(val, _float=True):
                    self.timeline_zoom = float(val)
            else:
                logging.log(
                    f'Unknown [Editor] key {key}',
                    logging.Ansi.LYELLOW
                )

        self._offset += e_end

    def _parse_metadata(self) -> None:
        m_end = self.data.find('\n\n')

        for line in self.data[:m_end].splitlines():
            key, val = line.split(':', maxsplit=1)

            if key == 'Title':
                self.title = val
            elif key == 'TitleUnicode':
                self.title_unicode = val
            elif key == 'Artist':
                self.artist = val
            elif key == 'ArtistUnicode':
                self.artist_unicode = val
            elif key == 'Creator':
                self.creator = val
            elif key == 'Version':
                self.version = val
            elif key == 'Source':
                self.source = val
            elif key == 'Tags':
                self.tags = val.split(' ')
            elif key == 'BeatmapID':
                if val.isdecimal():
                    self.id = int(val)
            elif key == 'BeatmapSetID':
                if val.isdecimal():
                    self.set_id = int(val)
            else:
                logging.log(
                    f'Unknown [Metadata] key {key}',
                    logging.Ansi.LYELLOW
                )

        self._offset += m_end

    def _parse_difficulty(self) -> None:
        d_end = self.data.find('\n\n')

        for line in self.data[:d_end].splitlines():
            key, val = line.split(':', maxsplit=1)

            # all diff params should be float
            if utils._isdecimal(val, _float=True):
                if key == 'HPDrainRate':
                    self.diff_hp = float(val)
                elif key == 'CircleSize':
                    self.diff_cs = float(val)
                elif key == 'OverallDifficulty':
                    self.diff_od = float(val)
                elif key == 'ApproachRate':
                    self.diff_ar = float(val)
                elif key == 'SliderMultiplier':
                    self.slider_multiplier = float(val)
                elif key == 'SliderTickRate':
                    self.slider_tick_rate = float(val)
                else:
                    logging.log(
                        f'Unknown [Difficulty] key {key}',
                        logging.Ansi.LYELLOW
                    )

        self._offset += d_end

    def _parse_events(self) -> None:
        self.backgrounds = []
        self.videos = []
        self.breaks = []

        # this is actually events, backgrounds,
        # videos, breaks, and storyboards.. lol
        ev_end = self.data.find('\n\n')

        for line in self.data[:ev_end].splitlines():
            if line[:2] == '//':
                continue

            ev = Event.from_str(line)

            if ev is not None:
                if isinstance(ev, Background):
                    self.backgrounds.append(ev)
                elif isinstance(ev, Video):
                    self.videos.append(ev)
                elif isinstance(ev, Break):
                    self.breaks.append(ev)

        self._offset += ev_end

    def _parse_timing_points(self) -> None:
        self.timing_points = []

        # find the end of the timing points section
        tp_end = self.data.find('\n\n')

        # iterate through each line, parsing
        # the lines into timing point objects.
        for line in self.data[:tp_end].splitlines():
            if not (tp := TimingPoint.from_str(line)):
                logging.printc(
                    f'Failed to parse timing point? "{line}"',
                    logging.Ansi.RED
                )
                continue

            self.timing_points.append(tp)

        self._offset += tp_end

    def _parse_colours(self) -> None:
        self.colours = {}

        # find the end of the colours section
        cl_end = self.data.find('\n\n')

        for line in self.data[:cl_end].splitlines():
            key, val = line.split(':', maxsplit=1)
            key = key.rstrip()
            val = val.lstrip()

            if colour := Colour.from_str(val):
                # add to beatmap's colours
                self.colours[key] = colour

        self._offset += cl_end

    def _parse_hit_objects(self) -> None:
        self.hit_objects = []

        parent_tp = self.timing_points[0]
        child_tp = self.timing_points[0]
        next_tp_index = 1

        # iterate through each line, parsing
        # the lines into hit object objects
        for line in self.data.splitlines():
            if not (
                len(args := line.split(',', 5)) == 6 and
                all(map(str.isdecimal, args[:-1]))
            ):
                continue

            t = int(args[3])

            if t & ObjectType.HIT_CIRCLE:
                cls = HitCircle
            elif t & ObjectType.SLIDER:
                cls = Slider
            elif t & ObjectType.SPINNER:
                cls = Spinner
            elif t & ObjectType.MANIA_HOLD:
                cls = ManiaHold
            else:
                logging.log(
                    f'Unknown hit obj type {t}',
                    logging.Ansi.LYELLOW
                )
                continue

            time = int(args[2])

            while time >= self.timing_points[next_tp_index].time:
                child_tp = self.timing_points[next_tp_index]
                if child_tp.uninherited:
                    parent_tp = child_tp
                next_tp_index += 1

            obj = cls.from_str(
                s=args[5],
                x=int(args[0]),
                y=int(args[1]),
                time=time,
                hit_sound=HitSound(int(args[4])),
                parent_tp=parent_tp,
                child_tp=child_tp
            )
            self.hit_objects.append(obj)

        self._offset += len(self.data)

if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.realpath(__file__)))

    import time
    st = time.time_ns()
    bmap = Beatmap.from_file('tstmts.osu')
    elapsed = utils.magnitude_fmt_time(time.time_ns()-st)
    print(f'Parsed {bmap} in {elapsed}.')

    #import cProfile
    #cProfile.run("Beatmap.from_file('tstmts.osu')", filename='bmap.stats')
