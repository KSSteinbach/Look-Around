"""Translation helpers for the Look Around plugin.

All user-facing strings are routed through :func:`tr` so that they can be
extracted with ``pylupdate5`` and translated with Qt Linguist. See
``i18n/lookaround.pro`` for the list of source files.
"""

import os

from qgis.PyQt.QtCore import QCoreApplication, QLocale, QSettings, QTranslator

_PLUGIN_DIR = os.path.dirname(__file__)
_I18N_DIR = os.path.join(_PLUGIN_DIR, "i18n")
_CONTEXT = "@default"


def tr(message: str) -> str:
    """Translate ``message`` using the ``LookAround`` translation context."""
    return QCoreApplication.translate(_CONTEXT, message)


def install_translator() -> QTranslator | None:
    """Install the .qm translation matching the current QGIS/UI locale.

    Returns the installed :class:`QTranslator` so the caller can keep a
    reference and remove it again on ``unload``.
    """
    locale = (
        QSettings().value("locale/userLocale")
        or QLocale.system().name()
        or "en"
    )
    # Accept both full ("de_DE") and short ("de") locale codes.
    candidates = [locale, locale.split("_")[0]]

    translator = QTranslator()
    for code in candidates:
        qm_path = os.path.join(_I18N_DIR, f"lookaround_{code}.qm")
        if os.path.exists(qm_path) and translator.load(qm_path):
            QCoreApplication.installTranslator(translator)
            return translator
    return None
