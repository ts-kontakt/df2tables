#!/usr/bin/python
# coding=utf8
"""
Comnt - template content using block-annotated comments

A dead-simple way to manage template regions using standard comment
syntax -- no preprocessing needed to view the file in a browser.

You can inject real JavaScript-ready values from Python (not just
quoted strings), so there's no JSON.parse(...) round-trip on the
frontend like the usual Jinja2 approach requires.

Supported tag/comment formats:
    HTML/XML:  <!--[tag_id-->  ...  <!--tag_id]-->
    JS/CSS:    /*[tag_id*/    ...  /*tag_id]*/

Rules:
    - Opening/closing tag ids must match exactly.
    - A tag id must use ONE comment style consistently (mixing html
      and js comments for the same id is an error).
    - A tag id MAY repeat (same style): render() broadcasts its value
      into every occurrence; get_tag_content(..., occurrence=N) reads
      one specific occurrence (default: the first).
    - A value of None in repldict means "leave this tag untouched".

Deliberately small: plain string.find() scanning, no regex, no file
cache, no overlap/nesting detection. Built for templates with a
handful of tags. If you outgrow that, you want a real template
engine, not comnt.

Author: Tomasz Slugocki
"""

import os
import tempfile

__all__ = ['render', 'get_tag_content', 'write_from_template',
           'simple_example', 'example', 'NotFoundError']

__version__ = "0.0.2"


class NotFoundError(ValueError):
    """A tag's markers are missing, one-sided, mixed between comment
    styles, or don't pair up cleanly. Subclasses ValueError so old
    `except ValueError` call sites keep working unchanged."""
    pass


def _find_spans(text, start_tag, end_tag):
    """All non-overlapping (block_start, body_start, body_end, block_end)
    spans for one already-known start/end tag pair, left to right."""
    spans = []
    pos = 0
    while True:
        s = text.find(start_tag, pos)
        if s == -1:
            break
        body_start = s + len(start_tag)
        e = text.find(end_tag, body_start)
        if e == -1:
            break
        spans.append((s, body_start, e, e + len(end_tag)))
        pos = e + len(end_tag)
    return spans


def _scan(text, tag_id):
    """Locate every complete pair for tag_id. Returns (style, spans).
    Raises NotFoundError if the tag is absent, mixed between comment
    styles, or its opening/closing markers don't pair up cleanly."""
    found = {}
    for style, cstart, cend in (("html", "<!--", "-->"), ("js", "/*", "*/")):
        start_tag = f"{cstart}[{tag_id}{cend}"
        end_tag = f"{cstart}{tag_id}]{cend}"
        start_cnt, end_cnt = text.count(start_tag), text.count(end_tag)
        if start_cnt or end_cnt:
            found[style] = (start_tag, end_tag, start_cnt, end_cnt)

    if not found:
        raise NotFoundError(
            f"tag '{tag_id}' not found (checked both html and js comment forms)"
        )
    if len(found) > 1:
        raise NotFoundError(
            f"tag '{tag_id}' used in both html and js comments -- "
            f"not allowed, use two distinct ids"
        )

    style = next(iter(found))
    start_tag, end_tag, start_cnt, end_cnt = found[style]
    spans = _find_spans(text, start_tag, end_tag)
    if start_cnt != end_cnt or len(spans) != start_cnt:
        raise NotFoundError(
            f"tag '{tag_id}' has unbalanced or malformed markers: "
            f"{start_cnt}x '{start_tag}' vs {end_cnt}x '{end_tag}' "
            f"({len(spans)} complete pair(s) found)"
        )
    return style, spans


def get_tag_content(tag_id, instr, occurrence=0):
    """Return the current content of tag_id without modifying anything.
    occurrence (0-based) picks which copy to read if the tag repeats."""
    if not isinstance(tag_id, str) or not tag_id:
        raise TypeError("'tag_id' must be a non-empty str")
    if not isinstance(instr, str) or not instr:
        raise TypeError("'instr' must be a non-empty str")
    _, spans = _scan(instr, tag_id)
    if not (0 <= occurrence < len(spans)):
        raise IndexError(
            f"tag '{tag_id}' has {len(spans)} occurrence(s); "
            f"requested occurrence index {occurrence}"
        )
    _, body_start, body_end, _ = spans[occurrence]
    return instr[body_start:body_end]


def render(instr, repldict, strict=False):
    """Replace the body of each tag named in repldict with its value.

    - val is None -> tag left untouched (does not error).
    - Missing / mixed-style / unbalanced tag ids: printed and skipped,
      or raised immediately if strict=True.
    - A repeated tag id gets its value broadcast into every occurrence.
    """
    if not isinstance(repldict, dict):
        raise TypeError("repldict must be a dict")
    if not isinstance(instr, str):
        raise TypeError(f"instr must be a str, got {type(instr).__name__}")

    for tag_id, val in repldict.items():
        if val is None:
            continue
        if not isinstance(val, str):
            raise TypeError(
                f"replacement for '{tag_id}' must be a str or None, "
                f"got {type(val).__name__}"
            )
        try:
            _, spans = _scan(instr, tag_id)
        except NotFoundError as exc:
            if strict:
                raise
            print(f"comnt: {exc}")
            continue
        # right-to-left so earlier offsets already computed for `instr`
        # stay valid as we rewrite it
        for _, body_start, body_end, _ in reversed(spans):
            instr = instr[:body_start] + val + instr[body_end:]

    return instr


def write_from_template(template, newfile, repldict, strict=False):
    """Render `template` (a path) with repldict and write the result to
    `newfile`. Written atomically (temp file + os.replace) so a crash
    mid-write can never leave a corrupted/half-written file. newline=""
    on both read and write preserves the file's original line endings
    (e.g. CRLF) instead of silently normalizing them."""
    if not isinstance(repldict, dict):
        raise TypeError("repldict must be a dict")
    if os.path.normcase(os.path.realpath(template)) \
            == os.path.normcase(os.path.realpath(newfile)):
        raise ValueError("template and newfile must be different paths")

    with open(template, encoding="utf-8", newline="") as op_file:
        instr = op_file.read()
    replaced = render(instr, repldict, strict=strict)

    tmp_dir = os.path.dirname(newfile) or "."
    fd, tmp_path = tempfile.mkstemp(
        prefix=os.path.basename(newfile) + ".", suffix=".tmp", dir=tmp_dir
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as outfile:
            outfile.write(replaced)
        os.replace(tmp_path, newfile)
    except BaseException:
        try:
            os.unlink(tmp_path)
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
       <head><!--[title1--><title> </title><!--title1]--></head>
       <body>
          <h3><!--[title--> Welcome to our site! <!--title]--></h3>
          <!--[content-->
          <p>This is placeholder content.</p>
          <!--content]-->
          <code id="data-display"></code>
          <script>
             const data = /*[data_arr*/ [0, 1] /*data_arr]*/;
             document.addEventListener('DOMContentLoaded', function () {
                 document.getElementById('data-display').textContent =
                     JSON.stringify(data, null, 2);
             });
          </script>
       </body>
    </html>
    """
    outstr = render(
        content,
        {
            # "title" appears twice above -- both get the same value
            "title": "Example rendered python object",
            "content": "<p>Below: a python range rendered as a js array</p>",
            "data_arr": repr(list(range(10))),  # repr is JS-valid for a plain list
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
    <p id="title"></p>
    <div id="data_arr"></div>
    <script>
    const title = /*[title*/ "Example title" /*title]*/;
    const data = /*[data_arr*/ [0, 1] /*data_arr]*/;
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