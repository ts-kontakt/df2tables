#!/usr/bin/python
# coding=utf8
"""
Comnt - template content using block-annotated comments

Template regions are marked with standard comment syntax, so the template
stays a valid file you can open in a browser as-is, placeholder included.

    HTML/XML:  <!--[tag_id-->  ...  <!--tag_id]-->
    JS/CSS:    /*[tag_id*/    ...  /*tag_id]*/

Python values go in as JavaScript source -- no JSON.parse() round trip:

    const data = /*[data*/ [0, 1] /*data]*/;      <- js_value([1, 2, 3])

Rules
    - ids are ASCII identifiers: a letter or _ first, then letters, digits
      and _ (the same rule as Python/Jinja2 names, but ASCII only).
      Opening and closing id must match.
    - An id may repeat (same style): render() writes its value into every
      occurrence; get_tag_content(..., occurrence=N) reads one of them.
    - An id uses ONE comment style (use two ids for html and js).
    - Tags may nest. Replacing an outer tag replaces everything inside it,
      so a value given for an inner tag as well is ignored (and reported).
    - A value of None leaves that tag untouched.
    - Markers stay in the output: a rendered file is again a template.

Error model
    Problems are detected per id and only matter for ids you actually pass:
    unknown id, id in both comment styles, unbalanced or misordered markers,
    inner tag swallowed by an outer one. A broken id is skipped, never
    guessed. render() then issues one warnings.warn() listing everything;
    strict=True raises a single ValueError instead. get_tag_content()
    raises NotFoundError.

Guarantees
    Markers are searched only in the template, in one linear pass, and the
    output is built once, left to right. Values are opaque: marker-like text
    inside a value is copied verbatim and never treated as a tag.

Escaping
    Comnt does not escape. Use js_value() for JS (json.dumps plus '<'
    escaping, so '</script>' in data cannot break out of the element) and
    html.escape() for HTML text.

Web apps
    render_file() returns a string and caches the scanned template (up to
    16 files, validated by mtime and size, thread-safe), so a large
    template is not rescanned on every request:

        @app.get("/")
        def index():
            return comnt.render_file("page.html", {"data": comnt.js_value(rows)})

Author: Tomasz Slugocki
Version: 2.0.0
"""

import functools
import json
import os
import re
import secrets
import stat
import tempfile
import warnings
import webbrowser
from pathlib import Path

__all__ = ['render', 'render_file', 'write_from_template', 'get_tag_content',
           'js_value', 'clear_cache', 'example', 'NotFoundError']

__version__ = "2.0.0"


class NotFoundError(ValueError):
    """A tag is missing, used in both comment styles, or its markers don't
    pair up cleanly. Subclasses ValueError."""


_NAME = r'[A-Za-z_][A-Za-z0-9_]*'
_NAME_RE = re.compile(_NAME)

# One pattern for every marker. The name of the group that matched tells
# which one it was: h/j = html/js comment, o/c = opening/closing marker.
_MARKER = re.compile(
    r'<!--(?:\[(?P<ho>' + _NAME + r')|(?P<hc>' + _NAME + r')\])-->'
    r'|/\*(?:\[(?P<jo>' + _NAME + r')|(?P<jc>' + _NAME + r')\])\*/'
)


def _scan(text):
    """Pair up all markers of `text` in one linear pass.

    Returns (spans, conflicts, counts):
      spans:     {tag_id: [(block_start, body_start, body_end, block_end)]}
                 complete pairs in document order; markers of one id are
                 paired like brackets, so same-id nesting works
      conflicts: ids that occur in both html and js comments
      counts:    {tag_id: (opening, closing)} raw marker counts

    Never raises; problems are reported only for ids that get used.
    """
    spans, counts, kinds, stacks, conflicts = {}, {}, {}, {}, set()
    for m in _MARKER.finditer(text):
        group = m.lastgroup
        tag_id = m.group(group)
        kind, is_open = group[0], group[1] == 'o'
        count = counts.setdefault(tag_id, [0, 0])
        count[0 if is_open else 1] += 1
        if kinds.setdefault(tag_id, kind) != kind:
            conflicts.add(tag_id)
        stack = stacks.setdefault(tag_id, [])
        if is_open:
            stack.append((m.start(), m.end()))
        elif stack:
            block_start, body_start = stack.pop()
            spans.setdefault(tag_id, []).append(
                (block_start, body_start, m.start(), m.end()))
    for pairs in spans.values():
        pairs.sort()
    return spans, conflicts, {k: tuple(v) for k, v in counts.items()}


def _problem(tag_id, scan):
    """Why `tag_id` can't be used, or None if it is fine."""
    spans, conflicts, counts = scan
    if tag_id in conflicts:
        return f"'{tag_id}' is used in both html and js comments (use two ids)"
    opening, closing = counts.get(tag_id, (0, 0))
    if not (opening or closing):
        hint = "" if _NAME_RE.fullmatch(tag_id) else \
            " (ids must start with a letter or _ and use only letters, digits and _)"
        return f"'{tag_id}' not found{hint}"
    pairs = len(spans.get(tag_id, ()))
    if pairs != opening or opening != closing:
        return (f"'{tag_id}' has unbalanced or misordered markers "
                f"({opening} opening, {closing} closing, "
                f"{pairs} complete pair(s))")
    return None


def _render_scanned(text, repldict, scan, strict):
    """Substitution over an already scanned template (shared by render()
    and render_file(), so a cached scan can be reused)."""
    spans = scan[0]
    problems, work = [], []
    for tag_id, val in repldict.items():
        if val is None:
            continue
        if not isinstance(val, str):
            raise TypeError(
                f"replacement for '{tag_id}' must be a str or None, "
                f"got {type(val).__name__}")
        problem = _problem(tag_id, scan)
        if problem:
            problems.append(problem)
        else:
            work.extend((*s, tag_id, val) for s in spans[tag_id])

    work.sort(key=lambda w: w[0])           # outer / leftmost first
    pieces, cursor, owner, ignored = [], 0, None, {}
    for block_start, body_start, body_end, block_end, tag_id, val in work:
        if block_start < cursor:            # starts inside a replaced region
            if tag_id != owner:             # (an id inside itself is no news)
                key = (tag_id, block_end > cursor)      # True: crosses it
                ignored[key] = ignored.get(key, 0) + 1
            continue
        pieces.append(text[cursor:body_start])
        pieces.append(val)
        cursor, owner = body_end, tag_id
    pieces.append(text[cursor:])

    for (tag_id, crossing), count in ignored.items():
        what = ("crosses another replaced tag (misnested markers)" if crossing
                else "lies inside another replaced tag")
        problems.append(f"'{tag_id}' {what}, its value was ignored in "
                        f"{count} of {len(spans[tag_id])} occurrence(s)")
    if problems:
        message = "comnt: " + "; ".join(problems)
        if strict:
            raise ValueError(message)
        warnings.warn(message, stacklevel=3)
    return "".join(pieces)


def render(instr, repldict, strict=False):
    """Replace the body of each tag named in `repldict` with its value.

    A repeated id gets the value in every occurrence; None leaves the tag
    untouched. Broken or unknown ids are skipped and reported (see the
    module docstring); strict=True raises ValueError instead.
    """
    if not isinstance(repldict, dict):
        raise TypeError("repldict must be a dict")
    if not isinstance(instr, str):
        raise TypeError(f"instr must be a str, got {type(instr).__name__}")
    if not repldict:
        return instr
    return _render_scanned(instr, repldict, _scan(instr), strict)


def get_tag_content(tag, instr, occurrence=0):
    """Return the current content of `tag` without modifying anything.
    `occurrence` (0-based) picks which copy to read if the id repeats."""
    if not isinstance(tag, str) or not tag:
        raise TypeError("'tag' must be a non-empty str")
    if not isinstance(instr, str):
        raise TypeError(f"'instr' must be a str, got {type(instr).__name__}")
    scan = _scan(instr)
    problem = _problem(tag, scan)
    if problem:
        raise NotFoundError(problem)
    pairs = scan[0][tag]
    if not 0 <= occurrence < len(pairs):
        raise IndexError(
            f"tag '{tag}' has {len(pairs)} occurrence(s); "
            f"requested occurrence index {occurrence}")
    _, body_start, body_end, _ = pairs[occurrence]
    return instr[body_start:body_end]


def js_value(obj):
    """Python object -> JavaScript literal that is safe inside <script>."""
    return json.dumps(obj).replace("<", "\\u003c")


def _normpath(path):
    return os.path.normcase(os.path.realpath(path))


@functools.lru_cache(maxsize=16)
def _load(path, mtime_ns, size):
    # mtime and size are not used in the body: they are part of the cache
    # key, so an edited file is simply a cache miss.
    with open(path, encoding="utf-8", newline="") as op_file:
        text = op_file.read()
    return text, _scan(text)


def clear_cache():
    """Forget all cached templates (mostly useful in tests)."""
    _load.cache_clear()


def render_file(template, repldict, strict=False):
    """render() for a template file, returning a str. The text and its scan
    are cached until the file's mtime or size changes."""
    if not isinstance(repldict, dict):
        raise TypeError("repldict must be a dict")
    path = os.path.abspath(template)
    st = os.stat(path)
    text, scan = _load(path, st.st_mtime_ns, st.st_size)
    return _render_scanned(text, repldict, scan, strict)


def write_from_template(template, newfile, repldict, strict=False):
    """Render the file `template` and write the result to `newfile`.
    Written atomically (temp file + os.replace), so a crash can never leave
    a half-written file. newline="" keeps the original line endings.
    A new file gets the usual umask-based permissions; an existing `newfile`
    keeps its permissions."""
    newfile = os.fspath(newfile)
    if _normpath(template) == _normpath(newfile):
        raise ValueError("template and newfile must be different paths")
    replaced = render_file(template, repldict, strict)
    try:
        mode = stat.S_IMODE(os.stat(newfile).st_mode)
    except FileNotFoundError:
        mode = None
    tmp = f"{newfile}.{secrets.token_hex(4)}.tmp"
    try:
        with open(tmp, "x", encoding="utf-8", newline="") as outfile:
            if mode is not None:
                os.chmod(tmp, mode)         # before any data is written
            outfile.write(replaced)
        os.replace(tmp, newfile)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return True


def example():
    """Render a small demo page and open it in the default browser."""
    template = """<!DOCTYPE html>
<html>
  <head><meta charset="utf-8"><title>comnt example</title></head>
  <body>
    <h1><!--[title-->Welcome to our site!<!--title]--></h1>
    <!--[content--><p>This is placeholder content.</p><!--content]-->
    <pre id="out"></pre>
    <p><small><!--[title-->Welcome to our site!<!--title]--></small></p>
    <script>
      // A Python dict, injected as a JS value
      const data = /*[data*/ {"name": "Ada"} /*data]*/;
      document.getElementById("out").textContent = JSON.stringify(data, null, 2);
    </script>
  </body>
</html>
"""
    page = render(template, {
        "title": "Example rendered from Python",
        "content": "<p>Below: a Python dict rendered as a JavaScript object.</p>",
        "data": js_value({"name": "Ada", "age": 37, "roles": ["admin", "editor"]}),
    })
    path = os.path.join(tempfile.gettempdir(), "comnt_example.html")
    with open(path, "w", encoding="utf-8") as outfile:
        outfile.write(page)
    webbrowser.open(Path(path).as_uri())


if __name__ == "__main__":
    example()
