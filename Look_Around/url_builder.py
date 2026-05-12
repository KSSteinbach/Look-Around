import sys


def google_street_view_url(lat: float, lon: float) -> str:
    return (
        f"https://www.google.com/maps/@?api=1&map_action=pano"
        f"&viewpoint={lat},{lon}&heading=0&pitch=0&fov=75"
    )


def apple_look_around_url(lat: float, lon: float, viewer: str = "lookmap") -> str:
    """
    viewer:
      'lookmap' – open-source viewer (sk-zk/lookaround-map), all platforms,
                  jumps directly into the Look Around panorama
      'native'  – maps:// protocol (macOS only), falls back to web on other OS
      'web'     – maps.apple.com, all platforms (user must click binoculars)
    """
    if viewer == "lookmap":
        return (
            f"https://lookmap.eu.pythonanywhere.com/"
            f"#c=18/{lat:.6f}/{lon:.6f}&p={lat:.6f}/{lon:.6f}"
        )
    if viewer == "native" and sys.platform == "darwin":
        return f"maps://?ll={lat},{lon}&z=18"
    return f"https://maps.apple.com/?ll={lat},{lon}&z=18"
