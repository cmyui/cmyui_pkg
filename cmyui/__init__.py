# -*- coding: utf-8 -*-

"""\
Tools I find myself constantly rebuilding and reusing.

I enjoy writing things myself from a relatively low level, so while some of
these classes are simply inferior to using a 'real' lightweight framework, I
find that I learn much much quicker doing things on my own, and that I also
love the feeling of understanding exactly how everything works in my projects.

Note that I do releases on this package quite frequently and for relatively
small changes; this is because I often think of new ideas when writing other
projects and think they would be a nice addition to the library, but want to
use them immediately in my own code.

Source: https://github.com/cmyui/cmyui_pkg

:copyright: (c) 2020 cmyui
:license: MIT, see LICENSE for details.
"""

__title__ = 'cmyui'
__author__ = 'cmyui'
__license__ = 'MIT'
__copyright__ = 'Copyright 2020 cmyui'
__version__ = '1.7.3'

from .logging import *
from .mysql import *
from .utils import *
from .version import *
from .web import *
