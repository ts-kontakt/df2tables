#!/usr/bin/python
# coding=utf8
"""
Comnt3 - template content using block-annotated comments

A dead-simple, human-friendly way to manage template regions using
**standard comment syntax** -- no weird symbols, no broken files, no
preprocessing to view your code in a browser.

You can inject actual JavaScript-ready values from Python (not just
quoted strings), or refer to JS functions defined elsewhere -- no
`JSON.parse(...)` round-trip on the frontend, unlike the usual Jinja2
approach. Note: `repr()` is only JS-valid for a narrow subset
(int/float/str/list/dict); use `json.dumps(...)` for anything else.

Supported tag/comment formats:
    HTML/XML:  <!--[tag_name-->  ...  <!--tag_name]-->
    JS/CSS:    /*[tag_name*/    ...  /*tag_name]*/

Tag names may contain letters, digits, '_', '.', ':' and '-'; opening
and closing names must match exactly.

Error model (uniform):
    The scan phase never raises. Tag problems -- missing tags,
    one-sided/malformed pairs, an id used in both comment styles,
    unbalanced duplicate markers, nested/overlapping replacements --
    are localized to the affected tag id:
      * render(): the id is skipped (unbalanced ids still replace their
        complete pairs), a note is printed, and the rest of the render
        proceeds. strict=True raises a single ValueError instead.
      * get_tag_content(): raises, but only for the requested id.
    An id that is never rendered is copied through byte-for-byte.

Rendering guarantee:
    Markers are found only in the original template. The output is built
    once, left to right, from original text and replacement values. Every
    replacement value is opaque: marker-like text inside it is copied
    verbatim and is never treated as another tag. One render() call never
    substitutes into the output of an earlier substitution.

    This is not context-sensitive escaping. Callers must still encode data
    appropriately for its destination (for example json.dumps() plus
    script-safe '<' escaping for JSON in a <script> element).

Behavior notes:
    - A tag id may repeat (same comment style): render() broadcasts its
      value into every occurrence; get_tag_content(tag, instr,
      occurrence=0) picks the 0-based occurrence to read.
    - Mixing html/js styles for one id is rejected -- use two distinct
      ids (the two contexts usually need different quoting).
    - Nested original regions are supported. Selecting both an outer
      and an inner region for replacement is rejected at occurrence
      level; selecting only one of them is safe.
    - write_from_template(..., cache=True) caches text + scan keyed by
      (path, st_mtime_ns) with LRU eviction (max 128); output is
      written atomically (temp file + os.replace).

Author: Tomasz Slugocki
Version: 3.0.0
"""

import os
import re
import tempfile

__all__ = ['render', 'get_tag_content', 'write_from_template',
           'simple_example', 'example', 'NotFoundError']

__version__ = "3.0.0"


class NotFoundError(ValueError):
    """Raised when a tag's opening marker, closing marker, or both are
    missing or malformed. Subclasses ValueError so existing
    `except ValueError` call sites keep working unchanged."""
    pass


_NAME = r'[A-Za-z0-9_.:-]+'

# Matches every raw opening/closing marker of both styles in a single
# pass (group 1: html open, 2: html close, 3: js open, 4: js close).
# Used to detect ids whose raw marker counts don't add up to complete
# pairs -- e.g. three "<!--[date-->" but only two "<!--date]-->".
_ANY_MARKER_RE = re.compile(
    r'<!--\[(' + _NAME + r')-->'
    r'|<!--(' + _NAME + r')\]-->'
    r'|/\*\[(' + _NAME + r')\*/'
    r'|/\*(' + _NAME + r')\]\*/'
)
_IS_OPEN = (True, False, True, False)


def _scan_tags(text):
    """
    One original-template marker pass plus per-tag marker pairing.
    Returns (spans, conflicts, unbalanced):

      spans:      {tag_id: [(block_start, block_end, body_start,
                            body_end, kind), ...]} -- complete pairs,
                   in document order
      conflicts:  set of ids with complete pairs in BOTH comment styles
      unbalanced: {tag_id: (raw_open_count, raw_close_count)} for ids
                  that have at least one complete pair PLUS stray
                  unmatched markers (e.g. 3 openers but 2 closers due
                  to a typo)

    Never raises. A mixed-style or unbalanced id is an authoring error,
    but it is only *reported* (by render/get_tag_content) when that id
    is actually used -- an unrelated problem elsewhere in the template
    must not abort the whole render.
    """
    markers = {}
    id_kind = {}
    conflicts = set()
    raw = {}
    for match in _ANY_MARKER_RE.finditer(text):
        group_index = match.lastindex
        tag_id = match.group(group_index)
        kind = "html" if group_index <= 2 else "js"
        is_open = _IS_OPEN[group_index - 1]
        counts = raw.setdefault(tag_id, [0, 0])
        counts[0 if is_open else 1] += 1
        if id_kind.setdefault(tag_id, kind) != kind:
            conflicts.add(tag_id)
        markers.setdefault(tag_id, []).append(
            (match.start(), match.end(), is_open, kind)
        )

    spans = {}
    unbalanced = {}
    for tag_id, tag_markers in markers.items():
        stack = []
        tag_spans = []
        for start, end, is_open, kind in tag_markers:
            if is_open:
                stack.append((start, end, kind))
                continue
            if not stack:
                continue
            block_start, body_start, _ = stack.pop()
            tag_spans.append(
                (block_start, end, body_start, start, kind)
            )
        if tag_spans:
            spans[tag_id] = sorted(tag_spans)
        open_count, close_count = raw[tag_id]
        if (open_count != close_count or len(tag_spans) != open_count) \
                and tag_spans and tag_id not in conflicts:
            unbalanced[tag_id] = (open_count, close_count)
    return spans, conflicts, unbalanced


def _diagnose_missing(text, tag_id):
    """
    Only called on the error path (tag_id has no complete pair at all).
    Re-derives the specific diagnostics -- which half of the pair is
    missing, how many, whether styles are mixed -- via cheap substring
    counts. Repeated ids are legal since 0.2.0, so this reports the
    opening/closing imbalance instead of the 0.0.1-era "more than one
    start tag" assertion. Always raises.
    """
    html_start, html_end = f"<!--[{tag_id}-->", f"<!--{tag_id}]-->"
    js_start, js_end = f"/*[{tag_id}*/", f"/*{tag_id}]*/"

    hs, he = text.count(html_start), text.count(html_end)
    js, je = text.count(js_start), text.count(js_end)

    if not any((hs, he, js, je)):
        raise NotFoundError(
            f"not found: tag id '{tag_id}' in either html or js form"
        )
    if (hs or he) and (js or je):
        raise NotFoundError(
            f"same tag id in javascript and html is not allowed: '{tag_id}'"
        )

    if hs or he:
        start_cnt, end_cnt, start_tag, end_tag = hs, he, html_start, html_end
    else:
        start_cnt, end_cnt, start_tag, end_tag = js, je, js_start, js_end

    if start_cnt > end_cnt:
        raise NotFoundError(
            f"unbalanced tags for '{tag_id}': {start_cnt} opening "
            f"'{start_tag}' vs {end_cnt} closing '{end_tag}' "
            f"-- {start_cnt - end_cnt} closing tag(s) missing"
        )
    if end_cnt > start_cnt:
        raise NotFoundError(
            f"unbalanced tags for '{tag_id}': {end_cnt} closing "
            f"'{end_tag}' vs {start_cnt} opening '{start_tag}' "
            f"-- {end_cnt - start_cnt} opening tag(s) missing"
        )

    # counts match but the regex still matched nothing --
    # e.g. the closing tag appears before the opening one
    raise NotFoundError(
        f"tags for '{tag_id}' exist but are malformed or out of order"
    )


def _find_overlaps(replacements, spans):
    """
    Return the set of individual spans -- as (tag_id, index) pairs --
    whose replacement would corrupt the output by nesting inside or
    crossing another replaced span. The original-template marker stack
    supports same-style and cross-style nesting. Keeping the granularity
    at the span level means a non-overlapping duplicate occurrence of an
    otherwise-overlapping id is still replaced.
    """
    entries = sorted(
        ((span[2], span[3], span[0], tag_id, idx)
         for tag_id in replacements
         for idx, span in enumerate(spans[tag_id])),
        key=lambda t: t[0],
    )
    overlapping = set()
    cursor = 0
    cursor_owner = None
    for body_start, body_end, block_start, tag_id, idx in entries:
        if block_start < cursor:
            overlapping.add((tag_id, idx))
            if cursor_owner is not None:
                overlapping.add(cursor_owner)
            continue  # rejected entry doesn't extend the cursor
        cursor = body_end
        cursor_owner = (tag_id, idx)
    return overlapping


def _render_spans(instr, repldict, spans, conflicts, unbalanced, strict):
    """
    Substitution pass over an already-scanned document. Split out from
    render() so write_from_template(cache=True) can reuse a cached scan.
    """
    missing = []
    conflicted = []
    replacements = {}
    for key, val in repldict.items():
        if val is None:
            continue  # "leave untouched" -- can't be dangerous, never errors
        if not isinstance(val, str):
            raise TypeError(
                f"replacement value for '{key}' must be a str or None, "
                f"got {type(val).__name__}"
            )
        if key in conflicts:
            conflicted.append(key)  # never broadcast one literal into
            continue                # two different quoting contexts
        if key not in spans:
            missing.append(key)
            continue
        replacements[key] = val

    # Overlapping/nested spans would corrupt the rebuild; drop only the
    # offending occurrences, keep non-overlapping duplicates of the same
    # id. _find_overlaps returns (tag_id, index) pairs, not bare ids.
    overlapping = _find_overlaps(replacements, spans)
    overlap_ids = {tag_id for tag_id, _ in overlapping}

    kept = {}
    for tag_id in replacements:
        kept_spans = [
            span for idx, span in enumerate(spans[tag_id])
            if (tag_id, idx) not in overlapping
        ]
        if kept_spans:
            kept[tag_id] = kept_spans

    # ids with complete pairs PLUS stray unmatched markers that are
    # still being replaced after overlap removal: the complete pairs are
    # rendered, but the author should hear about the strays.
    imbalanced = [k for k in kept if k in unbalanced]

    if strict and (missing or conflicted or imbalanced or overlap_ids):
        problems = []
        if missing:
            problems.append("not found: " + ", ".join(missing))
        if conflicted:
            problems.append(
                "used in both html and js comments: " + ", ".join(conflicted)
            )
        if imbalanced:
            problems.append(
                "unbalanced markers: " + ", ".join(
                    f"'{k}' ({unbalanced[k][0]} opening vs "
                    f"{unbalanced[k][1]} closing)"
                    for k in imbalanced
                )
            )
        if overlap_ids:
            problems.append(
                "nested/overlapping with another replaced tag: "
                + ", ".join(sorted(overlap_ids))
            )
        raise ValueError(f"comnt: tag id(s) {'; '.join(problems)}")

    for key in conflicted:
        print(
            f"comnt: tag id '{key}' exists in both html and js comments; "
            f"skipped (use two distinct ids -- the two contexts usually "
            f"need different quoting)"
        )
    for key in missing:
        try:
            _diagnose_missing(instr, key)
        except Exception as exc:
            print(f"comnt: {exc}")
    for key in imbalanced:
        open_cnt, close_cnt = unbalanced[key]
        print(
            f"comnt: tag id '{key}' has {open_cnt} opening vs "
            f"{close_cnt} closing markers; replaced the "
            f"{len(kept[key])} complete pair(s), stray unmatched "
            f"marker(s) left untouched"
        )
    for key in sorted(overlap_ids):
        total = len(spans[key])
        n_kept = len(kept[key]) if key in kept else 0
        if n_kept:
            print(
                f"comnt: tag id '{key}' has {total - n_kept} of {total} "
                f"occurrence(s) nested inside / crossing another replaced "
                f"tag; skipped those, replaced the remaining {n_kept}"
            )
        else:
            print(
                f"comnt: tag id '{key}' is nested inside or crosses "
                f"another replaced tag; skipped -- replace only the "
                f"outermost one"
            )

    if not kept:
        return instr

    # Flatten every remaining occurrence into one left-to-right rebuild
    # pass. Overlaps were excluded above, so this cannot fail -- the
    # check stays as a defensive sanity net, not the primary path.
    ordered = sorted(
        ((span[2], span[3], span[0], tag_id, replacements[tag_id])
         for tag_id, spans_list in kept.items()
         for span in spans_list),
        key=lambda t: t[0],
    )
    pieces = []
    cursor = 0
    for body_start, body_end, block_start, tag_id, val in ordered:
        if block_start < cursor:
            raise AssertionError(
                f"internal error: '{tag_id}' should have been caught by "
                f"_find_overlaps -- please report this as a comnt bug"
            )
        pieces.append(instr[cursor:body_start])
        pieces.append(val)
        cursor = body_end
    pieces.append(instr[cursor:])
    return "".join(pieces)


def render(instr, repldict, strict=False):
    """
    Replace the body of each tag named in `repldict` with its value.

    - Unknown/typo'd tag ids and ids used in both comment styles:
      reported (printed) and skipped, UNLESS strict=True, in which case
      a single ValueError listing every problem is raised instead.
    - Ids with complete pairs plus stray unmatched markers: the pairs
      are replaced, and a warning about the strays is printed (or
      raised in strict mode).
    - A value of None means "leave this tag's content untouched".
    - If a tag id occurs more than once in `instr` (same comment
      style), its value is broadcast into every occurrence.
    - Values are opaque. Tags are located in the original `instr`, not
      in replacement text, and the output is rebuilt only once.

    Returns the rendered string. Runs in O(len(instr) + total tag
    occurrences) regardless of how many keys are in `repldict`.
    """
    if not isinstance(repldict, dict):
        raise TypeError("repldict must be a dict")
    if not isinstance(instr, str):
        raise TypeError(f"instr must be a str, got {type(instr).__name__}")
    if not repldict:
        return instr
    spans, conflicts, unbalanced = _scan_tags(instr)
    return _render_spans(instr, repldict, spans, conflicts, unbalanced, strict)


def get_tag_content(tag, instr, occurrence=0):
    """Return the current content between the opening/closing tag `tag`
    in `instr`, without modifying anything.

    If `tag` appears more than once, `occurrence` (0-based, in document
    order) picks which copy to read; it defaults to the first one, so
    existing calls on non-repeated tags are unaffected. Reading is
    non-destructive, so stray unmatched markers for the same id do not
    raise here -- complete pairs are still well-defined.
    """
    if not tag or not isinstance(tag, str):
        raise TypeError("'tag' must be a non-empty str")
    if not instr or not isinstance(instr, str):
        raise TypeError("'instr' must be a non-empty str")

    spans, conflicts, _ = _scan_tags(instr)
    if tag in conflicts:
        raise NotFoundError(
            f"same tag id in javascript and html is not allowed: '{tag}'"
        )
    if tag not in spans:
        _diagnose_missing(instr, tag)  # always raises

    occurrences = spans[tag]
    if not (0 <= occurrence < len(occurrences)):
        raise IndexError(
            f"tag '{tag}' has {len(occurrences)} occurrence(s); "
            f"requested occurrence index {occurrence}"
        )

    _, _, body_start, body_end, _ = occurrences[occurrence]
    return instr[body_start:body_end]


def _normpath(path):
    """Canonical identity key for a path: absolute, symlinks resolved,
    case-normalized on platforms where that applies. Not a perfect
    file-identity check (that would need st_dev/st_ino), but it covers
    relative paths, symlinked directories and Windows case differences.
    """
    return os.path.normcase(os.path.realpath(path))


_template_cache = {}
_CACHE_MAX_ENTRIES = 128


def write_from_template(template, newfile, repldict, cache=False, strict=False):
    """
    Render `template` (a path) with `repldict` and write the result to
    `newfile` atomically (temp file + os.replace, so a crash can never
    leave a half-written output file).

    cache=False (default): read and scan the file fresh every call.
    cache=True: keep the file's text AND its tag scan in memory keyed
    by (normcase(realpath(path)), st_mtime_ns), so repeated renders of
    an unchanged on-disk template (e.g. a Flask endpoint hit on every
    request) skip both the disk read and the tag scan -- only the
    substitution pass runs per call. The cache holds at most 128
    templates with LRU eviction, so one extra template never
    invalidates the whole cache.
    """
    if not isinstance(repldict, dict):
        raise TypeError("repldict must be a dict")
    if _normpath(template) == _normpath(newfile):
        raise ValueError("template and newfile must be different paths")

    if cache:
        key = _normpath(template)
        mtime = os.stat(template).st_mtime_ns
        cached = _template_cache.get(key)
        if cached is not None and cached[0] == mtime:
            # LRU: move the hit to the end of the insertion-ordered dict
            _template_cache[key] = _template_cache.pop(key)
            _, instr, spans, conflicts, unbalanced = cached
        else:
            with open(template, encoding="utf-8", newline="") as op_file:
                instr = op_file.read()
            spans, conflicts, unbalanced = _scan_tags(instr)
            if len(_template_cache) >= _CACHE_MAX_ENTRIES:
                _template_cache.pop(next(iter(_template_cache)))  # evict LRU
            _template_cache[key] = (mtime, instr, spans, conflicts, unbalanced)
        replaced = _render_spans(
            instr, repldict, spans, conflicts, unbalanced, strict)
    else:
        with open(template, encoding="utf-8", newline="") as op_file:
            instr = op_file.read()
        replaced = render(instr, repldict, strict=strict)

    tmp_dir = os.path.dirname(newfile) or "."
    tmp_prefix = os.path.basename(newfile) + "."
    fd, tmp = tempfile.mkstemp(prefix=tmp_prefix, suffix=".tmp", dir=tmp_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as outfile:
            outfile.write(replaced)
        os.replace(tmp, newfile)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return True


def _open_file(filename):
    import subprocess
    import sys
    if sys.platform.startswith("win"):
        os.startfile(filename)
    else:
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        subprocess.call([opener, filename])


def example():
    content = """
    <!DOCTYPE html>
    <html>
       <head>
          <title>
             Example  comnt rendered page
            </title>

       </head>
       <body> <h3>
           <!--[title-->
             Welcome to our site!
          <!--title]--></h3>
          <!--[content-->
          <p>
             This is placeholder content that shows in the browser.
          </p>
          <!--content]-->
          <code id="data-display" style=
             "background-color: rgb(245, 245, 245); padding: 10px; border: 1px solid rgb(221, 221, 221);">
             </code>
          <code id="user-display" style=
             "background-color: rgb(245, 245, 245); padding: 10px; border: 1px solid rgb(221, 221, 221);">
             </code>
          <script>
             // A Python list and a Python dict, injected as JS values
             const data = /*[data_arr*/ [0, 1]
             /*data_arr]*/;
             const user = /*[user_obj*/ {name: "Ada", age: 37}
             /*user_obj]*/;
             document.addEventListener('DOMContentLoaded', function() {
                 document.getElementById('data-display').textContent =
                     JSON.stringify(data, null, 2);
                 document.getElementById('user-display').textContent =
                     JSON.stringify(user, null, 2);
             });
          </script>
       </body>
    </html>
    """

    outstr = render(
        content,
        {
            "title": "Example rendered python object",
            "content": "<p>Below python range rendered as javascript variable</p>",
            "data_arr": repr(list(range(10))),  # a Python list -> JS array
            "user_obj": repr(
                {"name": "Ada", "age": 37, "roles": ["admin", "editor"]}
            ),  # a Python dict -> JS object (single quotes are valid JS)
        },
    )
    file_name = os.path.join(os.getcwd(), "comnt_test.html")
    with open(file_name, "w", encoding="utf8") as outfile:
        outfile.write(outstr)
    _open_file(file_name)


def simple_example():
    import json

    content = """
    <!DOCTYPE html>
    <p id="title"> </p>
    <div id="data_arr"></div>
    <script>
    const title = /*[title*/
        "Example title"
    /*title]*/;
    const data = /*[data_arr*/
        [0, 1]
    /*data_arr]*/;

      document.getElementById("data_arr").textContent = JSON.stringify(data);
      document.getElementById("title").textContent = title;
    </script>
    """
    outstr = render(
        content,
        {
            "title": json.dumps("Example rendered python object"),
            "data_arr": json.dumps(list(range(10))),
        },
    )
    file_name = os.path.join(os.getcwd(), "comnt_simple.html")
    with open(file_name, "w", encoding="utf8") as outfile:
        outfile.write(outstr)
    _open_file(file_name)


if __name__ == "__main__":
    # simple_example()
    example()
