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

(these are the only currently implemented)

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
