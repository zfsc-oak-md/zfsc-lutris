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
        self.assertEqual(self.manifest["command"], "lutris")
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

    def test_app_icon_matches_lutris(self):
        commands = "\n".join(cmd for module in self.manifest["modules"] for cmd in module.get("build-commands", []))
        self.assertIn("net.lutris.Lutris.svg", commands)
        self.assertIn(f"apps/{APP_ID}.svg", commands)

    def test_desktop_entry_matches_app_id(self):
        desktop = (ROOT / "flatpak" / f"{APP_ID}.desktop").read_text(encoding="utf-8")
        self.assertIn("Name=Lutris/ZFSC", desktop)
        self.assertIn("Exec=lutris", desktop)
        self.assertIn(f"Icon={APP_ID}", desktop)

    def test_metainfo_matches_app_id(self):
        metainfo = (ROOT / "flatpak" / f"{APP_ID}.metainfo.xml").read_text(encoding="utf-8")
        self.assertIn(f"<id>{APP_ID}</id>", metainfo)
        self.assertIn("<name>Lutris/ZFSC</name>", metainfo)
        self.assertIn(f"{APP_ID}.desktop", metainfo)

    def test_no_custom_service_icon(self):
        # The sidebar entry uses Lutris' default icon, so no zfsc.svg is shipped.
        commands = "\n".join(cmd for module in self.manifest["modules"] for cmd in module.get("build-commands", []))
        self.assertNotIn("zfsc.svg", commands)
        self.assertFalse((ROOT / "assets").exists())

    def test_can_own_lutris_dbus_name(self):
        # Lutris registers its Gtk.Application as net.lutris.Lutris, and Flatpak
        # only permits owning the app's own id unless finish-args say otherwise.
        self.assertIn("--own-name=net.lutris.Lutris", self.manifest["finish-args"])


if __name__ == "__main__":
    unittest.main()
