#!/usr/bin/python3
# encoding: utf-8

from setuptools import setup

setup(name="smartmerge",
      description="Three way merge with domain specific knowledge",
      version="0.0.1",
      maintainer="Breezy Developers",
      maintainer_email="team@breezy-vcs.org",
      license="GNU GPLv2 or later",
      url="https://www.breezy-vcs.org/",
      packages=['smartmerge'],
      test_suite='smartmerge.tests.test_suite',
      install_requires=['merge3'],
      classifiers=[
          'Development Status :: 4 - Beta',
          'License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)',  # noqa
          'Programming Language :: Python :: 3.3',
          'Programming Language :: Python :: 3.4',
          'Programming Language :: Python :: 3.5',
          'Programming Language :: Python :: 3.6',
          'Programming Language :: Python :: Implementation :: CPython',
          'Programming Language :: Python :: Implementation :: PyPy',
          'Operating System :: POSIX',
      ])
