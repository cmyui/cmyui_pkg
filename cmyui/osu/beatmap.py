# -*- coding: utf-8 -*-

import os
from enum import IntEnum
from enum import IntFlag
from enum import unique
from functools import cached_property
from functools import partial
from typing import Callable
from typing import Optional

from cmyui import utils

__all__ = ('TimingPoint', 'SampleSet', 'HitSample',
           'HitObject', 'HitCircle', 'Slider', 'Spinner', 'ManiaHold',
           'Beatmap', 'CurveType', 'HitSound', 'Colour', 'OverlayPosition',
           'Event', 'Background', 'Video', 'Break')

"""\
a pretty messy but complete osu! beatmap parser.

written over the span of about 12 hours,
probably has some cleanup coming, but functionally
it's actually pretty good; it has near full coverage.

Basic usage:
```
  b = Beatmap.from_file('1234567.osu')
  if not b:
    # file not found
    ...

  # now you have basically everything
  # you can think of from a beatmap.

  # most complex structures are classes,
  # with many attributes within them..
  for tp in b.timing_points:
    print(tp.time, tp.beat_length, tp.meter, ...)
    ...

  for obj in b.hit_objects:
    print(obj.x, obj.y, obj.time, obj.hit_sample.volume, ...)
    ...

  # im too baked to give more examples, so
  # just check the Beatmap class below >B)
  ...
```

soon i'll be adding some kind of simulator that can play
through the map and achieve a perfect score.. it would be
useful for scorev2 detection on gulag too.. could finally
be rid of the scorev2 bugginess :o
"""

# TODO: some of the classmethod usage in this is pretty nasty,
# seems like i didn't fully understand it at the time of writing.

# who knows why, but different sections
# of the beatmap file use different
# k:v pair spacing in them.. lol
_separators = {
    'General': ': ',
    'Editor': ': ',
    'Metadata': ':',
    'Difficulty': ':',
    'Colours': ' : '
}

class TimingPoint:
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
    def bpm(self) -> int:
        return 1 / self.beat_length * 1000 * 60

    @classmethod
    def from_str(cls, s: str) -> 'TimingPoint':
        if len(tp_split := s.split(',')) != 8:
            return

        isfloat_n = partial(
            utils._isdecimal,
            _float = True,
            _negative = True
        )

        # make sure all params are at least floats
        if not all(isfloat_n(x) for x in tp_split):
            return

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

@unique
class SampleSet(IntEnum):
    NONE = 0
    NORMAL = 1
    SOFT = 2
    DRUM = 3

    def __str__(self) -> str:
        return self.name.lower()

class HitSample:
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
    def from_str(cls, s: str) -> 'HitSample':
        if len(hs_split := s.split(':')) != 5:
            return

        if not all(x.isdecimal() for x in hs_split[:-1]):
            return

        return cls(
            normal_set=SampleSet(int(hs_split[0])),
            addition_set=SampleSet(int(hs_split[1])),
            index=int(hs_split[2]),
            volume=int(hs_split[3]),
            filename=hs_split[4]
        )

HIT_CIRCLE = 1 << 0
SLIDER = 1 << 1
NEW_COMBO = 1 << 2
SPINNER = 1 << 3

SKIP_ONE = 1 << 4
SKIP_TWO = 1 << 5
SKIP_THREE = 1 << 6

MANIA_HOLD = 1 << 7

""" # slow :(
@unique
class ObjectType(IntFlag):
    HIT_CIRCLE = 1 << 0
    SLIDER = 1 << 1
    NEW_COMBO = 1 << 2
    SPINNER = 1 << 3

    # a bit weird?
    # maybe it should be a property
    # where it just checks all the bits
    # or soemthing.. will think abt this
    SKIP_ONE = 1 << 4
    SKIP_TWO = 1 << 5
    SKIP_THREE = 1 << 6

    MANIA_HOLD = 1 << 7
"""

@unique
class HitSound(IntFlag):
    NORMAL = 1 << 0
    WHISTLE = 1 << 1
    FINISH = 1 << 2
    CLAP = 1 << 3

    def __str__(self) -> str:
        return self.name.lower()

class HitObject:
    def __init__(
        self,
        x: int, y: int, time: int,
        hit_sound: HitSound,
        hit_sample: Optional[HitSample] = None
    ) -> None:
        self.x = x
        self.y = y
        self.time = time

        # very closely related
        # XXX: i could actually refactor these to
        # be in a single class (and may), but i think
        # it might confuse people who are reading osu!'s
        # implementation to make sense of it? idk man lol
        self.hit_sound = hit_sound
        self.hit_sample = hit_sample

    @staticmethod
    def from_str(s: str) -> 'HitObject':
        if len(args := s.split(',', 5)) != 6:
            return

        # make sure all params so far are integral
        if not all(x.isdecimal() for x in args[:-1]):
            return

        # parse common items from hit object
        # the first 5 params of any hitobject
        type = int(args[3])

        # hit sample not read yet, it may be at the
        # end of the args list depending on the type.

        cls = None

        if type & HIT_CIRCLE:
            cls = HitCircle
        elif type & SLIDER:
            cls = Slider
        elif type & SPINNER:
            cls = Spinner
        elif type & MANIA_HOLD:
            cls = ManiaHold
        else:
            return

        return cls.from_str(
            s=args[5],
            x=int(args[0]),
            y=int(args[1]),
            time=int(args[2]),
            hit_sound=HitSound(int(args[4]))
        ) # pass rest of the args

class HitCircle(HitObject):
    # hitcircle is simple, nothing extra,
    # so we don't have to write constructor

    @classmethod
    def from_str(cls, s: str, **kwargs):
        if s != '0:0:0:0:':
            kwargs |= {'hit_sample': HitSample.from_str(s)}

        return cls(**kwargs)

@unique
class CurveType(IntEnum):
    Bezier = 0
    Catmull = 1
    Linear = 2
    Perfect = 3

    #def __str__(self) -> str:
    #    # first char of character
    #    return self.name[0]

class Slider(HitObject):
    def __init__(self, **kwargs) -> None:
        self.curve_type: CurveType = kwargs.pop('curve_type')
        self.curve_points: list[str] = kwargs.pop('curve_points')
        self.slides: int = kwargs.pop('slides')
        self.length: float = kwargs.pop('length')
        self.edge_sounds: list[int] = kwargs.pop('edge_sounds', [])
        self.edge_sets: list[list[int, int]] = kwargs.pop('edge_sets', [])

        super().__init__(**kwargs)

    @classmethod
    def from_str(cls, s: str, **kwargs):
        if len(split := s.split(',')) < 3:
            return

        _curve, _slides, _slen, *_extra = split
        ctype, cpoints = _curve.split('|', 1)

        kwargs |= {
            'curve_type': {
                'B': CurveType.Bezier, 'C': CurveType.Catmull,
                'L': CurveType.Linear, 'P': CurveType.Perfect
            }[ctype],
            'curve_points': cpoints.split('|'),
            'slides': int(_slides),
            'length': float(_slen)
        }

        if _extra:
            assert len(_extra) == 3
            kwargs |= {
                'edge_sounds': [int(x) for x in _extra[0].split('|')],
                'edge_sets': [x.split(':', 1) for x in _extra[1].split('|')],
                'hit_sample': HitSample.from_str(_extra[2])
            }

        return cls(**kwargs)

class Spinner(HitObject):
    def __init__(self, end_time: int, **kwargs) -> None:
        self.end_time = end_time

        super().__init__(**kwargs)

    @classmethod
    def from_str(cls, s, **kwargs):
        if len(split := s.split(',')) != 2:
            return

        if not split[0].isdecimal():
            return

        if split[1] != '0:0:0:0:':
            kwargs |= {'hit_sample': HitSample.from_str(split[1])}

        return cls(end_time=int(split[0]), **kwargs)

class ManiaHold(HitObject):
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

        if not split[0].isdecimal():
            return

        if split[1] != '0:0:0:0:':
            kwargs |= {'hit_sample': HitSample.from_str(split[1])}

        return cls(end_time=int(split[0]), **kwargs)

class Colour:
    def __init__(self, r: int, g: int, b: int) -> None:
        self.r = r
        self.g = g
        self.b = b

    @classmethod
    def from_str(cls, s: str):
        if len(split := s.split(',')) != 3:
            return

        if not all(x.isdecimal() for x in split):
            return

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

class Event:
    def __init__(self, start_time: int) -> None:
        self.start_time = start_time

    @staticmethod
    def from_str(s: str):
        if len(split := s.split(',', 2)) != 3:
            return

        if not split[1].isdecimal():
            return

        # a bit unsafe but w/e

        _type = split[0]

        if _type.isdecimal():
            ev_map = (Background, Video, Break)
            _type = int(_type)
        else:
            ev_map = {'Video': Video, 'Break': Break}

        cls = ev_map[_type]

        return cls.from_str(split[2], start_time=int(split[1]))

class Background(Event):
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

            kwargs |= {'x_offset': int(x_off),
                       'y_offset': int(y_off)}
        elif lsplit != 1:
            raise Exception('Invalid arg count for a background.')

        kwargs |= {
            'filename': split[0].strip('"')
        }

        return cls(**kwargs)

# they're literally identical, since i'm
# still parsing the time for backgrounds lol
Video = type('Video', Background.__bases__, dict(Background.__dict__))

class Break(Event):
    def __init__(self, end_time: int, **kwargs) -> None:
        self.end_time = end_time

        super().__init__(**kwargs)


    @classmethod
    def from_str(cls, s: str, **kwargs):
        if not s.isdecimal():
            return

        return cls(end_time=int(s), **kwargs)

# TODO: storyboards?

class Beatmap:
    def __init__(self) -> None:
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

        """ internal reader use only """
        self._data: Optional[str] = None
        self._offset: Optional[int] = None

    @property
    def data(self) -> str:
        # return all data starting from
        # the internal offset of the reader.
        return self._data[self._offset:]

    @classmethod
    def from_file(cls, filename: str) -> 'Beatmap':
        if not os.path.exists(filename):
            return

        b = cls()

        with open(filename, 'r') as f:
            a: list[str] = []

            # remove any commented-out lines
            for line in f.readlines():
                if not line.startswith('//'):
                    a.append(line)

            b._data = ''.join(a)
            b._offset = 0

        b._parse()
        return b

    def _parse(self) -> None:
        sec_start = self.data.find('\n\n')
        self._offset += len('osu file format v')

        ver_str = self.data[:sec_start - self._offset]
        if not ver_str.isdecimal():
            raise Exception('Invalid file format.')

        self.file_version = int(ver_str)

        sections = {
            'General': self._parse_general,
            'Editor': self._parse_editor,
            'Metadata': self._parse_metadata,
            'Difficulty': self._parse_difficulty,
            'Events': self._parse_events,
            'TimingPoints': self._parse_timing_points,
            'Colours': self._parse_colours,
            'HitObjects': self._parse_hit_objects
        }

        for name, func in sections.items():
            self._parse_section(name, func)

        # TODO
        # parsing file completed, now
        # construct any additional info
        # now that we have everything.
        #self._parse_end()

    def _parse_section(self, name: str, parse_func: Callable) -> None:
        to_find = f'\n\n[{name}]\n'
        offs = self.data.find(to_find)

        if offs == -1:
            # skip any sections not found - the beatmap
            # object will simply have `None` attributes
            # if not parsed from the file.
            return

        self._offset += offs + len(to_find)
        parse_func()

    def _parse_general(self):
        g_end = self.data.find('\n\n')
        separator = _separators['General']

        for line in self.data[:g_end].splitlines():
            key, val = line.split(separator, 1)

            # how should i clean this.. lol

            if key == 'AudioFilename':
                self.audio_filename = val
            elif key == 'AudioLeadIn':
                if not val.isdecimal():
                    continue

                self.audio_leadin = int(val)
            # deprecated
            #elif key == 'AudioHash':
            #    self.audio_hash = val
            elif key == 'PreviewTime':
                if not val.isdecimal():
                    continue

                self.preview_time = int(val)
            elif key == 'Countdown':
                if not val.isdecimal():
                    continue

                self.countdown = int(val)
            elif key == 'SampleSet':
                if val not in ('Normal', 'Soft', 'Drum'):
                    continue

                self.sample_set = {
                    'Normal': SampleSet.NORMAL,
                    'Soft': SampleSet.SOFT,
                    'Drum': SampleSet.DRUM
                }[val]
            elif key == 'StackLeniency':
                if not utils._isdecimal(val, _float=True):
                    continue

                self.stack_leniency = float(val)
            elif key == 'Mode':
                if not val.isdecimal():
                    continue

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
                if val not in ('NoChange', 'Below', 'Above'):
                    continue

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
                if not val.isdecimal():
                    continue

                self.countdown_offset = int(val)
            elif key == 'SpecialStyle':
                self.special_style = val == '1'
            elif key == 'WidescreenStoryboard':
                self.widescreen_storyboard = val == '1'
            elif key == 'SamplesMatchPlaybackRate':
                self.samples_match_playback_rate = val == '1'
            #else:
            #    raise Exception(f'Invalid [General] key {key}')

        self._offset += g_end

    def _parse_editor(self):
        e_end = self.data.find('\n\n')
        separator = _separators['Editor']

        for line in self.data[:e_end].splitlines():
            key, val = line.split(separator, 1)

            if key == 'Bookmarks':
                bookmarks_str = val.split(',')
                if not all(x.isdecimal() for x in bookmarks_str):
                    continue

                self.bookmarks = [int(x) for x in bookmarks_str]
            elif key == 'DistanceSpacing':
                if not utils._isdecimal(val, _float=True):
                    continue

                self.distance_spacing = float(val)
            elif key == 'BeatDivisor':
                if not utils._isdecimal(val, _float=True):
                    continue

                self.beat_divisor = float(val)
            elif key == 'GridSize':
                if not val.isdecimal():
                    continue

                self.grid_size = int(val)
            elif key == 'TimelineZoom':
                if not utils._isdecimal(val, _float=True):
                    continue

                self.timeline_zoom = float(val)
            #else:
            #    raise Exception(f'Invalid [Editor] key {key}')

        self._offset += e_end

    def _parse_metadata(self):
        m_end = self.data.find('\n\n')
        separator = _separators['Metadata']

        for line in self.data[:m_end].splitlines():
            key, val = line.split(separator, 1)

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
                if not val.isdecimal():
                    continue

                self.id = int(val)
            elif key == 'BeatmapSetID':
                if not val.isdecimal():
                    continue

                self.set_id = int(val)
            #else:
            #    raise Exception(f'Invalid [Metadata] key {key}')

        self._offset += m_end

    def _parse_difficulty(self):
        d_end = self.data.find('\n\n')
        separator = _separators['Difficulty']

        for line in self.data[:d_end].splitlines():
            key, val = line.split(separator, 1)

            # all diff params should be float
            if not utils._isdecimal(val, _float=True):
                continue

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
            #else:
            #    raise Exception(f'Invalid [Difficulty] key {key}')

        self._offset += d_end

    def _parse_events(self):
        self.backgrounds = []
        self.videos = []
        self.breaks = []

        # this is actually events, backgrounds,
        # videos, breaks, and storyboards.. lol
        ev_end = self.data.find('\n\n')

        for line in self.data[:ev_end].splitlines():
            ev = Event.from_str(line)

            if isinstance(ev, Background):
                self.backgrounds.append(ev)
            elif isinstance(ev, Video):
                self.videos.append(ev)
            elif isinstance(ev, Break):
                self.breaks.append(ev)
            else:
                breakpoint()

        self._offset += ev_end

    def _parse_timing_points(self):
        self.timing_points = []

        # find the end of the timing points section
        tp_end = self.data.find('\n\n')

        # iterate through each line, parsing
        # the lines into timing point objects.
        for line in self.data[:tp_end].splitlines():
            if not (tp := TimingPoint.from_str(line)):
                utils.printc('Failed to parse timing point?', utils.Ansi.RED)
                continue

            self.timing_points.append(tp)

        self._offset += tp_end

    def _parse_colours(self):
        self.colours = {}

        # find the end of the colours section
        cl_end = self.data.find('\n\n')
        separator = _separators['Colours']

        for line in self.data[:cl_end].splitlines():
            key, val = line.split(separator, 1)

            if not (colour := Colour.from_str(val)):
                continue

            # add to beatmap's colours
            self.colours |= {key: colour}

        self._offset += cl_end

    def _parse_hit_objects(self):
        self.hit_objects = []

        # iterate through each line, parsing
        # the lines into hit object objects
        for line in self.data.splitlines():
            if not (ho := HitObject.from_str(line)):
                utils.printc('Failed to parse hit object?', utils.Ansi.RED)
                continue

            self.hit_objects.append(ho)

        self._offset += len(self.data)
