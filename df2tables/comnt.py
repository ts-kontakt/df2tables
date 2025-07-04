#!/usr/bin/python
# coding=utf8
from sys import exc_info
"""
Comnt - template content using block-annotated comments

A dead-simple, human-friendly way to manage template regions using
**standard comment syntax** — no weird symbols, no broken files, no preprocessing
to view your code in a browser.

One huge practical benefit: you can inject actual JavaScript-ready values from Python—
not just strings or you can refer to javascript functions defined elsewhere.
That means you don’t need to wrap your data in quotes and then call
`JSON.parse(...)` on the frontend, like you often do with Jinja2.

Supported tag/comment Formats:
    HTML/XML style:
        <!--[tag_name-->
        Content to be replaced
        <!--tag_name]-->

    JavaScript/CSS style:
        /*[tag_name*/
       const arr_to_change = [0,1]
        /*tag_name]*/

Tag Format Rules:
    - Opening tag: Comment start + '[' + tag_name + Comment continuation
    - Closing tag: Comment start + tag_name + ']' + Comment end
    - Tag names must match exactly between opening and closing tags

Author: [Tomasz Sługocki]
Version: 0.0.1
"""

__all__ = ['render', 'write_from_template', 'simple_example', 'example']


class NotFoundError(Exception):
    pass


def _render_block(text, tag_id, val=None):
    assert isinstance(text, str) and isinstance(tag_id, str)
    assert len(text) > len(tag_id)

    assert val is None or isinstance(val, str)

    def get_tags(text, tag_id, ext):
        assert ext in ("html", "js")
        start, end = ("/*", "*/") if ext == "js" else ("<!--", "-->")
        start_tag_js, start_tag_html = f"/*[{tag_id}*/", f"<!--[{tag_id}-->"
        if start_tag_js in text and start_tag_html in text:
            raise AssertionError(f"same tag id in javascript and html is not allowed")
        start_tag = "".join((start, "[", tag_id, end))
        end_tag = "".join((start, tag_id, "]", end))
        start_cnt = len(text.split(start_tag)) - 1
        end_cnt = len(text.split(end_tag)) - 1
        if not start_cnt and not end_cnt:
            raise ValueError(f"not found tags {start_tag} {end_tag}, ext:{ext}")
        if not start_cnt:
            raise NotFoundError(f"start tag not found in form: '{start_tag}'")
        if not end_cnt:
            raise NotFoundError(f"end tag not found in form: '{end_tag}'")
        if start_cnt > 1:
            raise AssertionError(f"more than one start tag: '{start_tag}'")
        if end_cnt > 1:
            raise AssertionError(f"more than one end tag: '{end_tag}'")
        return start_tag, end_tag

    start_tag, end_tag = None, None
    errs = []
    for ext in ["js", "html"]:
        try:
            start_tag, end_tag = get_tags(text, tag_id, ext)
        except ValueError:
            errs.append(repr(exc_info()[1]))
    if not start_tag:
        raise ValueError(f"Errors happened: {''.join(errs)}")

    start_idx = text.find(start_tag)
    end_idx = text.find(end_tag)
    prefix = text[:start_idx + len(start_tag)]
    suffix = text[end_idx:]

    if val is None:  # empty strings are ok
        old_val = text[start_idx + len(start_tag):end_idx]
        return old_val
    return "\n".join((prefix, val, suffix))


def get_tag_content(tag, instr):
    assert len(instr) > len(tag) and tag + instr
    return _render_block(instr, tag, None)


def render(instr, repldict):
    for key, val in repldict.items():
        try:
            instr = _render_block(instr, key, val)
        except ValueError:
            print(exc_info()[1])

    return instr


def write_from_template(template, newfile, repldict):
    assert isinstance(repldict, dict)
    assert template != newfile
    with open(template, encoding="utf-8") as op_file:
        instr = op_file.read()
    replaced = render(instr, repldict)
    with open(newfile, "w", encoding="utf8") as outfile:
        outfile.write(replaced)
    return True


def example():
    import os
    import subprocess
    import sys

    def open_file(filename):
        if sys.platform.startswith("win"):
            os.startfile(filename)
        else:
            opener = "open" if sys.platform == "darwin" else "xdg-open"
            subprocess.call([opener, filename])

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
          <script>
             // Example data array for
             const data = /*[data_arr*/ [0, 1]
             /*data_arr]*/;

             document.addEventListener('DOMContentLoaded', function() {
                 // Display data array in paragraph (like Python's repr)
                 const dataDisplay = document.getElementById('data-display');
                 dataDisplay.textContent = JSON.stringify(data, null, 2);
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
            "data_arr": repr(list(range(10))),  # dont even need json here
            # , 'none_existing' : '0'
        },
    )
    file_name = os.path.join(os.getcwd(), "comnt_test.html")
    with open(file_name, "w", encoding="utf8") as outfile:
        outfile.write(outstr)
    open_file(file_name)


def simple_example():
    import json
    import os
    import subprocess
    import sys

    def open_file(filename):
        if sys.platform.startswith("win"):
            os.startfile(filename)
        else:
            opener = "open" if sys.platform == "darwin" else "xdg-open"
            subprocess.call([opener, filename])

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
    open_file(file_name)


if __name__ == "__main__":
    # simple_example()
    example()
