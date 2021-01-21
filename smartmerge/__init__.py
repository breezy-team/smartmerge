# Copyright (C) 2020 Breezy Developers
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA


import importlib
import os


_custom_mergers = []


def iter_plugins():
    from smartmerge.plugins import __path__ as paths
    for path in paths:
        for entry in os.scandir(path):
            if entry.is_dir() and os.path.exists(entry.path + '/__init__.py'):
                yield entry.name


def load_plugins():
    for name in iter_plugins():
        importlib.import_module('smartmerge.plugins.' + name)


def default_line_based_merger(base, this, other):
    from merge3 import Merge3
    m3 = Merge3(base, this, other)
    return m3.merge_lines()


def install_custom_merger(merger, description=None):
    """Register a new custom merger.

    Args:
      merger: Merger function
      description: Optional description
    """
    _custom_mergers.append((merger, description))


def smartmerge(base, this, other):
    return default_line_based_merger(base, this, other)
