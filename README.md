# Look Around – QGIS Plugin

A QGIS plugin that opens the clicked map location directly in
**Apple Look Around** and/or **Google Street View** in your browser.
Optionally, coverage layers for both services can be displayed as an
overlay inside QGIS.

Compatible with **QGIS 3.28+ (PyQt5)** and **QGIS 4 (Qt6 / PyQt6)**.

## Features

- **One-click panoramas**: Activate the tool, click anywhere on the map
  and the chosen service opens instantly in your default browser.
- **Service selector**: Toolbar dropdown to switch between
  *Apple Look Around*, *Google Street View*, or *both at once*.
- **Apple Look Around viewer options**:
  - `lookmap.eu` — open-source viewer by
    [sk-zk/lookaround-map](https://github.com/sk-zk/lookaround-map),
    works on all platforms, jumps directly into the panorama *(default)*
  - Apple Maps Web (`maps.apple.com`)
  - Native Maps app (macOS only)
- **Coverage layers**:
  - Google Street View blue-line raster tiles
  - Apple Look Around green point layer (via lookmap.eu public API),
    fetched in the background with a two-tier (memory + disk) cache so
    the GUI stays responsive
- **Configurable Apple tile limit**: Set the maximum number of Look
  Around coverage tiles fetched per refresh in the settings dialog.
- **Customisable toolbar**: Each toolbar element (tool button, service
  dropdown, coverage button, settings button) can be shown or hidden
  individually via the settings dialog.
- **Multilingual**: German translation included (Qt Linguist).

## Notes & limitations

- Apple Look Around is not available through an official public API.
  The plugin uses the open-source viewer
  [lookmap.eu](https://lookmap.eu.pythonanywhere.com/)
  (sk-zk/lookaround-map). If you receive a rate-limit error (HTTP 429),
  wait a moment and try again.
- The Apple coverage layer is capped at the configured tile limit
  (default 64) per request. If the current map extent exceeds the
  limit, zoom in further or raise the limit in the settings dialog.
- Google Street View coverage is loaded via unofficial XYZ tiles;
  availability may change on Google's side at any time.

## Installation

### From the QGIS Plugin Repository

Once published: *Plugins → Manage and Install Plugins…* → search for
*Look Around* → *Install*.

### From a ZIP release

1. Download the latest ZIP from the
   [Releases page](https://github.com/KSSteinbach/Look-around/releases).
2. In QGIS: *Plugins → Manage and Install Plugins → Install from ZIP*
   → select the file.

### From source

1. Clone the repository.
2. Copy or symlink the `Look_Around/` folder into the QGIS plugin
   directory:
   - **Linux**: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
   - **macOS**: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`
   - **Windows**: `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\`
3. Restart QGIS and enable the plugin in the Plugin Manager.

## Usage

1. Enable the plugin — the *Look Around* toolbar appears.
2. Select the desired service in the dropdown (Apple, Google or both).
3. Click the binoculars tool button, then click a location on the map.
4. The panorama opens automatically in your browser.
5. Optionally, click the coverage button to display which areas have
   available panoramas before you click.

## Settings

Open the settings dialog via the gear icon in the toolbar or via
*Plugins → Look Around → Look Around Settings…*:

| Setting | Description |
|---|---|
| **Default service** | Service used when the toolbar dropdown is hidden |
| **Apple Look Around viewer** | Selects the viewer used for Apple panoramas |
| **Apple coverage tile limit** | Maximum tiles fetched per coverage refresh (16–512) |
| **Toolbar** | Show/hide individual toolbar elements |

Settings are stored persistently via `QSettings`.

## Project structure

```
Look_Around/                Plugin root (copy into the QGIS plugins directory)
├── __init__.py             QGIS entry point (classFactory)
├── metadata.txt            QGIS plugin metadata
├── look_around.py          Main plugin class (GUI, toolbar)
├── map_tool.py             Map tool: click handling and cursor
├── settings_dialog.py      Settings dialog and settings loaders
├── coverage_layer.py       Coverage layers (Google XYZ + Apple dispatch)
├── apple_coverage.py       Apple coverage: parallel fetch, cache, QgsTask
├── url_builder.py          URL builders for Apple and Google viewers
├── i18n.py                 Translation helpers
├── icons/                  Images and SVGs
│   ├── icon_Tool.svg       Plugin icon
│   ├── icon_CovLayers.svg  Coverage toolbar icon
│   ├── icon_Settings.svg   Settings toolbar icon
│   ├── apple.svg           Apple logo (dropdown)
│   ├── google.svg          Google logo (dropdown)
│   └── binoculars.svg      Cursor symbol
└── i18n/                   Translations
    ├── lookaround.pro      pylupdate project file
    ├── lookaround_de.ts    German translation source (Qt Linguist)
    └── lookaround_de.qm    Compiled German message catalog
```

## Translations

`.ts` files are edited with Qt Linguist and compiled to `.qm` with
`lrelease`. Run the commands from inside the `Look_Around/` folder:

```bash
pylupdate5 i18n/lookaround.pro      # update .ts from source
lrelease   i18n/lookaround_de.ts    # compile .ts to .qm
```

At runtime, `i18n.install_translator()` loads the `.qm` file matching
the active QGIS locale.

## License

See [LICENSE](LICENSE).

## Credits

- Apple Look Around viewer: [sk-zk/lookaround-map](https://github.com/sk-zk/lookaround-map)
- Binoculars, Google and Apple icons by [Icons8](https://icons8.com/)
