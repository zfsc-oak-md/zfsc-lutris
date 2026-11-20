"""Lutris service for a self-hosted ZFSC server.

ZFSC exposes a read-only JSON API (``/api/v1``) protected by a personal
bearer token.  This module mirrors the shape of ``dlsite.py`` but takes the
library and the downloads from ZFSC instead of DLsite itself.
"""

import json
import os
from gettext import gettext as _
from typing import Any
from urllib.parse import quote, urlencode, urlparse

from gi.repository import Gtk

from lutris import settings
from lutris.exceptions import AuthenticationError, UnavailableGameError
from lutris.gui.dialogs import ErrorDialog, ModalDialog
from lutris.installer import AUTO_WIN32_EXE
from lutris.installer.installer_file import InstallerFile
from lutris.services.base import SERVICE_LOGIN, AuthTokenExpiredError, OnlineService
from lutris.services.service_game import ServiceGame
from lutris.services.service_media import ServiceMedia
from lutris.util.downloader import SimpleDownloader
from lutris.util.http import HTTPError, Request, UnauthorizedAccessError
from lutris.util.log import logger

API_PREFIX = "/api/v1"
DEFAULT_PAGE_SIZE = 100


def normalize_server_url(value: str) -> str:
    """Return a usable ZFSC base URL, or raise ``ValueError``."""
    url = value.strip().rstrip("/")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(_("The server URL must start with http:// or https://"))
    return url


class ZfscLoginDialog(ModalDialog):
    """Ask for the ZFSC server URL and a personal API token."""

    def __init__(self, service: "ZfscService", parent: Gtk.Widget | None = None):
        super().__init__(title=_("Connect to ZFSC"), parent=parent)
        self.set_border_width(12)
        self.set_default_size(480, -1)
        self.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        self.add_default_button(Gtk.STOCK_OK, Gtk.ResponseType.OK)
        self.set_default_response(Gtk.ResponseType.OK)

        grid = Gtk.Grid(column_spacing=12, row_spacing=8, visible=True)
        self.url_entry = Gtk.Entry(visible=True, hexpand=True, text=service.server_url)
        self.url_entry.set_placeholder_text("https://zfsc.example.com")
        self.token_entry = Gtk.Entry(visible=True, hexpand=True)
        self.token_entry.set_visibility(False)
        self.token_entry.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        self.token_entry.set_placeholder_text("zfsc_...")

        grid.attach(Gtk.Label(label=_("Server URL"), xalign=0, visible=True), 0, 0, 1, 1)
        grid.attach(self.url_entry, 1, 0, 1, 1)
        grid.attach(Gtk.Label(label=_("API token"), xalign=0, visible=True), 0, 1, 1, 1)
        grid.attach(self.token_entry, 1, 1, 1, 1)
        self.get_content_area().pack_start(grid, True, True, 0)

        hint = Gtk.Label(
            label=_("Ask a zfsc admin to run:\nzfsc token mint --user <you> --name lutris"),
            xalign=0,
            visible=True,
        )
        hint.set_selectable(True)
        self.get_content_area().pack_start(hint, False, False, 12)

        for entry in (self.url_entry, self.token_entry):
            entry.connect("changed", self._on_entry_changed)
        self._on_entry_changed()

    def _on_entry_changed(self, _entry: Gtk.Entry | None = None) -> None:
        has_values = bool(self.url_entry.get_text().strip() and self.token_entry.get_text().strip())
        self.set_response_sensitive(Gtk.ResponseType.OK, has_values)

    @property
    def server_url(self) -> str:
        return normalize_server_url(self.url_entry.get_text())

    @property
    def token(self) -> str:
        return self.token_entry.get_text().strip()


class ZfscBanner(ServiceMedia):
    """Work cover, taken from the DLsite metadata cached by ZFSC."""

    service = "zfsc"
    size = (200, 150)
    dest_path = os.path.join(settings.CACHE_DIR, "zfsc/banners")
    file_patterns = ["%s.jpg", "%s.png"]
    api_field = "cover_url"

    def get_media_url(self, details: dict[str, Any]) -> str | None:
        url = details.get(self.api_field) or ""
        if url.startswith("//"):
            return "https:" + url
        return url or None


class ZfscGame(ServiceGame):
    """A work in a ZFSC library."""

    service = "zfsc"
    runner = "wine"

    @classmethod
    def new_from_work(cls, work: dict[str, Any]) -> "ZfscGame":
        game = cls()
        game.appid = str(work.get("dlsite_id", ""))
        game.slug = game.appid.lower()
        game.name = work.get("title") or game.appid
        game.details = json.dumps(work, ensure_ascii=False)
        return game


class ZfscService(OnlineService):
    """Service class for a self-hosted ZFSC server."""

    id = "zfsc"
    name = _("ZFSC")
    description = _("Self-hosted DLsite library")
    icon = "zfsc"
    runner = "wine"
    drm_free = True
    medias = {"banner": ZfscBanner}
    default_format = "banner"

    cache_path = os.path.join(settings.CACHE_DIR, "zfsc-library.json")
    token_path = os.path.join(settings.CACHE_DIR, ".zfsc.token")

    @property
    def credential_files(self) -> list[str]:
        return [self.token_path]

    @property
    def server_url(self) -> str:
        return (settings.read_setting("server_url", section="zfsc", default="") or "").rstrip("/")

    def load_token(self) -> str | None:
        if not os.path.exists(self.token_path):
            return None
        with open(self.token_path, encoding="utf-8") as token_file:
            token = token_file.read().strip()
        return token or None

    def _save_token(self, token: str) -> None:
        os.makedirs(os.path.dirname(self.token_path), exist_ok=True)
        with open(self.token_path, "w", encoding="utf-8") as token_file:
            token_file.write(token)
        os.chmod(self.token_path, 0o600)

    @staticmethod
    def _request(server_url: str, token: str, path: str, timeout: int = 30) -> Any:
        request = Request(
            f"{server_url}{path}",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=timeout,
        )
        try:
            request.get()
        except UnauthorizedAccessError as ex:
            raise AuthTokenExpiredError(_("The ZFSC token was rejected")) from ex
        except HTTPError as ex:
            if ex.code == 401:
                raise AuthTokenExpiredError(_("The ZFSC token was rejected")) from ex
            raise
        return request.json

    @staticmethod
    def _probe(server_url: str, token: str) -> None:
        profile = ZfscService._request(server_url, token, f"{API_PREFIX}/me", timeout=10)
        if not isinstance(profile, dict) or not profile:
            raise ValueError(_("Unexpected response from the ZFSC API"))

    def api(self, path: str, params: dict[str, Any] | None = None, timeout: int = 30) -> Any:
        server_url = self.server_url
        if not server_url:
            raise AuthenticationError(_("ZFSC server URL is not configured"))
        token = self.load_token()
        if not token:
            raise AuthenticationError(_("ZFSC API token is not configured"))
        if params:
            clean = {key: value for key, value in params.items() if value is not None}
            path = f"{path}?{urlencode(clean)}"
        return self._request(server_url, token, path, timeout=timeout)

    def login(self, parent: Gtk.Widget | None = None) -> None:
        dialog = ZfscLoginDialog(self, parent=parent)
        response = dialog.run()
        if response != Gtk.ResponseType.OK:
            dialog.destroy()
            return
        try:
            server_url = dialog.server_url
            token = dialog.token
        except ValueError as ex:
            dialog.destroy()
            ErrorDialog(str(ex), parent=parent)
            return
        dialog.destroy()

        try:
            self._probe(server_url, token)
        except (AuthTokenExpiredError, HTTPError, UnauthorizedAccessError, ValueError) as ex:
            ErrorDialog(_("Could not connect to ZFSC: %s") % ex, parent=parent)
            return

        settings.write_setting("server_url", server_url, section="zfsc")
        self._save_token(token)
        SERVICE_LOGIN.fire(self)

    def is_connected(self) -> bool:
        if not self.is_authenticated() or not self.server_url:
            return False
        try:
            profile = self.api(f"{API_PREFIX}/me", timeout=10)
        except (AuthenticationError, AuthTokenExpiredError, HTTPError, UnauthorizedAccessError, ValueError):
            return False
        return isinstance(profile, dict) and bool(profile)

    def load(self) -> list[ZfscGame]:
        if not self.is_connected():
            logger.error("User not connected to ZFSC")
            return []

        games: list[ZfscGame] = []
        page = 1
        while True:
            data = self.api(
                f"{API_PREFIX}/works",
                {"page": page, "per_page": DEFAULT_PAGE_SIZE, "with_files": 1},
            )
            works = data.get("works") if isinstance(data, dict) else None
            if not isinstance(works, list):
                raise ValueError(_("Unexpected response from the ZFSC works API"))

            for work in works:
                if not work.get("latest_file"):
                    continue
                game = ZfscGame.new_from_work(work)
                game.save()
                games.append(game)

            next_page = data.get("next_page")
            if not next_page or next_page <= page:
                break
            page = next_page

        logger.info("Loaded %d games from ZFSC", len(games))
        return games

    def get_installer_files(self, installer: Any, installer_file_id: str) -> list[InstallerFile]:
        appid = installer.service_appid
        if not appid:
            return []

        try:
            work = self.api(f"{API_PREFIX}/works/{quote(str(appid), safe='')}")
        except AuthTokenExpiredError as ex:
            raise AuthenticationError(_("The ZFSC token expired; reconnect the service")) from ex
        except HTTPError as ex:
            if ex.code == 404:
                raise UnavailableGameError(_("This work is not available on ZFSC")) from ex
            raise

        file = work.get("latest_file") if isinstance(work, dict) else None
        file_id = file.get("id") if file else None
        if not file_id:
            raise UnavailableGameError(_("This work has no downloadable file on ZFSC"))

        server_url = self.server_url
        token = self.load_token()
        if not server_url or not token:
            raise AuthenticationError(_("ZFSC is not configured; reconnect the service"))

        url = f"{server_url}{API_PREFIX}/files/{file_id}"
        headers = {"Authorization": f"Bearer {token}"}
        filename = file.get("name") or f"{appid}.zip"
        return [
            InstallerFile(
                installer.game_slug,
                installer_file_id,
                {
                    "url": url,
                    "filename": filename,
                    "downloader": lambda f, u=url, h=headers: SimpleDownloader(
                        u, f.download_file, overwrite=True, headers=h
                    ),
                },
            )
        ]

    def get_installers_from_api(self, _appid: str) -> list[dict[str, Any]]:
        """ZFSC libraries are private; lutris.net has no matching installers."""
        return []

    def generate_installer(self, db_game: dict[str, Any]) -> dict[str, Any]:
        return {
            "name": db_game.get("name") or db_game["appid"],
            "version": "zfsc",
            "slug": db_game["slug"],
            "game_slug": self.get_installed_slug(db_game),
            "runner": "wine",
            "appid": db_game["appid"],
            "script": {
                "game": {"exe": AUTO_WIN32_EXE, "prefix": "$GAMEDIR/pfx"},
                "files": [{"zfscgame": "N/A:Select the game archive from zfsc"}],
                "installer": [
                    {"task": {"name": "create_prefix", "prefix": "$GAMEDIR/pfx"}},
                    {"install_or_extract": "zfscgame"},
                ],
            },
        }

    def get_installed_slug(self, db_game: dict[str, Any]) -> str:
        return (db_game.get("appid") or "").lower() or super().get_installed_slug(db_game)

    def get_game_release_date(self, db_game: dict[str, Any]) -> str:
        date = self._details(db_game).get("release_date") or ""
        return date[:10] if len(date) >= 10 else ""

    def get_store_url(self, db_game: dict[str, Any]) -> str:
        return self._details(db_game).get("product_url") or ""

    def get_game_platforms(self, _db_game: dict[str, Any]) -> list[str]:
        return ["Windows"]

    @staticmethod
    def _details(db_game: dict[str, Any]) -> dict[str, Any]:
        raw = db_game.get("details")
        if not raw:
            return {}
        try:
            details = json.loads(raw)
        except (TypeError, ValueError):
            return {}
        return details if isinstance(details, dict) else {}
