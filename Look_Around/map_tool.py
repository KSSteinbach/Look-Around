import os
import webbrowser

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProject,
)
from qgis.gui import QgsMapTool
from qgis.PyQt.QtCore import QPoint, QRectF, Qt
from qgis.PyQt.QtGui import QColor, QCursor, QPainter, QPixmap
from qgis.PyQt.QtSvg import QSvgRenderer

from .url_builder import apple_look_around_url, google_street_view_url

_PLUGIN_DIR = os.path.dirname(__file__)
_BINOCULARS_SVG = os.path.join(_PLUGIN_DIR, "icons", "binoculars.svg")

# Cursor geometry (logical pixels). The hotspot — i.e. the actual click
# position — sits inside the dot in the top-left; the binoculars are an
# unobtrusive indicator next to it.
_CURSOR_SIZE = 32  # cursor pixmap size (32 x 32 px)
_HOTSPOT = QPoint(6, 6)  # actual click position (6 px right / down from 0,0)
_DOT_OUTER_RADIUS = 6   # white halo, for visibility on dark backgrounds
_DOT_INNER_RADIUS = 3   # black core, marks the actual click point
_BINOCULARS_RECT = QRectF(8, 8, 24, 24)  # binoculars symbol: offset 8/8, 24x24 px


def _build_cursor() -> QCursor:
    pixmap = QPixmap(_CURSOR_SIZE, _CURSOR_SIZE)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    if os.path.exists(_BINOCULARS_SVG):
        QSvgRenderer(_BINOCULARS_SVG).render(painter, _BINOCULARS_RECT)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("white"))
    painter.drawEllipse(_HOTSPOT, _DOT_OUTER_RADIUS, _DOT_OUTER_RADIUS)
    painter.setBrush(QColor("black"))
    painter.drawEllipse(_HOTSPOT, _DOT_INNER_RADIUS, _DOT_INNER_RADIUS)

    painter.end()
    return QCursor(pixmap, _HOTSPOT.x(), _HOTSPOT.y())


class LookAroundMapTool(QgsMapTool):
    def __init__(self, canvas, service_getter, apple_viewer_getter):
        super().__init__(canvas)
        self._get_service = service_getter          # callable → 'google'|'apple'|'both'
        self._get_apple_viewer = apple_viewer_getter  # callable → 'lookmap'|'native'|'web'
        self.setCursor(_build_cursor())

    def canvasReleaseEvent(self, event):
        point = self.toMapCoordinates(event.pos())
        wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
        transform = QgsCoordinateTransform(
            QgsProject.instance().crs(), wgs84, QgsProject.instance()
        )
        p = transform.transform(point)
        lat, lon = p.y(), p.x()

        service = self._get_service()
        if service in ("google", "both"):
            webbrowser.open(google_street_view_url(lat, lon))
        if service in ("apple", "both"):
            webbrowser.open(apple_look_around_url(lat, lon, self._get_apple_viewer()))
