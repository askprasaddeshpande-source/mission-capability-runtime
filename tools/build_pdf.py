#!/usr/bin/env python3
"""Build the publication PDF from the final manuscript (Markdown -> HTML -> headless Chrome/Edge).

Requirements: Python 3, the `markdown` package, and Chrome or Edge on PATH or in the usual Windows locations.
No network, SAP, MCP or model access is used.

Usage: python tools/build_pdf.py <manuscript.md> <out.pdf>
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

import markdown

CSS = """
@page { size: A4; margin: 18mm 16mm 18mm 16mm; }
body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 10pt; line-height: 1.42; color: #111; }
h1 { font-size: 17pt; margin: 1.3em 0 .4em; page-break-after: avoid; border-bottom: 1px solid #999; padding-bottom: 2px; }
h1:first-of-type { font-size: 21pt; border: none; }
h2 { font-size: 13pt; margin: 1.1em 0 .3em; page-break-after: avoid; }
h3 { font-size: 11pt; page-break-after: avoid; }
table { border-collapse: collapse; width: 100%; margin: .6em 0; font-size: 8.6pt; page-break-inside: auto; }
tr { page-break-inside: avoid; }
th, td { border: 1px solid #999; padding: 3px 5px; vertical-align: top; }
th { background: #e9edf2; text-align: left; }
code { font-family: Consolas, 'Courier New', monospace; font-size: 8.6pt; background: #f3f3f3; padding: 0 2px; word-break: break-all; }
pre { background: #f3f3f3; padding: 6px; overflow-x: auto; font-size: 8.6pt; }
blockquote { border-left: 4px solid #14365d; margin: .8em 0; padding: .2em .9em; background: #eef3f9; font-weight: 600; }
img { max-width: 100%; page-break-inside: avoid; }
hr { border: none; border-top: 1px solid #bbb; margin: 1em 0; }
"""


def find_browser():
    for name in ("chrome", "google-chrome", "msedge", "chromium"):
        p = shutil.which(name)
        if p:
            return p
    for p in (r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"):
        if os.path.exists(p):
            return p
    raise SystemExit("No Chrome/Edge found")


def main(md_path, pdf_path):
    md_path = os.path.abspath(md_path)
    text = open(md_path, encoding="utf-8").read()
    title = re.search(r"^# (.+)$", text, re.M).group(1).strip()
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])
    base = os.path.dirname(md_path)
    # make relative image paths absolute file URLs
    body = re.sub(r'src="(?!https?:|file:)([^"]+)"', lambda m: 'src="file:///' + os.path.abspath(os.path.join(base, m.group(1))).replace("\\", "/") + '"', body)
    html = f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>{title}</title><meta name='author' content='Prasad Deshpande'><style>{CSS}</style></head><body>{body}</body></html>"
    tmp = tempfile.mkdtemp()
    hp = os.path.join(tmp, "m.html")
    open(hp, "w", encoding="utf-8").write(html)
    out = os.path.abspath(pdf_path)
    cmd = [find_browser(), "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={out}", "file:///" + hp.replace("\\", "/")]
    subprocess.run(cmd, check=True, capture_output=True, timeout=180)
    shutil.rmtree(tmp, ignore_errors=True)
    try:  # add document metadata (Chrome does not set Author/Subject/Keywords)
        from pypdf import PdfReader, PdfWriter
        r = PdfReader(out)
        w = PdfWriter()
        for pg in r.pages:
            w.add_page(pg)
        w.add_metadata({"/Title": title, "/Author": "Prasad Deshpande", "/Subject": "Mission-Capability Runtime (MCR) R1.9 external-review candidate R3",
                        "/Keywords": "agentic AI; Mission-Capability Runtime; MCWS; MCP; deterministic authority; outcome validation",
                        "/Creator": "tools/build_pdf.py (Markdown -> HTML -> headless Chrome)"})
        with open(out, "wb") as f:
            w.write(f)
    except ImportError:
        print("pypdf not installed; metadata left as produced by the browser")
    print("wrote", out, os.path.getsize(out), "bytes")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2])
