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

import argparse
import logging
import sys

from . import smartmerge, load_plugins, iter_custom_file_mergers


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument('--git', action='store_true')
    parser.add_argument('--list', '-l', action='store_true')
    parser.add_argument('--install', action='store_true')
    parser.add_argument('--target', type=str)
    parser.add_argument('this', type=str, nargs='?')
    parser.add_argument('other', type=str, nargs='?')
    parser.add_argument('base', type=str, nargs='?')
    parser.add_argument('--conflictlen', type=int, default=7)

    args = parser.parse_args()

    logging.basicConfig(format='%(message)s', level=logging.INFO)

    load_plugins()

    if args.list:
        for per_file_merger in iter_custom_file_mergers():
            logging.info('%r - %s', per_file_merger, per_file_merger.summary)
        return 0

    if args.install:
        if not args.git:
            logging.warning(
                '--git not specified, but assuming that is what you meant')
            args.git = True
        # TODO(jelmer): Update ~/.gitconfig to add:
        # [merge "smartmerge"]
        # name = smartmerge
        # driver = smartmerge --git %A %O %B --conflictlen=%L --target=%P
        # TODO(jelmer): Update $XDG_HOME_DIR/.git/attributes to add for each custom merger:
        # * merge=smartmerge
        for per_file_merger in iter_custom_file_mergers():
            for pattern in per_file_merger.git_patterns():
                print(f'{pattern} merge=smartmerge')
        raise NotImplementedError

    if not args.base or not args.this or not args.other:
        parser.print_usage()
        return 1

    def read_file(n):
        if n == '':
            return []
        with open(n, 'rb') as f:
            return f.readlines()

    this = read_file(args.this)
    base = read_file(args.base)
    other = read_file(args.other)

    result, merged_chunks = smartmerge(
        args.target or args.this, this, other, base, conflictlen=args.conflictlen)

    if result == 'conflicted':
        exit_code = 1
    elif result == 'success':
        exit_code = 0
    elif result == 'delete':
        exit_code = 0
    elif result == 'not_applicable':
        exit_code = 0
    else:
        raise ValueError(result)

    if args.git:
        if result in ('conflicted', 'success'):
            with open(args.this, 'wb') as f:
                f.writelines(merged_chunks)
        elif result == 'delete':
            os.unlink(args.this)
    else:
        sys.stdout.writelines(merged_lines)
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
