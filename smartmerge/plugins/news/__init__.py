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

__doc__ = """Merge hook for bzr's NEWS file.

To enable this plugin, add a section to your branch.conf or location.conf
like::

    [/home/user/code/bzr]
    news_merge_files = NEWS

The news_merge_files config option takes a list of file paths, separated by
commas.

Limitations:

* if there's a conflict in more than just bullet points, this doesn't yet know
  how to resolve that, so bzr will fallback to the default line-based merge.
"""

from smartmerge import PerLineFileMerger, install_custom_file_merger

import merge3


def simple_parse_lines(lines):
    """Same as simple_parse, but takes an iterable of strs rather than a single
    str.
    """
    return simple_parse(''.join(lines))


def simple_parse(content):
    """Returns blocks, where each block is a 2-tuple (kind, text).

    :kind: one of 'heading', 'release', 'section', 'empty' or 'text'.
    :text: a str, including newlines.
    """
    blocks = content.split('\n\n')
    for block in blocks:
        if block.startswith('###'):
            # First line is ###...: Top heading
            yield 'heading', block
            continue
        last_line = block.rsplit('\n', 1)[-1]
        if last_line.startswith('###'):
            # last line is ###...: 2nd-level heading
            yield 'release', block
        elif last_line.startswith('***'):
            # last line is ***...: 3rd-level heading
            yield 'section', block
        elif block.startswith('* '):
            # bullet
            yield 'bullet', block
        elif block.strip() == '':
            # empty
            yield 'empty', block
        else:
            # plain text
            yield 'text', block


class NewsMerger(PerLineFileMerger):
    """Merge bzr NEWS files."""

    summary = "NEWS file merge"

    config_key = "news"

    @classmethod
    def can_handle(cls, path):
        # TODO(jelmer)
        return False

    @classmethod
    def git_patterns(cls):
        # TODO(jelmer)
        return []

    def merge_text(self, this_lines, other_lines, base_lines):
        """Perform a simple 3-way merge of a bzr NEWS file.

        Each section of a bzr NEWS file is essentially an ordered set of bullet
        points, so we can simply take a set of bullet points, determine which
        bullets to add and which to remove, sort, and reserialize.
        """
        # Transform the different versions of the NEWS file into a bunch of
        # text lines where each line matches one part of the overall
        # structure, e.g. a heading or bullet.
        this_lines = list(simple_parse_lines(params.this_lines))
        other_lines = list(simple_parse_lines(params.other_lines))
        base_lines = list(simple_parse_lines(params.base_lines))
        m3 = merge3.Merge3(base_lines, this_lines, other_lines,
                           allow_objects=True)
        result_chunks = []
        for group in m3.merge_groups():
            if group[0] == 'conflict':
                _, base, a, b = group
                # Are all the conflicting lines bullets?  If so, we can merge
                # this.
                for line_set in [base, a, b]:
                    for line in line_set:
                        if line[0] != 'bullet':
                            # Something else :(
                            # Maybe the default merge can cope.
                            return 'not_applicable', None
                # Calculate additions and deletions.
                new_in_a = set(a).difference(base)
                new_in_b = set(b).difference(base)
                all_new = new_in_a.union(new_in_b)
                deleted_in_a = set(base).difference(a)
                deleted_in_b = set(base).difference(b)
                # Combine into the final set of bullet points.
                final = all_new.difference(deleted_in_a).difference(
                    deleted_in_b)
                # Sort, and emit.
                final = sorted(final, key=sort_key)
                result_chunks.extend(final)
            else:
                result_chunks.extend(group[1])
        # Transform the merged elements back into real blocks of lines.
        result_lines = '\n\n'.join(chunk[1] for chunk in result_chunks)
        return 'success', result_lines


def sort_key(chunk):
    return chunk[1].replace('`', '').lower()


install_custom_file_merger(NewsMerger)


def test_suite():
    from . import tests
    return tests.test_suite()
