Smartmerge
==========

Smartmerge is a Python library and command-line tool that can do file
format-aware three way merges.

It primarily does this by detecting file formats and invoking other tools.

Usage in Git
~~~~~~~~~~~~

To define smartmerge as a custom merge driver inside of git, add the following
to your ~/.gitconfig::

    [merge "smartmerge"]
      name = smartmerge
      driver = smartmerge --git %A %O %B %P

You can then enable it globally or on a per project/file basis using
gitattributes, e.g.::

   *  merge=smartmerge

Implementation
~~~~~~~~~~~~~~

Smartmerge will invoke various file type-specific functions, which can be
registered by plugins.

If no applicable merger can be found, it will fall back to simple line-based
3-way merge.

Custom Mergers
--------------

These are mergers that take a base, this and other fulltext and simply apply
the merge.

Filters
-------

Transformations for files that make them more applicable for merging; good examples
are gzipping/gunzipping or other forms of encoding.

Normalization
-------------

In some situations, normalizing files makes conflicts less common. This is only possible where
a known normalization format exists. For example, go code should always be formatted with
gofmt.

Regenerate from source
----------------------

Some files are completely generated from other files in the same tree. In that
case, rather than merging the resulting file - merge the inputs and then regenerate it.
