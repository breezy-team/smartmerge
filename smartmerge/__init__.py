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

"""Smart three way merging of files.

Plugins can register four different kinds of file-specific handlers:

* install_custom_merger(merger, description=None)

Register a function that can do a three-way merge for a specific file

"""

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


class AbstractPerFileMerger(object):
    """PerFileMerger objects are used by plugins extending merge.

    See ``smartmerge.plugins.news_merge.news_merge`` for an example concrete
    class.

    :ivar merger: The Merge3Merger performing the merge.
    """

    def merge_contents(self, merge_params):
        """Attempt to merge the contents of a single file.

        :param merge_params: A breezy.merge.MergeFileHookParams
        :return: A tuple of (status, chunks), where status is one of
            'not_applicable', 'success', 'conflicted', or 'delete'.  If status
            is 'success' or 'conflicted', then chunks should be an iterable of
            strings for the new file contents.
        """
        return ('not applicable', None)


class PerFileMerger(AbstractPerFileMerger):
    """Merge individual files when self.file_matches returns True.

    This class is intended to be subclassed.  The file_matches and
    merge_matching methods should be overridden with concrete implementations.
    """

    def file_matches(self, params):
        """Return True if merge_matching should be called on this file.

        Only called with merges of plain files with no clear winner.

        Subclasses must override this.
        """
        raise NotImplementedError(self.file_matches)

    def merge_contents(self, params):
        """Merge the contents of a single file."""
        # Check whether this custom merge logic should be used.
        if (
            # OTHER is a straight winner, rely on default merge.
            params.winner == 'other' or
            # THIS and OTHER aren't both files.
            not params.is_file_merge() or
            # The filename doesn't match
                not self.file_matches(params)):
            return 'not_applicable', None
        return self.merge_matching(params)

    def merge_matching(self, params):
        """Merge the contents of a single file that has matched the criteria
        in PerFileMerger.merge_contents (is a conflict, is a file,
        self.file_matches is True).

        Subclasses must override this.
        """
        raise NotImplementedError(self.merge_matching)


def install_custom_merger(merger_kls, description=None):
    """Register a new custom merger.

    Args:
      merger_kls: Merger class
      description: Optional description
    """
    _custom_mergers.append((merger_kls, description))


def smartmerge(base, this, other):
    return default_line_based_merger(base, this, other)
