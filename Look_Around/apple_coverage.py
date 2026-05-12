"""Apple Look Around coverage: parallel fetch, on-disk cache, background QgsTask.

The Apple coverage tiles are served by the unofficial lookmap.eu API (Apple
provides no public API). A naive sequential urllib loop blocks the QGIS UI
for tens of seconds on a fresh extent. This module replaces that with:

  * a thread pool that reuses one HTTPS connection per worker (keep-alive
    + gzip);
  * a two-tier cache (in-memory + JSON files in the QGIS profile directory)
    keyed by (x, y) at zoom 17, with ``If-Modified-Since`` revalidation;
  * a ``QgsTask`` so fetching runs off the GUI thread and shows progress
    in the QGIS task manager.
"""

from __future__ import annotations

import gzip
import http.client
import json
import math
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from qgis.core import (
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsFeature,
    QgsGeometry,
    QgsMessageLog,
    QgsPointXY,
    QgsProject,
    QgsTask,
    QgsVectorLayer,
)
from qgis.PyQt.QtGui import QColor

from .i18n import tr

_LOOKMAP_HOST = "lookmap.eu.pythonanywhere.com"
_LOOKMAP_PATH = "/tiles/coverage/{x}/{y}/"
_APPLE_COVERAGE_ZOOM = 17

_REQUEST_TIMEOUT_S = 8
_APPLE_MAX_WORKERS = 12

# Treat cached tiles as fresh without revalidation for this long. After that,
# we still reuse the cached panos but ask the server with If-Modified-Since.
_CACHE_TTL_S = 24 * 60 * 60

_USER_AGENT = "QGIS-LookAround-Plugin/0.3"
_LOG_TAG = "Look Around"


def layer_name_apple() -> str:
    return tr("Look Around Coverage")


class RateLimited(Exception):
    """Raised when lookmap.eu returns HTTP 429 — abort the whole task."""


# ---------------------------------------------------------------------------
# Tile cache
# ---------------------------------------------------------------------------

class _AppleTileCache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._mem: dict[tuple[int, int], dict] = {}
        self._dir: Path | None = None

    def _ensure_dir(self) -> Path:
        if self._dir is None:
            base = Path(QgsApplication.qgisSettingsDirPath())
            self._dir = base / "cache" / "lookaround" / f"apple_coverage_z{_APPLE_COVERAGE_ZOOM}"
            self._dir.mkdir(parents=True, exist_ok=True)
        return self._dir

    def _path_for(self, x: int, y: int) -> Path:
        return self._ensure_dir() / f"{x}_{y}.json"

    def get(self, x: int, y: int) -> dict | None:
        key = (x, y)
        with self._lock:
            entry = self._mem.get(key)
            if entry is not None:
                return entry
        # Disk fallback
        path = self._path_for(x, y)
        try:
            with path.open("r", encoding="utf-8") as fh:
                entry = json.load(fh)
        except FileNotFoundError:
            return None
        except (OSError, json.JSONDecodeError):
            return None
        with self._lock:
            self._mem[key] = entry
        return entry

    def put(self, x: int, y: int, panos: list, last_modified: str | None) -> dict:
        entry = {
            "panos": panos,
            "last_modified": last_modified,
            "cached_at": time.time(),
        }
        with self._lock:
            self._mem[(x, y)] = entry
        path = self._path_for(x, y)
        tmp = path.with_suffix(".json.tmp")
        try:
            with tmp.open("w", encoding="utf-8") as fh:
                json.dump(entry, fh)
            os.replace(tmp, path)
        except OSError as exc:
            QgsMessageLog.logMessage(
                f"Apple tile cache write failed for {x},{y}: {exc!r}", _LOG_TAG
            )
        return entry

    def touch(self, x: int, y: int, last_modified: str | None) -> dict | None:
        """Refresh ``cached_at`` after a successful 304 Not Modified."""
        entry = self.get(x, y)
        if entry is None:
            return None
        entry["cached_at"] = time.time()
        if last_modified:
            entry["last_modified"] = last_modified
        with self._lock:
            self._mem[(x, y)] = entry
        path = self._path_for(x, y)
        tmp = path.with_suffix(".json.tmp")
        try:
            with tmp.open("w", encoding="utf-8") as fh:
                json.dump(entry, fh)
            os.replace(tmp, path)
        except OSError:
            pass
        return entry


_CACHE = _AppleTileCache()


# ---------------------------------------------------------------------------
# Tile math (slippy / Web Mercator)
# ---------------------------------------------------------------------------

def _latlon_to_tile(lat: float, lon: float, zoom: int) -> tuple[int, int]:
    n = 2 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    lat_r = math.radians(lat)
    y = int(
        (1.0 - math.log(math.tan(lat_r) + 1.0 / math.cos(lat_r)) / math.pi)
        / 2.0 * n
    )
    return x, y


def _extent_to_tiles(
    min_lat: float, max_lat: float,
    min_lon: float, max_lon: float,
    zoom: int,
) -> list[tuple[int, int]]:
    x0, y0 = _latlon_to_tile(max_lat, min_lon, zoom)
    x1, y1 = _latlon_to_tile(min_lat, max_lon, zoom)
    return [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]


# ---------------------------------------------------------------------------
# HTTP fetch (one keep-alive HTTPSConnection per worker thread)
# ---------------------------------------------------------------------------

def _get_connection(local: threading.local) -> http.client.HTTPSConnection:
    conn = getattr(local, "conn", None)
    if conn is None:
        conn = http.client.HTTPSConnection(_LOOKMAP_HOST, timeout=_REQUEST_TIMEOUT_S)
        local.conn = conn
    return conn


def _close_connection(local: threading.local) -> None:
    conn = getattr(local, "conn", None)
    if conn is not None:
        try:
            conn.close()
        except OSError as exc:
            QgsMessageLog.logMessage(
                f"Apple connection close failed: {exc!r}", _LOG_TAG
            )
        local.conn = None


def _request(
    local: threading.local,
    path: str,
    if_modified_since: str | None,
) -> tuple[int, dict, bytes]:
    headers = {
        "Host": _LOOKMAP_HOST,
        "User-Agent": _USER_AGENT,
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "Connection": "keep-alive",
    }
    if if_modified_since:
        headers["If-Modified-Since"] = if_modified_since

    # One transparent retry handles a stale keep-alive connection that the
    # server already closed. Anything else propagates.
    for attempt in (0, 1):
        conn = _get_connection(local)
        try:
            conn.request("GET", path, headers=headers)
            resp = conn.getresponse()
            body = resp.read()
            status = resp.status
            resp_headers = {k.lower(): v for k, v in resp.getheaders()}
            if resp_headers.get("content-encoding") == "gzip" and body:
                body = gzip.decompress(body)
            return status, resp_headers, body
        except (http.client.RemoteDisconnected, http.client.BadStatusLine, ConnectionError, OSError):
            _close_connection(local)
            if attempt == 1:
                raise
    raise RuntimeError("unreachable")


def _fetch_tile(x: int, y: int, local: threading.local) -> dict:
    """Return a cache entry ``{panos, last_modified, cached_at}`` for tile (x,y).

    Raises ``RateLimited`` on HTTP 429. On any other network/parse error,
    returns an empty entry (and logs) so the rest of the extent still loads.
    """
    cached = _CACHE.get(x, y)
    now = time.time()
    if cached and (now - cached.get("cached_at", 0)) < _CACHE_TTL_S:
        return cached

    if_mod = cached.get("last_modified") if cached else None
    path = _LOOKMAP_PATH.format(x=x, y=y)

    try:
        status, headers, body = _request(local, path, if_mod)
    except Exception as exc:
        QgsMessageLog.logMessage(
            f"lookmap.eu fetch failed for {x},{y}: {exc!r}", _LOG_TAG
        )
        return cached or {"panos": [], "last_modified": None, "cached_at": 0}

    if status == 304 and cached is not None:
        return _CACHE.touch(x, y, headers.get("last-modified")) or cached
    if status == 429:
        raise RateLimited()
    if status != 200:
        QgsMessageLog.logMessage(
            f"lookmap.eu HTTP {status} for {x},{y}", _LOG_TAG
        )
        return cached or {"panos": [], "last_modified": None, "cached_at": 0}

    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        QgsMessageLog.logMessage(
            f"lookmap.eu parse error for {x},{y}: {exc!r}", _LOG_TAG
        )
        return cached or {"panos": [], "last_modified": None, "cached_at": 0}

    # API: {"panos": [...], "lastModified": ...}; older "panoramas" / "latitude"
    # spellings are kept as a fallback in case the API ever changes.
    panos_raw = data.get("panos") or data.get("panoramas") or []
    panos: list[tuple[float, float]] = []
    for pano in panos_raw:
        lat = pano.get("lat") or pano.get("latitude")
        lon = pano.get("lon") or pano.get("longitude")
        if lat is not None and lon is not None:
            panos.append((float(lat), float(lon)))
    return _CACHE.put(x, y, panos, headers.get("last-modified"))


# ---------------------------------------------------------------------------
# Background QgsTask
# ---------------------------------------------------------------------------

class AppleCoverageTask(QgsTask):
    def __init__(self, iface, tiles: list[tuple[int, int]]):
        super().__init__(tr("Loading Apple Look Around coverage"), QgsTask.CanCancel)
        self._iface = iface
        self._tiles = tiles
        self._coords: list[tuple[float, float]] = []
        self.error_message: str | None = None
        self._rate_limited = False

    def run(self) -> bool:
        if not self._tiles:
            return True

        thread_local = threading.local()
        all_locals: list[threading.local] = []

        def worker(tile: tuple[int, int]) -> list[tuple[float, float]]:
            # First call on a worker thread initialises its connection.
            if not getattr(thread_local, "registered", False):
                thread_local.registered = True
                all_locals.append(thread_local)
            entry = _fetch_tile(tile[0], tile[1], thread_local)
            return entry.get("panos") or []

        completed = 0
        total = len(self._tiles)
        try:
            with ThreadPoolExecutor(max_workers=_APPLE_MAX_WORKERS) as pool:
                futures = {pool.submit(worker, t): t for t in self._tiles}
                for fut in as_completed(futures):
                    if self.isCanceled():
                        for f in futures:
                            f.cancel()
                        return False
                    try:
                        self._coords.extend(fut.result())
                    except RateLimited:
                        self._rate_limited = True
                        for f in futures:
                            f.cancel()
                        break
                    except Exception as exc:
                        QgsMessageLog.logMessage(
                            f"Apple coverage worker error: {exc!r}", _LOG_TAG
                        )
                    completed += 1
                    self.setProgress(100.0 * completed / total)
        finally:
            for tl in all_locals:
                _close_connection(tl)

        if self._rate_limited:
            self.error_message = tr(
                "Look Around: too many requests to lookmap.eu — "
                "please wait a moment and try again."
            )
            return False
        return True

    def finished(self, result: bool) -> None:
        # Runs on the main (GUI) thread.
        from .coverage_layer import _remove_layer  # local to avoid import cycle

        if self.isCanceled():
            return
        if not result:
            if self.error_message:
                self._iface.messageBar().pushWarning(tr("Look Around"), self.error_message)
            return

        name = layer_name_apple()
        _remove_layer(name)

        if not self._coords:
            self._iface.messageBar().pushInfo(
                tr("Look Around"),
                tr("No Look Around coverage found in the current extent."),
            )
            return

        layer = QgsVectorLayer("Point?crs=EPSG:4326", name, "memory")
        provider = layer.dataProvider()
        feats = []
        for lat, lon in self._coords:
            f = QgsFeature()
            f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(lon, lat)))
            feats.append(f)
        provider.addFeatures(feats)
        layer.updateExtents()

        sym = layer.renderer().symbol()
        sym.setColor(QColor(0, 180, 0))
        sym.setSize(2.0)
        layer.setOpacity(0.5)

        project = QgsProject.instance()
        root = project.layerTreeRoot()
        project.addMapLayer(layer, False)
        # Insert below the Google raster (which sits at index 0); fall back
        # to the top if Google is absent.
        google_name = tr("Street View Coverage")
        insert_at = 1 if project.mapLayersByName(google_name) else 0
        root.insertLayer(insert_at, layer)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def start_apple_coverage(iface, tile_limit: int) -> tuple[AppleCoverageTask | None, str | None]:
    """Compute tiles for the current canvas extent and dispatch a background task.

    Returns ``(task, None)`` on success or ``(None, error)`` if the extent is
    too wide for the configured tile limit.
    """
    canvas = iface.mapCanvas()
    crs_wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
    transform = QgsCoordinateTransform(
        QgsProject.instance().crs(), crs_wgs84, QgsProject.instance()
    )
    ext = transform.transformBoundingBox(canvas.extent())

    tiles = _extent_to_tiles(
        ext.yMinimum(), ext.yMaximum(),
        ext.xMinimum(), ext.xMaximum(),
        _APPLE_COVERAGE_ZOOM,
    )

    if len(tiles) > tile_limit:
        return None, tr(
            "Look Around: the current extent covers {count} tiles "
            "(maximum {max}) — please zoom in further or change Apple coverage tile limit in settings."
        ).format(count=len(tiles), max=tile_limit)

    task = AppleCoverageTask(iface, tiles)
    QgsApplication.taskManager().addTask(task)
    return task, None
