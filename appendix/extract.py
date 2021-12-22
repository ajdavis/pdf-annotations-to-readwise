import os as _os
import subprocess as _subprocess
import tempfile as _tempfile
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from bs4 import BeautifulSoup


def _extract_to_html(source_pdf_path: str, dst: str):
    dst_dir, dst_filename = _os.path.split(dst)
    script = f"""
set appPath to quoted form of "/System/Volumes/Data/Applications/PDF Expert.app"

set pdfPath to quoted form of "{source_pdf_path}"

do shell script "open -a " & appPath & " " & pdfPath

delay 2

tell application "System Events"
  tell process "PDF Expert"
    tell menu bar 1
      click menu item "HTML" of menu 1 of menu item "Export Annotation Summary as..." of menu 1 of menu bar item "File"
    end tell
    tell window 1
      repeat until sheet 1 exists
      end repeat
      tell sheet 1
        keystroke "{dst_filename}"
        -- Command-Shift-G to "go to" directory
        key down shift
        key down command
        keystroke "g"
        key up shift
        key up command
        delay 1
        keystroke "{dst_dir}"
        click button "Go" of sheet 1
        delay 0.2
        click button "Save"
      end tell
    end tell
    tell menu bar 1
      click menu item "Close Tab" of menu 1 of menu bar item "File"
    end tell
  end tell
end tell
"""

    _subprocess.check_call(["osascript", "-e", script])


@dataclass
class Annotation:
    text: str
    page: Optional[int] = None
    datetime: Optional[datetime] = None
    author: Optional[str] = None


def _parse_html_exported_annotations(source_pdf_path: str) -> list[Annotation]:
    # PDF Expert's HTML-exported annotations are like <div class="row">...</div>
    # <div class="row by-date"><p class="text page">15</p><p class="text
    # dateAndAuthor">Jul 7, 3:28 PM, by A. Jesse Jiryu Davis</p></div>.
    def gen():
        with open(source_pdf_path) as f:
            soup = BeautifulSoup(f, "html.parser")
            annotation = None
            for div in soup.select("div.row"):
                if 'by-date' not in div.attrs["class"]:
                    annotation = Annotation(div.select_one("p.text").text)
                else:
                    assert annotation

                yield annotation

    return list(gen())


def has_annotations(source_pdf_path: str) -> bool:
    with _tempfile.NamedTemporaryFile() as tmp:
        _extract_to_html(source_pdf_path, tmp.name)
        return len(_parse_html_exported_annotations(f"{tmp.name}.html")) > 0
