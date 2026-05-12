from qgis.core import (
    QgsMessageLog,
    QgsProject,
    QgsRasterLayer,
)

from .apple_coverage import AppleCoverageTask, layer_name_apple, start_apple_coverage
from .i18n import tr


def layer_name_google() -> str:
    return tr("Street View Coverage")


# Google Street View blue-line coverage XYZ tiles. The `style=40,18`
# query argument is what actually triggers rendering of the blue lines
# (without it, mts2.google.com returns blank tiles). Pattern matches
# saccon/streetview-plugin, which is known to work in the wild.
_GOOGLE_TILE_URL = (
    "https://mts2.google.com/mapslt?"
    "lyrs=svv&x={x}&y={y}&z={z}&w=256&h=256&hl=en&style=40,18"
)


def add_coverage_layers(iface, tile_limit: int) -> tuple[AppleCoverageTask | None, str | None]:
    """Add Google (raster) immediately and dispatch Apple (vector) as a task.

    Returns the running Apple task (or ``None``) and any user-visible error
    string aggregated across both layers.
    """
    errors: list[str] = []

    google_layer, err = _create_google_layer()
    if err:
        errors.append(err)

    project = QgsProject.instance()
    root = project.layerTreeRoot()
    if google_layer:
        project.addMapLayer(google_layer, False)
        root.insertLayer(0, google_layer)

    task, apple_err = start_apple_coverage(iface, tile_limit)
    if apple_err:
        errors.append(apple_err)

    return task, ("\n".join(errors) if errors else None)


def remove_coverage_layers() -> None:
    """Remove both coverage layers from the project."""
    _remove_layer(layer_name_google())
    _remove_layer(layer_name_apple())


def coverage_layers_exist() -> bool:
    project = QgsProject.instance()
    return bool(
        project.mapLayersByName(layer_name_google())
        or project.mapLayersByName(layer_name_apple())
    )


# ---------------------------------------------------------------------------
# Google
# ---------------------------------------------------------------------------

def _create_google_layer() -> tuple[QgsRasterLayer | None, str | None]:
    name = layer_name_google()
    _remove_layer(name)
    # The tile URL contains `&` and `=`, which conflict with the WMS URI's
    # own `key=value&key=value` syntax. Escape only those two characters;
    # leave `{x}/{y}/{z}` literal so the XYZ provider can still substitute
    # tile coordinates. The trailing `http-header:referer=` is a QGIS WMS
    # directive that sends an empty Referer header — Google occasionally
    # returns empty tiles otherwise. zmax=18 matches Google's coverage.
    url_for_uri = _GOOGLE_TILE_URL.replace("&", "%26").replace("=", "%3D")
    uri = f"type=xyz&url={url_for_uri}&zmin=0&zmax=18&http-header:referer="
    QgsMessageLog.logMessage(f"Street View XYZ URI: {uri}", "Look Around")
    layer = QgsRasterLayer(uri, name, "wms")
    if not layer.isValid():
        QgsMessageLog.logMessage(
            f"Street View layer invalid. Provider error: {layer.error().summary()}",
            "Look Around",
        )
        return None, tr("The Google coverage layer could not be loaded.")
    layer.setOpacity(0.8)
    return layer, None


def _remove_layer(name: str) -> None:
    for layer in QgsProject.instance().mapLayersByName(name):
        QgsProject.instance().removeMapLayer(layer.id())
