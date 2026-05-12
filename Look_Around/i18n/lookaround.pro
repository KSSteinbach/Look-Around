# Qt Linguist project file for the Look Around plugin.
#
# Regenerate translation source files (.ts) with:
#     pylupdate5 i18n/lookaround.pro
# Compile binary message catalogs (.qm) with:
#     lrelease i18n/lookaround_<locale>.ts
#
# The plugin loads i18n/lookaround_<locale>.qm at startup, picking the locale
# configured in QGIS' Settings -> Options -> General -> User interface.

SOURCES = ../look_around.py \
          ../coverage_layer.py \
          ../map_tool.py \
          ../settings_dialog.py \
          ../apple_coverage.py \
          ../i18n.py

TRANSLATIONS = lookaround_de.ts
