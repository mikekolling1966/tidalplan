"""Parse GPX files and extract ordered route waypoints."""
import re
import gpxpy
from dataclasses import dataclass


@dataclass
class Waypoint:
    lat: float
    lon: float
    name: str = ""


@dataclass
class Route:
    name: str
    waypoints: list[Waypoint]

    def __len__(self):
        return len(self.waypoints)


def _sanitise_gpx(text: str) -> str:
    """
    Fix common GPX files that use namespace-prefixed elements (e.g. opencpn:guid)
    without declaring the namespace on the root element.  We strip every
    <prefix:tag …> … </prefix:tag> block and self-closing <prefix:tag …/> so
    that the standard XML parser doesn't reject the file.
    """
    # Remove self-closing namespace tags: <opencpn:foo ... />
    text = re.sub(r'<[a-zA-Z_][\w]*:[^>]*/>', '', text)
    # Remove open/close namespace tag pairs (non-greedy, handles nesting badly
    # but extensions blocks are shallow): <opencpn:foo>…</opencpn:foo>
    text = re.sub(r'<([a-zA-Z_][\w]*:[^\s>/]+)[^>]*>.*?</\1>', '', text, flags=re.DOTALL)
    return text


def _regex_fallback(text: str) -> Route:
    """
    Last-resort extraction: pull lat/lon from every trkpt/rtept/wpt attribute
    using a simple regex — identical to the JS frontend preview.
    """
    pattern = re.compile(
        r'(?:trkpt|rtept|wpt)[^>]*lat="([^"]+)"[^>]*lon="([^"]+)"',
        re.IGNORECASE,
    )
    # Also grab name elements that follow each point
    name_pattern = re.compile(r'<name>([^<]*)</name>', re.IGNORECASE)
    names = name_pattern.findall(text)

    wps = []
    for i, m in enumerate(pattern.finditer(text)):
        name = names[i] if i < len(names) else ""
        wps.append(Waypoint(float(m.group(1)), float(m.group(2)), name))

    if len(wps) < 2:
        raise ValueError("GPX file must contain at least 2 waypoints, a route, or a track.")
    return Route(name="Route", waypoints=wps)


def parse_gpx(content: bytes) -> Route:
    """
    Parse GPX bytes and return the first route or track found.
    Falls back to waypoints if no route/track present.

    Strategy:
      1. Try gpxpy on the raw text (handles well-formed GPX fastest).
      2. If that fails, strip undeclared namespace elements and retry gpxpy.
      3. If still failing, fall back to regex extraction (handles any GPX).
    """
    text = content.decode("utf-8", errors="replace")

    for attempt, source in enumerate([text, _sanitise_gpx(text)]):
        try:
            gpx = gpxpy.parse(source)

            # Prefer explicit routes
            for route in gpx.routes:
                wps = [Waypoint(p.latitude, p.longitude, p.name or "") for p in route.points]
                if len(wps) >= 2:
                    return Route(name=route.name or "Route", waypoints=wps)

            # Fall back to first track
            for track in gpx.tracks:
                for seg in track.segments:
                    wps = [Waypoint(p.latitude, p.longitude, p.name or "") for p in seg.points]
                    if len(wps) >= 2:
                        return Route(name=track.name or "Track", waypoints=wps)

            # Fall back to waypoints in file order
            wps = [Waypoint(w.latitude, w.longitude, w.name or "") for w in gpx.waypoints]
            if len(wps) >= 2:
                return Route(name="Waypoints", waypoints=wps)

        except Exception:
            if attempt == 0:
                continue   # try sanitised version next
            # Both gpxpy attempts failed — use regex
            return _regex_fallback(text)

    # gpxpy succeeded but found no points — try regex before giving up
    return _regex_fallback(text)


def route_to_gpx(route: Route) -> str:
    """Export a Route back to GPX string."""
    gpx = gpxpy.gpx.GPX()
    gpx_route = gpxpy.gpx.GPXRoute(name=route.name)
    for wp in route.waypoints:
        gpx_route.points.append(gpxpy.gpx.GPXRoutePoint(wp.lat, wp.lon, name=wp.name))
    gpx.routes.append(gpx_route)
    return gpx.to_xml()
