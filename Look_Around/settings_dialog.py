from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QComboBox,
    QGroupBox,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)
from qgis.PyQt.QtCore import QSettings

from .i18n import tr

SETTINGS_KEY_APPLE_VIEWER = "lookaround/apple_viewer"

# Internal viewer keys are kept untranslated. Labels are produced lazily so
# they always reflect the active translation.
APPLE_VIEWER_KEYS = ["lookmap", "web", "native"]

# Service keys shared with look_around.py (imported from here to avoid circular imports).
SERVICE_KEYS = ["apple", "google", "both"]

SETTINGS_KEY_DEFAULT_SERVICE = "lookaround/default_service"
SETTINGS_KEY_SHOW_TOOL = "lookaround/toolbar_show_tool"
SETTINGS_KEY_SHOW_COMBO = "lookaround/toolbar_show_combo"
SETTINGS_KEY_SHOW_COVERAGE = "lookaround/toolbar_show_coverage"
SETTINGS_KEY_SHOW_SETTINGS_TB = "lookaround/toolbar_show_settings_tb"
SETTINGS_KEY_APPLE_TILE_LIMIT = "lookaround/apple_tile_limit"

_APPLE_TILE_LIMIT_DEFAULT = 64
_APPLE_TILE_LIMIT_MIN = 16
_APPLE_TILE_LIMIT_MAX = 512
_APPLE_TILE_LIMIT_STEP = 16


def _apple_viewer_labels() -> list[str]:
    return [
        tr("lookmap.eu (recommended, all platforms)"),
        tr("Apple Maps Web (maps.apple.com)"),
        tr("Native Maps app (macOS only)"),
    ]


def _service_labels() -> list[str]:
    return [tr("Apple Look Around"), tr("Google Street View"), tr("Both")]


def load_apple_viewer() -> str:
    return QSettings().value(SETTINGS_KEY_APPLE_VIEWER, "lookmap")


def load_default_service() -> str:
    return QSettings().value(SETTINGS_KEY_DEFAULT_SERVICE, "apple")


def load_apple_tile_limit() -> int:
    raw = QSettings().value(SETTINGS_KEY_APPLE_TILE_LIMIT, _APPLE_TILE_LIMIT_DEFAULT)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = _APPLE_TILE_LIMIT_DEFAULT
    return max(_APPLE_TILE_LIMIT_MIN, min(_APPLE_TILE_LIMIT_MAX, value))


def load_toolbar_visibility() -> dict:
    s = QSettings()
    return {
        "tool":     s.value(SETTINGS_KEY_SHOW_TOOL,        True, type=bool),
        "combo":    s.value(SETTINGS_KEY_SHOW_COMBO,       True, type=bool),
        "coverage": s.value(SETTINGS_KEY_SHOW_COVERAGE,    True, type=bool),
        "settings": s.value(SETTINGS_KEY_SHOW_SETTINGS_TB, True, type=bool),
    }


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Look Around – Settings"))
        self.setMinimumWidth(420)

        outer = QVBoxLayout(self)

        form = QFormLayout()
        outer.addLayout(form)

        self._service_combo = QComboBox()
        for label in _service_labels():
            self._service_combo.addItem(label)
        current_service = load_default_service()
        if current_service in SERVICE_KEYS:
            self._service_combo.setCurrentIndex(SERVICE_KEYS.index(current_service))
        form.addRow(QLabel(tr("Default service:")), self._service_combo)

        self._apple_combo = QComboBox()
        for label in _apple_viewer_labels():
            self._apple_combo.addItem(label)
        current_viewer = load_apple_viewer()
        if current_viewer in APPLE_VIEWER_KEYS:
            self._apple_combo.setCurrentIndex(APPLE_VIEWER_KEYS.index(current_viewer))
        form.addRow(QLabel(tr("Apple Look Around viewer:")), self._apple_combo)

        hint = QLabel(self.tr(
            "[Apple Maps Web] and [Native Maps app] won't open Look Around view automatically.\n"
            "Manually push the Look Around button in the Browser/App."))
        hint.setStyleSheet("color: grey; font-size: 10px;")
        form.addRow(hint)

        self._apple_tile_limit = QSpinBox()
        self._apple_tile_limit.setRange(_APPLE_TILE_LIMIT_MIN, _APPLE_TILE_LIMIT_MAX)
        self._apple_tile_limit.setSingleStep(_APPLE_TILE_LIMIT_STEP)
        self._apple_tile_limit.setValue(load_apple_tile_limit())
        self._apple_tile_limit.setToolTip(
            tr(
                "Maximum number of Look Around coverage tiles fetched per refresh. "
                "Higher values cover larger extents but take longer and may hit "
                "lookmap.eu rate limits."
            )
        )
        form.addRow(QLabel(tr("Apple coverage tile limit:")), self._apple_tile_limit)

        hint = QLabel(self.tr(
            "Higher values cover larger extents but take longer.\n"))
        hint.setStyleSheet("color: grey; font-size: 10px;")
        form.addRow(hint)

        group = QGroupBox(tr("Toolbar"))
        group_layout = QVBoxLayout(group)
        self._cb_tool = QCheckBox(tr("Look Around tool"))
        self._cb_combo = QCheckBox(tr("Service selection"))
        self._cb_coverage = QCheckBox(tr("Coverage layers"))
        self._cb_settings = QCheckBox(tr("Settings"))
        group_layout.addWidget(self._cb_tool)
        group_layout.addWidget(self._cb_combo)
        group_layout.addWidget(self._cb_coverage)
        group_layout.addWidget(self._cb_settings)
        outer.addWidget(group)

        vis = load_toolbar_visibility()
        self._cb_tool.setChecked(vis["tool"])
        self._cb_combo.setChecked(vis["combo"])
        self._cb_coverage.setChecked(vis["coverage"])
        self._cb_settings.setChecked(vis["settings"])
        self._cb_combo.setEnabled(vis["tool"])
        self._cb_tool.toggled.connect(self._on_tool_toggled)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save_and_accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def _on_tool_toggled(self, checked: bool):
        self._cb_combo.setEnabled(checked)
        if not checked:
            self._cb_combo.setChecked(False)

    def _save_and_accept(self):
        s = QSettings()
        idx = self._apple_combo.currentIndex()
        s.setValue(SETTINGS_KEY_APPLE_VIEWER,    APPLE_VIEWER_KEYS[idx])
        s.setValue(SETTINGS_KEY_DEFAULT_SERVICE,  SERVICE_KEYS[self._service_combo.currentIndex()])
        s.setValue(SETTINGS_KEY_SHOW_TOOL,        self._cb_tool.isChecked())
        s.setValue(SETTINGS_KEY_SHOW_COMBO,       self._cb_combo.isChecked())
        s.setValue(SETTINGS_KEY_SHOW_COVERAGE,    self._cb_coverage.isChecked())
        s.setValue(SETTINGS_KEY_SHOW_SETTINGS_TB, self._cb_settings.isChecked())
        s.setValue(SETTINGS_KEY_APPLE_TILE_LIMIT,  self._apple_tile_limit.value())
        self.accept()
