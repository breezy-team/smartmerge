# Copyright (C) 2010 Canonical Ltd
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

__doc__ = """Merge hook for GNU-format ChangeLog files

To enable this plugin, add a section to your locations.conf
like::

    [/home/user/proj]
    changelog_merge_files = ChangeLog

Or add an entry to your branch.conf like::

    changelog_merge_files = ChangeLog

The changelog_merge_files config option takes a list of file names (not paths),
separated by commas.  (This is unlike the news_merge plugin, which matches
paths.)  e.g. the above config examples would match both
``src/foolib/ChangeLog`` and ``docs/ChangeLog``.

The algorithm used to merge the changes can be summarised as:

 * new entries added to the top of OTHER are emitted first
 * all other additions, deletions and edits from THIS and OTHER are preserved
 * edits (e.g. to fix typos) at the top of OTHER are hard to distinguish from
   adding and deleting independent entries; the algorithm tries to guess which
   based on how similar the old and new entries are.

Caveats
-------

Most changes can be merged, but conflicts are possible if the plugin finds
edits at the top of OTHER to entries that have been deleted (or also edited) by
THIS.  In that case the plugin gives up and bzr's default merge logic will be
used.

No effort is made to deduplicate entries added by both sides.

The results depend on the choice of the 'base' version, so it might give
strange results if there is a criss-cross merge.
"""

import difflib
import logging
import posixpath

from smartmerge import install_custom_file_merger, PerLineFileMerger, run_per_file_merger

from merge3 import Merge3


logger = logging.getLogger('smartmerge.changelog_merge')


def changelog_entries(lines):
    """Return a list of changelog entries.

    :param lines: lines of a changelog file.
    :returns: list of entries.  Each entry is a tuple of lines.
    """
    entries = []
    for line in lines:
        if line[0] not in (' ', '\t', '\n'):
            # new entry
            entries.append([line])
        else:
            try:
                entry = entries[-1]
            except IndexError:
                # Cope with leading blank lines.
                entries.append([])
                entry = entries[-1]
            entry.append(line)
    return list(map(tuple, entries))


def entries_to_lines(entries):
    """Turn a list of entries into a flat iterable of lines."""
    for entry in entries:
        for line in entry:
            yield line


class GnuChangeLogMerger(PerLineFileMerger):
    """Merge GNU-format ChangeLog files."""

    summary = 'GNU ChangeLog file merge'

    config_key = "gnu_changelog"

    @classmethod
    def git_patterns(cls):
        return ['ChangeLog']

    @classmethod
    def can_handle(self, path):
        return path == 'ChangeLog'

    def merge_text(self, params):
        """Merge changelog changes.

         * new entries from other will float to the top
         * edits to older entries are preserved
        """
        # Transform files into lists of changelog entries
        this_entries = changelog_entries(params.this_lines)
        other_entries = changelog_entries(params.other_lines)
        base_entries = changelog_entries(params.base_lines)
        try:
            result_entries = merge_entries(
                base_entries, this_entries, other_entries)
        except EntryConflict:
            # XXX: generating a nice conflict file would be better
            return 'not_applicable', None
        # Transform the merged elements back into real blocks of lines.
        return 'success', entries_to_lines(result_entries)


class EntryConflict(Exception):
    pass


def default_guess_edits(new_entries, deleted_entries, entry_as_str=b''.join):
    """Default implementation of guess_edits param of merge_entries.

    This algorithm does O(N^2 * logN) SequenceMatcher.ratio() calls, which is
    pretty bad, but it shouldn't be used very often.
    """
    deleted_entries_as_strs = list(map(entry_as_str, deleted_entries))
    new_entries_as_strs = list(map(entry_as_str, new_entries))
    result_new = list(new_entries)
    result_deleted = list(deleted_entries)
    result_edits = []
    sm = difflib.SequenceMatcher()
    CUTOFF = 0.8
    while True:
        best = None
        best_score = CUTOFF
        # Compare each new entry with each old entry to find the best match
        for new_entry_as_str in new_entries_as_strs:
            sm.set_seq1(new_entry_as_str)
            for old_entry_as_str in deleted_entries_as_strs:
                sm.set_seq2(old_entry_as_str)
                score = sm.ratio()
                if score > best_score:
                    best = new_entry_as_str, old_entry_as_str
                    best_score = score
        if best is not None:
            # Add the best match to the list of edits, and remove it from the
            # the list of new/old entries.  Also remove it from the new/old
            # lists for the next round.
            del_index = deleted_entries_as_strs.index(best[1])
            new_index = new_entries_as_strs.index(best[0])
            result_edits.append(
                (result_deleted[del_index], result_new[new_index]))
            del deleted_entries_as_strs[del_index], result_deleted[del_index]
            del new_entries_as_strs[new_index], result_new[new_index]
        else:
            # No match better than CUTOFF exists in the remaining new and old
            # entries.
            break
    return result_new, result_deleted, result_edits


def merge_entries(base_entries, this_entries, other_entries,
                  guess_edits=default_guess_edits):
    """Merge changelog given base, this, and other versions."""
    m3 = Merge3(base_entries, this_entries, other_entries, allow_objects=True)
    result_entries = []
    at_top = True
    for group in m3.merge_groups():
        logger.debug('merge group:\n%r', group)
        group_kind = group[0]
        if group_kind == 'conflict':
            _, base, this, other = group
            # Find additions
            new_in_other = [
                entry for entry in other if entry not in base]
            # Find deletions
            deleted_in_other = [
                entry for entry in base if entry not in other]
            if at_top and deleted_in_other:
                # Magic!  Compare deletions and additions to try spot edits
                new_in_other, deleted_in_other, edits_in_other = guess_edits(
                    new_in_other, deleted_in_other)
            else:
                # Changes not made at the top are always preserved as is, no
                # need to try distinguish edits from adds and deletes.
                edits_in_other = []
            logger.debug('at_top: %r', at_top)
            logger.debug('new_in_other: %r', new_in_other)
            logger.debug('deleted_in_other: %r', deleted_in_other)
            logger.debug('edits_in_other: %r', edits_in_other)
            # Apply deletes and edits
            updated_this = [
                entry for entry in this if entry not in deleted_in_other]
            for old_entry, new_entry in edits_in_other:
                try:
                    index = updated_this.index(old_entry)
                except ValueError:
                    # edited entry no longer present in this!  Just give up and
                    # declare a conflict.
                    raise EntryConflict()
                updated_this[index] = new_entry
            logger.debug('updated_this: %r', updated_this)
            if at_top:
                # Float new entries from other to the top
                result_entries = new_in_other + result_entries
            else:
                result_entries.extend(new_in_other)
            result_entries.extend(updated_this)
        else:  # unchanged, same, a, or b.
            lines = group[1]
            result_entries.extend(lines)
        at_top = False
    return result_entries

# Put most of the code in a separate module that we lazy-import to keep the
# overhead of this plugin as minimal as possible.


install_custom_file_merger(GnuChangeLogMerger)


def load_tests(loader, basic_tests, pattern):
    testmod_names = [
        'tests',
        ]
    basic_tests.addTest(loader.loadTestsFromModuleNames(
        ["%s.%s" % (__name__, tmn) for tmn in testmod_names]))
    return basic_tests


if __name__ == '__main__':
    import sys
    sys.exit(run_per_file_merger(GnuChangeLogMerger))
