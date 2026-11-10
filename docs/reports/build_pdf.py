"""Markdown report -> self-contained HTML -> PDF, printed by headless Edge (Windows).

    python docs/reports/build_pdf.py docs/reports/<report>.md docs/reports/<report>.pdf    # needs the `markdown` package"""
import base64
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import markdown

src, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
body = markdown.markdown(src.read_text(encoding="utf-8"), extensions=["tables"])


def inline(m):   # images as data URIs so the HTML stands alone
    p = (src.parent / m.group(1)).resolve()
    return f'src="data:image/png;base64,{base64.b64encode(p.read_bytes()).decode()}"'


body = re.sub(r'src="([^"]+\.png)"', inline, body)
title = re.search(r"<h1>(.*?)</h1>", body).group(1)
html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{title}</title><style>
@page {{ size: A4; margin: 15mm 15mm 16mm; }}
body {{ font-family: "Segoe UI", Arial, sans-serif; font-size: 10pt; line-height: 1.4; color: #1a1a19; }}
h1 {{ font-size: 17pt; margin: 0 0 2pt; }}
h2 {{ font-size: 12.5pt; margin: 13pt 0 4pt; padding-bottom: 2pt; border-bottom: 1px solid #c3c2b7; break-after: avoid; }}
h3 {{ font-size: 10.5pt; margin: 9pt 0 3pt; break-after: avoid; }}
p {{ margin: 4pt 0; }} ul, ol {{ margin: 4pt 0; padding-left: 16pt; }} li {{ margin: 1.5pt 0; }}
table {{ border-collapse: collapse; width: 100%; margin: 6pt 0; font-size: 9pt; break-inside: avoid; }}
th, td {{ border: 1px solid #c3c2b7; padding: 2.5pt 5pt; text-align: left; vertical-align: top; }}
th {{ background: #f0efe9; }}
img {{ max-width: 100%; margin: 3pt 0 1pt; break-inside: avoid; }}
code {{ font-family: Consolas, monospace; font-size: 9pt; }}
em {{ color: #52514e; }}
</style></head><body>{body}</body></html>"""
tmp = out.with_suffix(".html")
tmp.write_text(html, encoding="utf-8")
edge = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
out.unlink(missing_ok=True)
subprocess.run([edge, "--headless", "--disable-gpu", "--no-pdf-header-footer", f"--user-data-dir={tempfile.mkdtemp()}",
                f"--print-to-pdf={out}", tmp.as_uri()], check=True, capture_output=True, timeout=120)
for _ in range(60):   # Edge writes the file just after it returns
    if out.exists() and out.stat().st_size > 0:
        break
    time.sleep(0.5)
tmp.unlink()
print(out, out.stat().st_size, "bytes")
