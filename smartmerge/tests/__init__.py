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
import unittest


from .. import iter_plugins


def test_suite():
    names = [
        ]
    module_names = [__name__ + '.test_' + name for name in names]
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    for plugin_name in iter_plugins():
        m = importlib.import_module(
            'smartmerge.plugins.' + plugin_name + '.tests')
        load_tests = getattr(m, 'load_tests')
        suite = unittest.TestSuite()
        load_tests(loader, suite, None)
    suite.addTests(loader.loadTestsFromNames(module_names))
    return suite
