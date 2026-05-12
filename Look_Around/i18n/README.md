# Translations

The Look Around plugin loads `lookaround_<locale>.qm` from this folder at
startup, where `<locale>` matches the QGIS user interface locale (for example
`de`, `de_DE`, `fr`, `es`).

## Adding a new language

1. Add the new locale to `TRANSLATIONS` in `lookaround.pro`, for example:
   ```
   TRANSLATIONS = lookaround_de.ts lookaround_fr.ts
   ```
2. Run `pylupdate5 lookaround.pro` from this folder. This (re)generates the
   `.ts` files from the Python sources.
3. Open the new `.ts` file in **Qt Linguist** and translate every string.
4. Compile to a binary catalog with `lrelease lookaround_<locale>.ts`. This
   produces `lookaround_<locale>.qm`, which is what the plugin actually loads.

## Updating an existing language

Whenever user-facing strings change in the Python sources, re-run
`pylupdate5 lookaround.pro` to refresh all `.ts` files, edit the new/changed
entries in Qt Linguist, then recompile with `lrelease`.

`pylupdate5` and `lrelease` ship with PyQt5 / Qt; on Debian-based systems
they are in the `pyqt5-dev-tools` and `qttools5-dev-tools` packages.
