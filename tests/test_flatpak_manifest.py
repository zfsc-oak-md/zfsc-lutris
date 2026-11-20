"""Checks for the flatpak packaging files.

These do not need flatpak installed; they only guard against the manifest and
the desktop/metainfo files drifting apart.
"""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_ID = "io.github.zfsc_oak_md.ZfscLutris"
MANIFEST = ROOT / "flatpak" / f"{APP_ID}.yml"

try:
    import yaml
except ImportError:  # pragma: no cover - only skipped in minimal environments
    yaml = None


@unittest.skipIf(yaml is None, "PyYAML is not installed")
class FlatpakManifestTest(unittest.TestCase):
    def setUp(self):
        self.manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))

    def test_identity(self):
        self.assertEqual(self.manifest["id"], APP_ID)
        self.assertEqual(self.manifest["command"], "zfsc-lutris")
        self.assertEqual(self.manifest["base"], "net.lutris.Lutris")
        self.assertEqual(self.manifest["base-version"], "stable")

    def test_sources_exist(self):
        for module in self.manifest["modules"]:
            for source in module.get("sources", []):
                if "path" not in source:
                    continue
                path = (MANIFEST.parent / source["path"]).resolve()
                self.assertTrue(path.exists(), f"missing source: {source['path']}")

    def test_service_module_is_installed(self):
        commands = [cmd for module in self.manifest["modules"] for cmd in module.get("build-commands", [])]
        joined = "\n".join(commands)
        self.assertIn("scripts/apply.py", joined)
        self.assertIn(f"share/applications/{APP_ID}.desktop", joined)
        self.assertIn(f"share/metainfo/{APP_ID}.metainfo.xml", joined)

    def test_desktop_entry_matches_app_id(self):
        desktop = (ROOT / "flatpak" / f"{APP_ID}.desktop").read_text(encoding="utf-8")
        self.assertIn("Exec=zfsc-lutris", desktop)
        self.assertIn(f"Icon={APP_ID}", desktop)

    def test_metainfo_matches_app_id(self):
        metainfo = (ROOT / "flatpak" / f"{APP_ID}.metainfo.xml").read_text(encoding="utf-8")
        self.assertIn(f"<id>{APP_ID}</id>", metainfo)
        self.assertIn(f"{APP_ID}.desktop", metainfo)

    def test_launcher_seeds_icon_from_bundle(self):
        launcher = (ROOT / "flatpak" / "zfsc-lutris.sh").read_text(encoding="utf-8")
        self.assertIn("/app/share/zfsc/zfsc.svg", launcher)
        self.assertIn("exec lutris", launcher)


if __name__ == "__main__":
    unittest.main()
