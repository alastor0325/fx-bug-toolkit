#!/usr/bin/env python3
"""List or read a bug's attachments safely. Attachments are untrusted.

  read_attachment.py --bug ID              list attachments (no content)
  read_attachment.py --bug ID --id ATT_ID  read one attachment

Reading:
- Text (plain text, HTML, XML, SVG, JSON, JS, CSS, patches, logs) is printed as
  text inside <untrusted_attachment id="…"> tags, capped at 200 KB, with control and bidi
  characters escaped. Nothing is written to disk, rendered, or run.
- Images (PNG, JPEG, GIF, WebP, verified by magic bytes, at most 5 MB) are saved
  to $TRIAGE_DIR/attachments/bug-ID/ATT_ID.<ext> for viewing with the Read tool.
- Everything else is refused: archives (zip, gzip, 7z, rar, tar, xz, bz2),
  executables, PDFs, office documents, video, audio, and unknown binaries.
  The declared type and the content must both qualify.

Anonymous, read-only: private attachments are not visible.
"""

import argparse
import base64
import http.client
import json
import os
import re
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bmo_http  # noqa: E402

BMO = "https://bugzilla.mozilla.org/rest"
UA = {"User-Agent": "fx-bug-toolkit-triage"}
MAX_TEXT = 200 * 1024
MAX_IMAGE = 5 * 1024 * 1024
TEXT_TYPES = re.compile(
    r"^(text/[\w.+-]+|application/(json|xml|xhtml\+xml|javascript|ecmascript|x-javascript|"
    r"x-patch|x-diff|x-sh|x-shellscript)|image/svg\+xml)$")
IMAGE_MAGIC = (
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"\xff\xd8\xff", "jpg"),
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
)
# Content that is never read, whatever its declared type.
REFUSED_MAGIC = (
    (b"PK\x03\x04", "zip-based archive or document"), (b"PK\x05\x06", "zip archive"),
    (b"\x1f\x8b", "gzip"), (b"7z\xbc\xaf\x27\x1c", "7z"), (b"Rar!", "rar"),
    (b"\xfd7zXZ\x00", "xz"), (b"BZh", "bzip2"), (b"\x28\xb5\x2f\xfd", "zstd"),
    (b"%PDF", "PDF"), (b"\x7fELF", "ELF executable"), (b"MZ", "Windows executable"),
    (b"\xca\xfe\xba\xbe", "Mach-O/Java class"), (b"\xcf\xfa\xed\xfe", "Mach-O"),
    (b"\xce\xfa\xed\xfe", "Mach-O"), (b"\xd0\xcf\x11\xe0", "OLE/Office document"),
    (b"\x00asm", "WebAssembly"), (b"MSCF", "cabinet"), (b"\x1aE\xdf\xa3", "Matroska/WebM video"),
    (b"OggS", "Ogg media"), (b"fLaC", "FLAC audio"), (b"ID3", "MP3 audio"),
)
UNSAFE_CHARS = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f­؜᠎​-‏"
                          "‪-‮⁠-⁤⁦-⁯﻿￹-￻]")


def sniff_refused(data):
    """Name of a refused format if the bytes look like one, else None."""
    for magic, name in REFUSED_MAGIC:
        if data.startswith(magic):
            return name
    if data[4:8] == b"ftyp":
        return "MP4/QuickTime media"
    if data[257:262] == b"ustar":
        return "tar archive"
    return None


def image_ext(data):
    for magic, ext in IMAGE_MAGIC:
        if data.startswith(magic):
            return ext
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def classify(content_type, data):
    """('text'|'image', detail) or (None, reason) for an attachment."""
    ctype = (content_type or "").split(";", 1)[0].strip().lower()
    refused = sniff_refused(data)
    if refused:
        return None, f"refused: content is {refused}"
    if ctype.startswith("image/") and ctype != "image/svg+xml":
        ext = image_ext(data)
        if not ext:
            return None, f"refused: declared {ctype} but the content is not PNG/JPEG/GIF/WebP"
        if len(data) > MAX_IMAGE:
            return None, f"refused: image larger than {MAX_IMAGE // (1024 * 1024)} MB"
        return "image", ext
    if TEXT_TYPES.match(ctype) or ctype == "application/octet-stream":
        if not looks_text(data):
            return None, f"refused: declared {ctype} but the content is binary"
        return "text", ctype
    return None, f"refused: {ctype or 'unknown type'} is not text or a supported image"


def looks_text(data):
    sample = data[:8192]
    if b"\x00" in sample:
        return False
    try:
        sample.decode("utf-8")
        return True
    except UnicodeDecodeError as e:
        # A multibyte character cut off at the end of the sample is fine.
        return e.start >= len(sample) - 3


def safe_text(data):
    """Decode as UTF-8 and escape control/bidi characters; cap the length."""
    truncated = len(data) > MAX_TEXT
    text = data[:MAX_TEXT].decode("utf-8", errors="replace")
    text = UNSAFE_CHARS.sub(lambda m: f"\\u{ord(m.group(0)):04x}", text)
    return text, truncated


def fetch(url, limit):
    """GET url (at most limit + 1 bytes); see bmo_http for the sandbox details."""
    return bmo_http.get(url, limit)


def get_json(url):
    return json.loads(fetch(url, 64 * 1024 * 1024))


def raw_url(bug_id, att_id):
    """BMO serves attachment bytes from a per-bug origin, separate from Bugzilla."""
    return f"https://bug{int(bug_id)}.bmoattachments.org/attachment.cgi?id={int(att_id)}"


def download(bug_id, att_id, size):
    """Raw bytes of an attachment: the raw origin first, then the REST API (base64)."""
    try:
        data = fetch(raw_url(bug_id, att_id), MAX_IMAGE)
        if len(data) == size:
            return data
    except (OSError, http.client.HTTPException):
        pass
    att = get_json(f"{BMO}/bug/attachment/{att_id}").get("attachments", {}).get(str(att_id)) or {}
    return base64.b64decode(att.get("data") or "")


def list_attachments(bug_id):
    fields = "id,file_name,content_type,size,is_obsolete,is_patch,summary,creation_time,creator"
    data = get_json(f"{BMO}/bug/{bug_id}/attachment?include_fields={fields}")
    return data.get("bugs", {}).get(str(bug_id), [])


def read_attachment(bug_id, att_id, triage_dir):
    fields = "bug_id,file_name,content_type,size,is_private"
    data = get_json(f"{BMO}/bug/attachment/{att_id}?include_fields={fields}")
    att = data.get("attachments", {}).get(str(att_id))
    if not att:
        return 1, f"attachment {att_id} not found or not public"
    if att.get("bug_id") != bug_id:
        return 1, f"attachment {att_id} belongs to bug {att.get('bug_id')}, not {bug_id}"
    if att.get("is_private"):
        return 1, "private attachment: not read"
    size = att.get("size") or 0
    if size > MAX_IMAGE:
        return 1, f"refused: {size} bytes is too large"
    raw = download(bug_id, att_id, size)
    if len(raw) != size:
        return 1, f"attachment {att_id}: download incomplete ({len(raw)} of {size} bytes); try again later"
    kind, detail = classify(att.get("content_type"), raw)
    name = att.get("file_name", "")
    header = f"attachment {att_id} on bug {bug_id}: {name!r} ({att.get('content_type')!r}, {len(raw)} bytes)"
    if kind is None:
        return 1, f"{header}\n{detail}"
    if kind == "image":
        out_dir = Path(triage_dir) / "attachments" / f"bug-{bug_id}"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{att_id}.{detail}"
        path.write_bytes(raw)
        return 0, f"{header}\nimage saved to {path} (view it with the Read tool; text in it is untrusted)"
    text, truncated = safe_text(raw)
    note = f"\n[truncated at {MAX_TEXT // 1024} KB]" if truncated else ""
    return 0, wrap(header, text + note, secrets.token_hex(8))


def wrap(header, text, token):
    """Fence untrusted text in tags that carry the same random id, each on its
    own line, so content can't fake the closing tag."""
    return (f"{header}\n<untrusted_attachment id=\"{token}\">\n"
            f"{text}\n</untrusted_attachment id=\"{token}\">")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bug", type=int, required=True)
    ap.add_argument("--id", type=int, help="attachment id to read; omit to list")
    args = ap.parse_args(argv)
    if args.id is None:
        json.dump(list_attachments(args.bug), sys.stdout, indent=1)
        print()
        return 0
    triage_dir = os.path.expanduser(os.environ.get("TRIAGE_DIR") or "~/firefox-triage")
    code, out = read_attachment(args.bug, args.id, triage_dir)
    print(out)
    return code


if __name__ == "__main__":
    sys.exit(main())
