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

* install_custom_file_merger(merger, description=None)

Register a function that can do a three-way merge for a specific file

"""


__version__ = (0, 0, 1)


import importlib
import logging
import os
from typing import List, Optional, Tuple, Iterator


DEFAULT_CONFLICT_LEN = 7


Chunks = List[bytes]
Lines = List[bytes]


_custom_file_mergers = []


def iter_custom_file_mergers() -> Iterator["PerFileMerger"]:
    return iter(_custom_file_mergers)


def iter_plugins():
    from smartmerge.plugins import __path__ as paths
    for path in paths:
        for entry in os.scandir(path):
            if entry.is_dir() and os.path.exists(entry.path + '/__init__.py'):
                yield entry.name


def load_plugins():
    for name in iter_plugins():
        importlib.import_module('smartmerge.plugins.' + name)


def chunks_to_lines(chunks: Chunks) -> Lines:
    """Re-split chunks into simple lines.

    Each entry in the result should contain a single newline at the end. Except
    for the last entry which may not have a final newline. If chunks is already
    a simple list of lines, we return it directly.

    :param chunks: An list/tuple of strings. If chunks is already a list of
        lines, then we will return it as-is.
    :return: A list of strings.
    """
    # Optimize for a very common case when chunks are already lines
    last_no_newline = False
    for chunk in chunks:
        if last_no_newline:
            # Only the last chunk is allowed to not have a trailing newline
            # Getting here means the last chunk didn't have a newline, and we
            # have a chunk following it
            break
        if not chunk:
            # Empty strings are never valid lines
            break
        elif b'\n' in chunk[:-1]:
            # This chunk has an extra '\n', so we will have to split it
            break
        elif chunk[-1:] != b'\n':
            # This chunk does not have a trailing newline
            last_no_newline = True
    else:
        # All of the lines (but possibly the last) have a single newline at the
        # end of the string.
        # For the last one, we allow it to not have a trailing newline, but it
        # is not allowed to be an empty string.
        return chunks

    # These aren't simple lines, just join and split again.
    return b''.join(chunks).splitlines(True)


def find_3way_file_mergers(path: str,) -> Optional["PerFileMerger"]:

    for file_merger_kls in _custom_file_mergers:
        if not file_merger_kls.available():
            logging.debug('Skipping unavailable file merger: %r', file_merger_kls)
            continue
        if file_merger_kls.can_handle(path):
            yield file_merger_kls()


class PerFileMerger(object):
    """PerFileMerger objects are used by plugins extending merge.

    See ``smartmerge.plugins.news`` for an example concrete
    class.
    """

    @classmethod
    def git_patterns(cls):
        raise NotImplementedError(cls)

    @classmethod
    def available(cls):
        return True

    @classmethod
    def can_handle(cls, path: str) -> bool:
        raise NotImplementedError(cls.can_handle)

    def use_breezy_config(self, config) -> None:
        """Use the specified breezy configuration."""
        raise NotImplementedError(self.use_breezy_config)

    def merge_chunks(
            self, this_chunks: Optional[Chunks], other_chunks: Optional[Chunks], base_chunks: Optional[Chunks]) -> Tuple[str, Optional[Chunks]]:
        """Attempt to merge the contents of a single file.

        Returns: A tuple of (status, chunks), where status is one of
            'not_applicable', 'success', 'conflicted', or 'delete'.  If status
            is 'success' or 'conflicted', then chunks should be an iterable of
            strings for the new file contents.
        """
        return ('not applicable', None)


class PerLineFileMerger(PerFileMerger):
    """PerFileMerger implementation that works on lines.
    """

    def merge_lines(self, this_lines: Lines, other_lines: Lines, base_lines: Lines, *, conflictlen: int = DEFAULT_CONFLICT_LEN) -> Tuple[str, Lines]:
        """Attempt to merge the contents of a single file.

        Returns: A tuple of (status, lines), where status is one of
            'not_applicable', 'success', 'conflicted', or 'delete'.  If status
            is 'success' or 'conflicted', then linesshould be an iterable of
            strings for the new file contents.
        """
        raise NotImplementedError(self.merge_lines)

    def merge_chunks(self, this_chunks: Chunks, other_chunks: Chunks, base_chunks: Chunks) -> Tuple[str, Chunks]:
        """Attempt to merge the contents of a single file.

        Returns: A tuple of (status, chunks), where status is one of
            'not_applicable', 'success', 'conflicted', or 'delete'.  If status
            is 'success' or 'conflicted', then chunks should be an iterable of
            strings for the new file contents.
        """
        this_lines = chunks_to_lines(this_chunks) if this_chunks is not None else None
        other_lines = chunks_to_lines(other_chunks) if other_chunks is not None else None
        base_lines = chunks_to_lines(base_chunks) if base_chunks is not None else None
        return self.merge_lines(this_lines, other_lines, base_lines)


class DefaultPerFileMerger(PerLineFileMerger):

    @classmethod
    def can_handle(cls, path) -> bool:
        # Maybe not quite true - what about non-text files?
        return True

    def merge_lines(self, this_lines, other_lines, base_lines, *, conflictlen=DEFAULT_CONFLICT_LEN):
        from merge3 import Merge3
        import patiencediff
        start_marker = b"!START OF MERGE CONFLICT!" + b"I HOPE THIS IS UNIQUE"
        m3 = Merge3(
            base_lines, this_lines, other_lines,
            sequence_matcher=patiencediff.PatienceSequenceMatcher)
        lines = list(m3.merge_lines(start_marker=start_marker))
        result = 'success'
        for i, line in enumerate(lines):
            if line.startswith(start_marker):
                lines[i] = b'<' * conflictlen + b'\n'
                result = 'conflicted'

        return result, lines


def install_custom_file_merger(merger_kls):
    """Register a new custom merger.

    Args:
      merger_kls: Merger class
      description: Optional description
    """
    _custom_file_mergers.append(merger_kls)


def smartmerge(path: str, base: Chunks, this: Chunks, other: Chunks, *, conflictlen: int = DEFAULT_CONFLICT_LEN) -> Tuple[str, Chunks]:
    per_file_mergers = find_3way_file_mergers(path)
    for per_file_merger in per_file_mergers:
        logging.info('Trying per-file-merger %r for %s', per_file_merger, path)
        result, chunks = per_file_merger.merge_chunks(base, this, other)
        if result != 'not_applicable':
            break
    else:
        logging.debug('Using default three-way merge')
        per_file_merger = DefaultPerFileMerger()
        result, chunks = per_file_merger.merge_chunks(base, this, other)
    return result, chunks


def run_per_file_merger(merger_kls):
    import argparse
    import sys
    parser = argparse.ArgumentParser()
    parser.add_argument('this', str)
    parser.add_argument('other', str)
    parser.add_argument('base', str)
    args = parser.parse_args()

    merger = merger_kls()
    with open(args.this, 'rb') as f:
        this = f.read()
    with open(args.other, 'rb') as f:
        other = f.read()
    with open(args.base, 'rb') as f:
        base = f.read()
    sys.stdout.writelines(merger.merge_chunks(this, other, base))
    return 0
