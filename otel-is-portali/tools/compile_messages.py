"""
Compile locale/*/LC_MESSAGES/django.po -> django.mo without GNU gettext.

Django's own `compilemessages` needs GNU gettext (msgfmt), which is often missing on
Windows. This script does the same job in pure Python:

    python tools/compile_messages.py

Run it after editing any .po file, then restart the server.
"""
import ast
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def parse_po(path):
    """Return {msgid: msgstr} where plural entries use 'singular\\0plural' -> 'form0\\0form1...'."""
    entries, cur, key, fuzzy = {}, {}, None, False

    def flush():
        nonlocal cur, fuzzy
        if "msgid" in cur and not fuzzy:
            msgid = cur["msgid"]
            if "msgid_plural" in cur:
                msgid += "\0" + cur["msgid_plural"]
                forms = [cur[k] for k in sorted((k for k in cur if k.startswith("msgstr[")), key=lambda k: int(k[7:-1]))]
                msgstr = "\0".join(forms)
            else:
                msgstr = cur.get("msgstr", "")
            if msgstr.replace("\0", "") or msgid == "":
                entries[msgid] = msgstr
        cur, fuzzy = {}, False

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#,") and "fuzzy" in line:
            fuzzy = True
            continue
        if line.startswith("#"):
            continue
        if line.startswith('"'):
            cur[key] += ast.literal_eval(line)
            continue
        word, _, rest = line.partition(" ")
        if word == "msgid" and "msgid" in cur:
            flush()
        key = word
        cur[key] = ast.literal_eval(rest)
    flush()
    return entries


def write_mo(entries, path):
    keys = sorted(entries)
    ids = b"".join(k.encode("utf-8") + b"\0" for k in keys)
    strs = b"".join(entries[k].encode("utf-8") + b"\0" for k in keys)
    n = len(keys)
    key_start = 7 * 4 + 16 * n
    value_start = key_start + len(ids)
    koffsets, voffsets, ko, vo = [], [], 0, 0
    for k in keys:
        kb, vb = k.encode("utf-8"), entries[k].encode("utf-8")
        koffsets += [len(kb), key_start + ko]
        voffsets += [len(vb), value_start + vo]
        ko += len(kb) + 1
        vo += len(vb) + 1
    header = struct.pack("Iiiiiii", 0x950412DE, 0, n, 7 * 4, 7 * 4 + n * 8, 0, 0)
    path.write_bytes(header + struct.pack(f"{len(koffsets)}i", *koffsets)
                     + struct.pack(f"{len(voffsets)}i", *voffsets) + ids + strs)


def main():
    pos = sorted((ROOT / "locale").glob("*/LC_MESSAGES/*.po"))
    if not pos:
        sys.exit("No .po files found under locale/")
    for po in pos:
        entries = parse_po(po)
        write_mo(entries, po.with_suffix(".mo"))
        print(f"compiled {po.relative_to(ROOT)} ({len(entries) - 1} messages)")


if __name__ == "__main__":
    main()
