#!/usr/bin/env python3
"""Copy the ZFSC service into a Lutris source tree and register it.

The script is intentionally idempotent: running it twice leaves a single import
and a single ``_services["zfsc"]`` entry.
"""

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVICE_SOURCE = ROOT / "lutris" / "services" / "zfsc.py"
SERVICE_TARGET_REL = Path("lutris") / "services" / "zfsc.py"
INIT_REL = Path("lutris") / "services" / "__init__.py"
IMPORT_LINE = "from lutris.services.zfsc import ZfscService"
REGISTRATION_LINE = '        "zfsc": ZfscService,'


def fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def add_import(lines: list[str]) -> list[str]:
    if any(line.strip() == IMPORT_LINE for line in lines):
        return lines

    insert_at = None
    for index, line in enumerate(lines):
        if line.startswith("from lutris.services.zoom import "):
            insert_at = index
            break

    if insert_at is None:
        service_imports = [index for index, line in enumerate(lines) if line.startswith("from lutris.services.")]
        if service_imports:
            insert_at = service_imports[-1] + 1

    if insert_at is None:
        fail(f"could not find the services import block in {INIT_REL}")

    lines.insert(insert_at, IMPORT_LINE)
    return lines


def add_registration(text: str) -> str:
    if '"zfsc": ZfscService' in text:
        return text

    marker = '        "dlsite": DlsiteService,\n'
    if marker in text:
        return text.replace(marker, marker + REGISTRATION_LINE + "\n", 1)

    marker = "    _services = {\n"
    if marker not in text:
        fail(f"could not find the _services dictionary in {INIT_REL}")
    return text.replace(marker, marker + REGISTRATION_LINE + "\n", 1)


def main() -> None:
    if len(sys.argv) != 2:
        fail("usage: apply.py <lutris-source-dir>")

    source_dir = Path(sys.argv[1]).resolve()
    init_path = source_dir / INIT_REL
    if not init_path.is_file():
        fail(f"{source_dir} does not look like a Lutris source tree (missing {INIT_REL})")
    if not SERVICE_SOURCE.is_file():
        fail(f"missing service module: {SERVICE_SOURCE}")

    target = source_dir / SERVICE_TARGET_REL
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SERVICE_SOURCE, target)

    text = init_path.read_text(encoding="utf-8")
    lines = add_import(text.splitlines())
    text = "\n".join(lines)
    if not text.endswith("\n"):
        text += "\n"
    text = add_registration(text)
    init_path.write_text(text, encoding="utf-8")

    print(f"copied {SERVICE_TARGET_REL}")
    print(f"registered ZfscService in {INIT_REL}")


if __name__ == "__main__":
    main()
