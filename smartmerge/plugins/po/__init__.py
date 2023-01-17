# Copyright (C) 2011 Canonical Ltd
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

__doc__ = """Merge hook for ``.po`` files.

To enable this plugin, add a section to your branch.conf or location.conf
like::

    [/home/user/code/bzr]
    po_merge.pot_dirs = po,doc/po4a/po

The ``po_merge.pot_dirs`` config option takes a list of directories that can
contain ``.po`` files, separated by commas (if several directories are
needed). Each directory should contain a single ``.pot`` file.

The ``po_merge.command`` is the command whose output is used as the result of
the merge. It defaults to::

   msgmerge -N "{other}" "{pot_file}" -C "{this}" -o "{result}"

where:

* ``this`` is the ``.po`` file content before the merge in the current branch,
* ``other`` is the ``.po`` file content in the branch merged from,
* ``pot_file`` is the path to the ``.pot`` file corresponding to the ``.po``
  file being merged.

If conflicts occur in a ``.pot`` file during a given merge, the ``.po`` files
will use the ``.pot`` file present in tree before the merge. If this doesn't
suit your needs, you should can disable the plugin during the merge with::

  bzr merge <usual merge args> -Opo_merge.po_dirs=

This will allow you to resolve the conflicts in the ``.pot`` file and then
merge the ``.po`` files again with::

  bzr remerge po/*.po doc/po4a/po/*.po

"""

from smartmerge import (
    install_custom_file_merger,
    PerLineFileMerger,
    DEFAULT_CONFLICT_LEN,
    )


import fnmatch
import logging
import os
import shlex
import shutil
import subprocess
import tempfile


logger = logging.getLogger('smartmerge.po')


DEFAULT_PO_MERGE_COMMAND = 'msgmerge -N "{other}" "{pot_file}" -C "{this}" -o "{result}"'


try:
    from breezy import config as breezy_config
except ModuleNotFoundError:
    pass
else:
    command_option = breezy_config.Option(
        'po_merge.command',
        default=DEFAULT_PO_MERGE_COMMAND,
        help='''\
    Command used to create a conflict-free .po file during merge.

    The following parameters are provided by the hook:
    ``this`` is the ``.po`` file content before the merge in the current branch,
    ``other`` is the ``.po`` file content in the branch merged from,
    ``pot_file`` is the path to the ``.pot`` file corresponding to the ``.po``
    file being merged.
    ``result`` is the path where ``msgmerge`` will output its result. The hook will
    use the content of this file to produce the resulting ``.po`` file.

    All paths are absolute.
    ''')

    breezy_config.option_registry.register(command_option)

    po_dirs_option = breezy_config.ListOption(
        'po_merge.po_dirs', default='po,debian/po',
        help='List of dirs containing .po files that the hook applies to.')

    breezy_config.option_registry.register(po_dirs_option)

    po_glob_option = breezy_config.Option(
        'po_merge.po_glob', default='*.po',
        help='Glob matching all ``.po`` files in one of ``po_merge.po_dirs``.')

    breezy_config.option_registry.register(po_glob_option)

    pot_glob_option = breezy_config.Option(
        'po_merge.pot_glob', default='*.pot',
        help='Glob matching the ``.pot`` file in one of ``po_merge.po_dirs``.')

    breezy_config.option_registry.register(pot_glob_option)


class PoMerger(PerLineFileMerger):
    """Merge .po files."""

    summary = ".po file merge"

    config_key = 'po'

    po_dirs = ['po', 'debian/po']
    po_glob = '*.po'
    pot_glob = '*.pot'
    command = DEFAULT_PO_MERGE_COMMAND

    @classmethod
    def git_patterns(cls):
        return [
            os.path.join(po_dir, cls.po_glob)
            for po_dir in cls.po_dirs]

    @classmethod
    def use_breezy_config(cls, config):
        # config options are cached locally until config files are (see
        # http://pad.lv/832042)

        cls.conf = config
        # Which dirs are targeted by the hook
        cls.po_dirs = self.conf.get('po_merge.po_dirs')
        # Which files are targeted by the hook
        cls.po_glob = self.conf.get('po_merge.po_glob')
        # Which .pot file should be used
        cls.pot_glob = self.conf.get('po_merge.pot_glob')
        cls.command = self.conf.get('po_merge.command', expand=False)

    def __init__(self):
        super().__init__()
        # file_matches() will set the following for merge_text()
        self.pot_file_abspath = None
        logger.debug('PoMerger created')

    @classmethod
    def can_handle(cls, po_path):
        """Return True if merge_chunks should be called on this file."""
        if not cls.po_dirs or not cls.command:
            # Return early if there is no options defined
            return False
        po_dir = None
        for po_dir in cls.po_dirs:
            glob = os.path.join(po_dir, cls.po_glob)
            if fnmatch.fnmatch(po_path, glob):
                logger.debug('po %s matches: %s' % (po_path, glob))
                break
        else:
            logger.debug('PoMerger did not match for %s and %s'
                         % (cls.po_dirs, cls.po_glob))
            return False
        # Do we have the corresponding .pot file
        for path, file_class, kind, entry in self.merger.this_tree.list_files(
                from_dir=po_dir, recursive=False):
            if fnmatch.fnmatch(path, self.pot_glob):
                relpath = os.path.join(po_dir, path)
                self.pot_file_abspath = self.merger.this_tree.abspath(relpath)
                # FIXME: I can't find an easy way to know if the .pot file has
                # conflicts *during* the merge itself. So either the actual
                # content on disk is fine and msgmerge will work OR it's not
                # and it will fail. Conversely, either the result is ok for the
                # user and he's happy OR the user needs to resolve the
                # conflicts in the .pot file and use remerge.
                # -- vila 2011-11-24
                logger.debug('will msgmerge %s using %s'
                             % (po_path, self.pot_file_abspath))
                return True
        else:
            return False

    def _invoke(self, command):
        logger.debug('Will msgmerge: %s' % (command,))
        # We use only absolute paths so we don't care about the cwd
        proc = subprocess.Popen(shlex.split(command),
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                stdin=subprocess.PIPE)
        out, err = proc.communicate()
        return proc.returncode, out, err

    def merge_lines(self, this_lines, other_lines, base_lines, *, conflictlen: int = DEFAULT_CONFLICT_LEN):
        """Calls msgmerge when .po files conflict.

        This requires a valid .pot file to reconcile both sides.
        """
        # Create tmp files with the 'this' and 'other' content
        tmpdir = tempfile.mkdtemp(prefix='po_merge')
        env = {}
        env['this'] = os.path.join(tmpdir, 'this')
        env['other'] = os.path.join(tmpdir, 'other')
        env['result'] = os.path.join(tmpdir, 'result')
        env['pot_file'] = self.pot_file_abspath
        try:
            with open(env['this'], 'wb') as f:
                f.writelines(this_lines)
            with open(env['other'], 'wb') as f:
                f.writelines(other_lines)
            command = self.conf.expand_options(self.command, env)
            retcode, out, err = self._invoke(command)
            with open(env['result'], 'rb') as f:
                # FIXME: To avoid the list() construct below which means the
                # whole 'result' file is kept in memory, there may be a way to
                # use an iterator that will close the file when it's done, but
                # there is still the issue of removing the tmp dir...
                # -- vila 2011-11-24
                return 'success', list(f.readlines())
        finally:
            shutil.rmtree(tmpdir)
        return 'not applicable', []


install_custom_file_merger(PoMerger)


def load_tests(loader, basic_tests, pattern):
    testmod_names = [
        'tests',
        ]
    basic_tests.addTest(loader.loadTestsFromModuleNames(
        ["%s.%s" % (__name__, tmn) for tmn in testmod_names]))
    return basic_tests
