# -*- coding: utf-8 -*-

"""\
A package of abstractions I find myself constantly rewriting in different apps..

I enjoy writing things myself from a relatively low level, so while some of
these classes are simply inferior to using a 'real' lightweight framework, I
find that I learn much much quicker doing things on my own, and that I also
love the feeling of understanding exactly how everything works in my projects.

Source: https://github.com/cmyui/cmyui_pkg

:copyright: (c) 2020 cmyui
:license: MIT, see LICENSE for details.
"""

__title__ = 'cmyui'
__author__ = 'cmyui'
__license__ = 'MIT'
__copyright__ = 'Copyright 2020 cmyui'
__version__ = '1.4.7'

from .logging import *
from .mysql import *
from .postgres import *
from .utils import *
from .version import *
from .web import *
