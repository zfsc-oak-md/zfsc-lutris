"""Unit tests for the ZFSC service module.

The module is loaded with small stubs for Lutris and GTK so these tests run
without a Lutris installation or a display.  They cover the pure client logic;
the GTK dialog and actual Lutris integration are exercised manually.
"""

import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parent.parent
CACHE_DIR = tempfile.TemporaryDirectory()


class AuthenticationError(Exception):
    pass


class UnavailableGameError(Exception):
    pass


class AuthTokenExpiredError(Exception):
    pass


class HTTPError(Exception):
    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code


class UnauthorizedAccessError(Exception):
    pass


class InstallerFile:
    def __init__(self, game_slug, file_id, meta):
        self.game_slug = game_slug
        self.id = file_id
        self.meta = meta
        self.url = meta["url"]
        self.filename = meta["filename"]


class SimpleDownloader:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class OnlineService:
    cookies_path = None
    cache_path = None

    def is_authenticated(self):
        return all(Path(path).exists() for path in self.credential_files)

    def get_installed_slug(self, db_game):
        return db_game["name"].lower()


class ServiceGame:
    saved = []

    def save(self):
        self.saved.append(self)


class ServiceMedia:
    pass


class Logger:
    def info(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass


class FakeGtk:
    class Widget:
        pass

    class Entry:
        pass

    class Grid:
        pass

    class Label:
        pass

    class ResponseType:
        OK = 1
        CANCEL = 0

    class InputPurpose:
        PASSWORD = 1

    STOCK_OK = "ok"
    STOCK_CANCEL = "cancel"


def install_stubs(settings_values):
    def module(name, **attrs):
        value = types.ModuleType(name)
        for key, attr in attrs.items():
            setattr(value, key, attr)
        sys.modules[name] = value
        return value

    module("gi")
    module("gi.repository", Gtk=FakeGtk)
    module("lutris")
    module(
        "lutris.settings",
        CACHE_DIR=CACHE_DIR.name,
        read_setting=lambda key, section=None, default=None: settings_values.get(key, default),
        write_setting=lambda key, value, section=None: settings_values.__setitem__(key, value),
    )
    module("lutris.exceptions", AuthenticationError=AuthenticationError, UnavailableGameError=UnavailableGameError)
    module("lutris.gui")
    module("lutris.gui.dialogs", ErrorDialog=object, ModalDialog=object)
    module("lutris.installer", AUTO_WIN32_EXE="AUTO_WIN32_EXE")
    module("lutris.installer.installer_file", InstallerFile=InstallerFile)
    module("lutris.services", __path__=[])
    module(
        "lutris.services.base",
        SERVICE_LOGIN=types.SimpleNamespace(fire=lambda service: None),
        AuthTokenExpiredError=AuthTokenExpiredError,
        OnlineService=OnlineService,
    )
    module("lutris.services.service_game", ServiceGame=ServiceGame)
    module("lutris.services.service_media", ServiceMedia=ServiceMedia)
    module("lutris.util")
    module("lutris.util.downloader", SimpleDownloader=SimpleDownloader)
    module("lutris.util.http", HTTPError=HTTPError, Request=object, UnauthorizedAccessError=UnauthorizedAccessError)
    module("lutris.util.log", logger=Logger())


def load_module():
    spec = importlib.util.spec_from_file_location("lutris.services.zfsc", REPO / "lutris/services/zfsc.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


SETTINGS = {}
install_stubs(SETTINGS)
zfsc = load_module()

WORK = {
    "dlsite_id": "RJ01234567",
    "title": "Example",
    "cover_url": "//img.example/cover.jpg",
    "release_date": "2024-05-01",
    "product_url": "https://www.dlsite.com/maniax/work/=/product_id/RJ01234567.html",
    "latest_file": {
        "id": 42,
        "name": "game.zip",
        "size": 1,
        "sha256": "x",
        "version": "2024-05-01",
        "source": "dlsite",
    },
}


class FakeRequest:
    payload = {}
    error = None

    def __init__(self, url, headers=None, timeout=30):
        self.url = url
        self.headers = headers
        self.timeout = timeout

    def get(self):
        if self.error:
            raise self.error
        return self

    @property
    def json(self):
        return self.payload


class ZfscModuleTest(unittest.TestCase):
    def setUp(self):
        SETTINGS.clear()
        SETTINGS["server_url"] = "https://zfsc.example"
        self.token_path = Path(CACHE_DIR.name) / ".zfsc.token"
        self.token_path.write_text("zfsc_test", encoding="utf-8")
        self.service = zfsc.ZfscService()
        ServiceGame.saved = []

    def test_request_returns_json_and_maps_auth_failures(self):
        with patch.object(zfsc, "Request", FakeRequest):
            FakeRequest.payload = {"id": 1}
            FakeRequest.error = None
            self.assertEqual(self.service._request("https://zfsc.example", "zfsc_test", "/api/v1/me"), {"id": 1})

            FakeRequest.error = UnauthorizedAccessError("denied")
            with self.assertRaises(AuthTokenExpiredError):
                self.service._request("https://zfsc.example", "zfsc_test", "/api/v1/me")

            FakeRequest.error = HTTPError("missing", code=404)
            with self.assertRaises(HTTPError):
                self.service._request("https://zfsc.example", "zfsc_test", "/api/v1/me")

    def test_normalize_server_url(self):
        self.assertEqual(zfsc.normalize_server_url(" https://zfsc.example/ "), "https://zfsc.example")
        with self.assertRaises(ValueError):
            zfsc.normalize_server_url("zfsc.example")

    def test_new_game(self):
        game = zfsc.ZfscGame.new_from_work(WORK)
        self.assertEqual(game.appid, "RJ01234567")
        self.assertEqual(game.slug, "rj01234567")
        self.assertEqual(game.name, "Example")
        self.assertEqual(json.loads(game.details)["latest_file"]["id"], 42)

    def test_banner_normalizes_protocol_relative_url(self):
        self.assertEqual(zfsc.ZfscBanner().get_media_url(WORK), "https://img.example/cover.jpg")
        self.assertIsNone(zfsc.ZfscBanner().get_media_url({}))

    def test_helpers(self):
        details = {"details": json.dumps(WORK)}
        self.assertEqual(self.service.get_game_release_date(details), "2024-05-01")
        self.assertTrue(self.service.get_store_url(details).endswith("RJ01234567.html"))
        self.assertEqual(self.service.get_installed_slug({"appid": "RJ01234567", "name": "Example"}), "rj01234567")
        self.assertEqual(self.service.get_installers_from_api("RJ01234567"), [])

    def test_generate_installer(self):
        installer = self.service.generate_installer(
            {"appid": "RJ01234567", "slug": "rj01234567", "name": "Example", "details": json.dumps(WORK)}
        )
        self.assertEqual(installer["runner"], "wine")
        self.assertEqual(installer["game_slug"], "rj01234567")
        self.assertEqual(installer["script"]["files"], [{"zfscgame": "N/A:Select the game archive from zfsc"}])
        self.assertEqual(installer["script"]["installer"][1], {"install_or_extract": "zfscgame"})

    def test_load_skips_works_without_a_file_and_follows_pages(self):
        pages = {
            1: {"works": [WORK, {**WORK, "dlsite_id": "RJ2", "latest_file": None}], "next_page": 2},
            2: {"works": [{**WORK, "dlsite_id": "RJ3"}], "next_page": None},
        }
        calls = []

        def api(path, params=None, timeout=30):
            if path == "/api/v1/me":
                return {"id": 1}
            calls.append(params)
            return pages[params["page"]]

        self.service.api = api
        games = self.service.load()
        self.assertEqual([game.appid for game in games], ["RJ01234567", "RJ3"])
        self.assertEqual([page["page"] for page in calls], [1, 2])
        self.assertEqual(len(ServiceGame.saved), 2)

    def test_installer_file_uses_a_bearer_header(self):
        self.service.api = lambda path, params=None, timeout=30: WORK
        files = self.service.get_installer_files(
            types.SimpleNamespace(service_appid="RJ01234567", game_slug="rj01234567"), "zfscgame"
        )
        self.assertEqual(files[0].url, "https://zfsc.example/api/v1/files/42")
        self.assertEqual(files[0].filename, "game.zip")
        downloader = files[0].meta["downloader"](types.SimpleNamespace(download_file="/tmp/game.zip"))
        self.assertEqual(downloader.kwargs["headers"], {"Authorization": "Bearer zfsc_test"})

    def test_installer_file_rejects_a_work_without_a_file(self):
        self.service.api = lambda path, params=None, timeout=30: {**WORK, "latest_file": None}
        with self.assertRaises(UnavailableGameError):
            self.service.get_installer_files(
                types.SimpleNamespace(service_appid="RJ01234567", game_slug="rj01234567"), "zfscgame"
            )


if __name__ == "__main__":
    unittest.main()
