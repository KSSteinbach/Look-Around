import os

from qgis.PyQt.QtCore import QCoreApplication, QRectF, QSize, Qt
from qgis.PyQt.QtGui import QColor, QIcon, QPainter, QPixmap
from qgis.PyQt.QtSvg import QSvgRenderer
from qgis.PyQt.QtWidgets import QComboBox
from qgis.core import QgsApplication

# QAction moved from QtWidgets to QtGui in Qt6 (QGIS 4).
try:
    from qgis.PyQt.QtGui import QAction
except ImportError:
    from qgis.PyQt.QtWidgets import QAction

from .i18n import install_translator, tr
from .map_tool import LookAroundMapTool
from .settings_dialog import (
    SERVICE_KEYS,
    SettingsDialog,
    load_apple_tile_limit,
    load_apple_viewer,
    load_default_service,
    load_toolbar_visibility,
)

_PLUGIN_DIR = os.path.dirname(__file__)
_ICONS_DIR = os.path.join(_PLUGIN_DIR, "icons")
_APPLE_SVG = os.path.join(_ICONS_DIR, "apple.svg")
_GOOGLE_SVG = os.path.join(_ICONS_DIR, "google.svg")
_ICON_SIZE = 20
_GOOGLE_SIZE = round(_ICON_SIZE * 0.85)  # ~17 px, centered vertically
_GOOGLE_OFFSET = (_ICON_SIZE - _GOOGLE_SIZE) / 2

# =============================================================================
# Stellschrauben für das kombinierte "Apple + Google"-Logo im Dropdown ("both")
# -----------------------------------------------------------------------------
# Alle Werte sind Pixel (außer _BOTH_LOGO_SCALE = Faktor).
# Nach Änderungen reicht ein QGIS-Reload des Plugins.
# =============================================================================

# (1) GRÖSSE -----------------------------------------------------------------
# Skalierung der Einzel-Logos im Kombi-Icon, relativ zu ihrer Originalgröße.
# 1.00 = Originalgröße, 0.80 = 20 % kleiner (Standard).
_BOTH_LOGO_SCALE = 0.80

# (2) ÜBERLAGERUNG -----------------------------------------------------------
# Wie weit sich Apple- und Google-Logo horizontal ineinander schieben.
# Größerer Wert = stärkere Überlappung. Negativer Wert = Lücke zwischen den Logos.
_BOTH_OVERLAP = 6

# (3) HÖHENVERSATZ -----------------------------------------------------------
# Vertikaler Versatz der beiden Logos gegeneinander.
# Apple wird um diesen Wert nach OBEN, Google um denselben Wert nach UNTEN
# verschoben. 0 = beide auf gleicher Höhe.
_BOTH_V_OFFSET = 2

# (4) POSITION & DARSTELLUNG des verbindenden "+" ----------------------------
# Horizontale Verschiebung des "+" gegenüber der Bild-Mitte (positiv = rechts).
_BOTH_PLUS_DX = 0
# Vertikale Verschiebung des "+" gegenüber der Bild-Mitte (positiv = unten).
_BOTH_PLUS_DY = 0
# Größe des "+" in Pixeln (Länge der horizontalen/vertikalen Balken).
_BOTH_PLUS_SIZE = 9
# Strichstärke des "+" in Pixeln (Breite der Balken).
# Vorher war das "+" ein Font-Glyph mit setBold(True); damit ist die
# maximale Stärke durch die Schrift begrenzt. Jetzt werden zwei
# gefüllte Rechtecke gezeichnet – beliebig dick einstellbar.
_BOTH_PLUS_THICKNESS = 3
# Farbe des "+" als HTML/CSS-Farbcode. Standard: kräftiges Blau ("DodgerBlue" #1E90FF).
_BOTH_PLUS_COLOR = "#0694ff"


def _both_logo_sizes() -> tuple[int, int]:
    """Effektive Pixelgrößen von Apple- und Google-Logo im Kombi-Icon."""
    apple = max(1, round(_ICON_SIZE * _BOTH_LOGO_SCALE))
    google = max(1, round(_GOOGLE_SIZE * _BOTH_LOGO_SCALE))
    return apple, google


def _both_canvas_size() -> QSize:
    """Größe der Pixmap für das Kombi-Icon (= benötigte iconSize der ComboBox)."""
    apple, google = _both_logo_sizes()
    width = apple + google - _BOTH_OVERLAP
    # Höhe muss den Höhenversatz auf beiden Seiten aufnehmen:
    height = _ICON_SIZE + 2 * abs(_BOTH_V_OFFSET)
    return QSize(max(1, width), max(1, height))


def _svg_icon(path: str, size: int = _ICON_SIZE) -> QIcon:
    # Alle Combo-Items werden in dieselbe Canvas-Größe gerendert wie das
    # "both"-Icon, damit die ComboBox-iconSize konsistent ist und die
    # Einzel-Logos nicht durch Qt verkleinert werden.
    canvas = _both_canvas_size()
    px = QPixmap(canvas)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    x = (canvas.width() - size) / 2
    y = (canvas.height() - size) / 2
    QSvgRenderer(path).render(p, QRectF(x, y, size, size))
    p.end()
    return QIcon(px)


def _both_icon() -> QIcon:
    canvas = _both_canvas_size()
    apple_size, google_size = _both_logo_sizes()

    px = QPixmap(canvas)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    cx = canvas.width() / 2
    cy = canvas.height() / 2

    # --- Apple-Logo (links, nach oben versetzt) ---------------------------
    apple_x = 0
    apple_y = cy - apple_size / 2 - _BOTH_V_OFFSET  # (3) Höhenversatz
    QSvgRenderer(_APPLE_SVG).render(p, QRectF(apple_x, apple_y, apple_size, apple_size))

    # --- Google-Logo (rechts, nach unten versetzt, mit Überlappung) -------
    google_x = apple_size - _BOTH_OVERLAP             # (2) Überlagerung
    google_y = cy - google_size / 2 + _BOTH_V_OFFSET  # (3) Höhenversatz
    QSvgRenderer(_GOOGLE_SVG).render(p, QRectF(google_x, google_y, google_size, google_size))

    # --- Verbindendes "+" mittig zwischen den Logos -----------------------
    # Als zwei gefüllte Rechtecke gezeichnet – Strichstärke frei via
    # _BOTH_PLUS_THICKNESS einstellbar.
    plus_cx = cx + _BOTH_PLUS_DX              # (4) Plus-Position X
    plus_cy = cy + _BOTH_PLUS_DY              # (4) Plus-Position Y
    half_len = _BOTH_PLUS_SIZE / 2
    half_thick = _BOTH_PLUS_THICKNESS / 2
    plus_color = QColor(_BOTH_PLUS_COLOR)
    # Horizontaler Balken
    p.fillRect(
        QRectF(plus_cx - half_len, plus_cy - half_thick,
               _BOTH_PLUS_SIZE, _BOTH_PLUS_THICKNESS),
        plus_color,
    )
    # Vertikaler Balken
    p.fillRect(
        QRectF(plus_cx - half_thick, plus_cy - half_len,
               _BOTH_PLUS_THICKNESS, _BOTH_PLUS_SIZE),
        plus_color,
    )
    p.end()
    return QIcon(px)


class LookAroundPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.toolbar = None
        self.action = None
        self.action_menu = None
        self.coverage_action = None
        self.coverage_menu_action = None
        self.settings_action = None
        self.settings_tb_action = None
        self.combo = None
        self.combo_action = None
        self.map_tool = None
        self._translator = None
        self._apple_task = None

    def initGui(self):
        self._translator = install_translator()

        icon_path = os.path.join(_ICONS_DIR, "icon_Tool.svg")
        icon_path_cov = os.path.join(_ICONS_DIR, "icon_CovLayers.svg")
        icon_path_settings = os.path.join(_ICONS_DIR, "icon_Settings.svg")

        self.action = QAction(QIcon(icon_path), tr("Look Around"), self.iface.mainWindow())
        self.action.setCheckable(True)
        self.action.setToolTip(tr("Click on the map to open Street View / Look Around"))
        self.action.triggered.connect(self._toggle_tool)

        self.coverage_action = QAction(
            QIcon(icon_path_cov), tr("Show coverage"), self.iface.mainWindow()  # set to second Icon path
        )
        self.coverage_action.setCheckable(True)
        self.coverage_action.setToolTip(
            tr("Show coverage layers: Street View (blue) and Look Around (green)")
        )
        self.coverage_action.triggered.connect(self._toggle_coverage)

        self.settings_action = QAction(
            tr("Look Around Settings…"), self.iface.mainWindow()
        )
        self.settings_action.triggered.connect(self._open_settings)

        # Plugin-eigenes Icon, falls vorhanden; sonst QGIS-Theme-Zahnrad als Fallback.
        if os.path.exists(icon_path_settings):
            icon_settings = QIcon(icon_path_settings)
        else:
            icon_settings = QgsApplication.getThemeIcon("mActionOptions.svg")
        self.settings_tb_action = QAction(
            icon_settings, tr("Look Around Settings…"), self.iface.mainWindow()
        )
        self.settings_tb_action.triggered.connect(self._open_settings)

        self.combo = QComboBox()
        self.combo.setToolTip(tr("Select service"))
        self.combo.addItem(_svg_icon(_APPLE_SVG), "", "apple")
        self.combo.addItem(_svg_icon(_GOOGLE_SVG, _GOOGLE_SIZE), "", "google")
        self.combo.addItem(_both_icon(), "", "both")
        self.combo.setItemData(0, tr("Apple Look Around"), Qt.ItemDataRole.ToolTipRole)
        self.combo.setItemData(1, tr("Google Street View"), Qt.ItemDataRole.ToolTipRole)
        self.combo.setItemData(2, tr("Both"), Qt.ItemDataRole.ToolTipRole)

        self.toolbar = self.iface.addToolBar(tr("Look Around"))
        self.toolbar.setObjectName("LookAroundToolBar")
        self.toolbar.addAction(self.action)
        self.combo_action = self.toolbar.addWidget(self.combo)
        self.toolbar.addAction(self.coverage_action)
        self.toolbar.addAction(self.settings_tb_action)

        # Combo-Höhe exakt auf Toolbar-Icon-Höhe schrumpfen. Breite, Rahmen
        # und Dropdown-Pfeil bleiben unverändert / Standard.
        self.combo.setIconSize(_both_canvas_size())
        self.combo.setFixedHeight(self.toolbar.iconSize().height())

        # Separate Menü-Actions, damit das Ausblenden in der Toolbar via
        # action.setVisible(False) den Menüeintrag nicht mit ausblendet.
        self.action_menu = QAction(QIcon(icon_path), tr("Look Around"), self.iface.mainWindow())
        self.action_menu.setCheckable(True)
        self.action_menu.setToolTip(self.action.toolTip())
        self.action_menu.triggered.connect(self.action.trigger)
        self.action.toggled.connect(self.action_menu.setChecked)

        self.coverage_menu_action = QAction(
            QIcon(icon_path_cov), tr("Show coverage"), self.iface.mainWindow()
        )
        self.coverage_menu_action.setCheckable(True)
        self.coverage_menu_action.setToolTip(self.coverage_action.toolTip())
        self.coverage_menu_action.triggered.connect(self.coverage_action.trigger)
        self.coverage_action.toggled.connect(self.coverage_menu_action.setChecked)

        self.iface.addPluginToMenu("Look Around", self.action_menu)
        self.iface.addPluginToMenu("Look Around", self.coverage_menu_action)
        self.iface.addPluginToMenu("Look Around", self.settings_action)

        self.map_tool = LookAroundMapTool(
            self.iface.mapCanvas(),
            self._get_service,
            load_apple_viewer,
        )
        self.map_tool.setAction(self.action)

        self._apply_toolbar_visibility()

    def unload(self):
        from .coverage_layer import remove_coverage_layers
        self._cancel_apple_task()
        remove_coverage_layers()
        self.iface.removePluginMenu("Look Around", self.action_menu)
        self.iface.removePluginMenu("Look Around", self.coverage_menu_action)
        self.iface.removePluginMenu("Look Around", self.settings_action)
        if self.toolbar:
            self.toolbar.deleteLater()
            self.toolbar = None
        if self._translator is not None:
            QCoreApplication.removeTranslator(self._translator)
            self._translator = None

    def _toggle_tool(self, checked):
        if checked:
            self.iface.mapCanvas().setMapTool(self.map_tool)
        else:
            self.iface.mapCanvas().unsetMapTool(self.map_tool)

    def _toggle_coverage(self, checked):
        from .coverage_layer import add_coverage_layers, remove_coverage_layers
        if checked:
            self._cancel_apple_task()
            task, error = add_coverage_layers(self.iface, load_apple_tile_limit())
            self._apple_task = task
            if error:
                self.iface.messageBar().pushWarning(tr("Look Around"), error)
        else:
            self._cancel_apple_task()
            remove_coverage_layers()
            self.iface.mapCanvas().refresh()

    def _cancel_apple_task(self):
        task = self._apple_task
        self._apple_task = None
        if task is not None:
            try:
                task.cancel()
            except RuntimeError:
                # Task already finished and was deleted by Qt.
                pass

    def _apply_toolbar_visibility(self):
        vis = load_toolbar_visibility()
        # action.setVisible() blendet die Action in der Toolbar zuverlässig aus.
        # Die Menüeinträge nutzen separate Action-Instanzen und bleiben sichtbar.
        self.action.setVisible(vis["tool"])
        self.coverage_action.setVisible(vis["coverage"])
        self.combo_action.setVisible(vis["combo"])
        self.settings_tb_action.setVisible(vis["settings"])

    def _get_service(self) -> str:
        if self.combo_action is not None and self.combo_action.isVisible():
            return self.combo.currentData() or SERVICE_KEYS[self.combo.currentIndex()]
        return load_default_service()

    def _open_settings(self):
        dlg = SettingsDialog(self.iface.mainWindow())
        # exec_() was removed in PyQt6 (QGIS 4); exec() works in both PyQt5 and PyQt6.
        if dlg.exec():
            self._apply_toolbar_visibility()
