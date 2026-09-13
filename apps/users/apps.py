"""
AppConfig for the users application.
"""

import array
import os
import struct

from django.apps import AppConfig
from django.conf import settings
import firebase_admin
from firebase_admin import credentials


def compile_po_to_mo(po_path: str, mo_path: str) -> None:
    """Compile a .po gettext catalog to a GNU .mo binary file in pure Python."""
    if not os.path.exists(po_path):
        return

    # Check if .mo is already up-to-date
    if os.path.exists(mo_path) and os.path.getmtime(mo_path) >= os.path.getmtime(po_path):
        return

    try:
        with open(po_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        catalog = {}
        msgid = None
        msgstr = None
        current = None

        def unescape(s: str) -> str:
            return (
                s.replace(r"\\", "\x00")
                .replace(r"\n", "\n")
                .replace(r"\t", "\t")
                .replace(r'\"', '"')
                .replace("\x00", "\\")
            )

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith('msgid "'):
                if msgid is not None and msgstr is not None:
                    catalog[msgid] = msgstr
                msgid = unescape(line[7:-1])
                msgstr = None
                current = "msgid"
            elif line.startswith('msgstr "'):
                msgstr = unescape(line[8:-1])
                current = "msgstr"
            elif line.startswith('"') and line.endswith('"'):
                val = unescape(line[1:-1])
                if current == "msgid":
                    msgid += val
                elif current == "msgstr":
                    msgstr += val

        if msgid is not None and msgstr is not None:
            catalog[msgid] = msgstr

        keys = sorted(catalog.keys())
        offsets = []
        ids = b""
        strs = b""

        for k in keys:
            k_bytes = k.encode("utf-8")
            v_bytes = catalog[k].encode("utf-8")
            offsets.append((len(ids), len(k_bytes), len(strs), len(v_bytes)))
            ids += k_bytes + b"\x00"
            strs += v_bytes + b"\x00"

        keystart = 7 * 4 + 16 * len(keys)
        valuestart = keystart + len(ids)

        koffsets = []
        voffsets = []
        for o1, l1, o2, l2 in offsets:
            koffsets.extend([l1, o1 + keystart])
            voffsets.extend([l2, o2 + valuestart])

        output = struct.pack(
            "Iiiiiii",
            0x950412DE,
            0,
            len(keys),
            7 * 4,
            7 * 4 + len(keys) * 8,
            0,
            0,
        )
        output += array.array("i", koffsets).tobytes()
        output += array.array("i", voffsets).tobytes()
        output += ids
        output += strs

        os.makedirs(os.path.dirname(mo_path), exist_ok=True)
        with open(mo_path, "wb") as f:
            f.write(output)
    except Exception as e:
        print(f"Warning: Failed to compile {po_path} to {mo_path}: {e}")


class UsersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.users"
    verbose_name = "Users"

    def ready(self):
        """Initialize Firebase Admin SDK and auto-compile translations on startup."""
        po_file = os.path.join(settings.BASE_DIR, "locale", "es", "LC_MESSAGES", "django.po")
        mo_file = os.path.join(settings.BASE_DIR, "locale", "es", "LC_MESSAGES", "django.mo")
        compile_po_to_mo(po_file, mo_file)

        if getattr(settings, "FIREBASE_CREDENTIALS_PATH", None) and not firebase_admin._apps:
            try:
                cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
                firebase_admin.initialize_app(cred)
            except Exception as e:
                print(f"Failed to initialize Firebase app: {e}")
