Smartmerge
==========

Smartmerge is a Python library and command-line tool that can do file
format-aware three way merges.

It primarily does this by detecting file formats and invoking other tools.

Currently supported file formats:

 * GNU ChangeLog
 * debian/changelog
 * po files
 * Bazaar-style NEWS files

Usage in Git
~~~~~~~~~~~~

To install, simply run:

   $ smartmerge --install --git

This defines smartmerge as a custom merge driver inside of git, by adding the following
to your ~/.gitconfig::

    [merge "smartmerge"]
      name = smartmerge
      driver = smartmerge --git %A %B %O --target=%P

It then enables the driver for relevant files by registering it for use
for specific files::

    debian/changelog  merge=smartmerge
