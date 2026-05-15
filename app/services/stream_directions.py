"""
Tidal stream direction and speed data for UK coastal stations.

Sources: Admiralty Tidal Stream Atlases NP249 (Thames Estuary), NP250 (English
Channel Eastern), NP251 (North Sea Southern), NP233 (Dover Strait), and
VisitMyHarbour articles derived from those atlases.

Each entry: {
    flood_direction  – degrees True the stream flows when tide is rising
    ebb_direction    – degrees True the stream flows when tide is falling
    spring_range_m   – approx MHWS-MLWS tidal range in metres
    spring_max_knots – approx maximum spring tidal stream speed in knots
}

Lookup is done by lowercased partial-match on station name.
Keys are listed longest/most-specific first so a more precise match wins.
"""

# fmt: off
STREAM_DATA: list[tuple[str, dict]] = [

    # ── Thames (inner river) ──────────────────────────────────────────────
    ("london bridge",       dict(flood_direction=290, ebb_direction=110, spring_range_m=6.8, spring_max_knots=0.8)),
    ("woolwich",            dict(flood_direction=290, ebb_direction=110, spring_range_m=6.2, spring_max_knots=1.0)),
    ("erith",               dict(flood_direction=285, ebb_direction=105, spring_range_m=6.0, spring_max_knots=1.2)),
    ("gravesend",           dict(flood_direction=275, ebb_direction=95, spring_range_m=5.8, spring_max_knots=1.5)),
    ("tilbury",             dict(flood_direction=280, ebb_direction=100, spring_range_m=5.8, spring_max_knots=1.5)),
    ("leigh-on-sea",        dict(flood_direction=270, ebb_direction=90, spring_range_m=5.0, spring_max_knots=1.5)),
    ("leigh on sea",        dict(flood_direction=270, ebb_direction=90, spring_range_m=5.0, spring_max_knots=1.5)),
    ("southend",            dict(flood_direction=270, ebb_direction=90, spring_range_m=5.0, spring_max_knots=1.5)),

    # ── Medway ────────────────────────────────────────────────────────────
    ("rochester",           dict(flood_direction=265, ebb_direction=85, spring_range_m=5.3, spring_max_knots=1.2)),
    ("chatham",             dict(flood_direction=270, ebb_direction=90, spring_range_m=5.4, spring_max_knots=1.5)),
    ("sheerness",           dict(flood_direction=270, ebb_direction=90, spring_range_m=5.8, spring_max_knots=2.0)),

    # ── Thames outer / Essex rivers ───────────────────────────────────────
    ("burnham-on-crouch",   dict(flood_direction=260, ebb_direction=80, spring_range_m=5.0, spring_max_knots=1.5)),
    ("burnham on crouch",   dict(flood_direction=260, ebb_direction=80, spring_range_m=5.0, spring_max_knots=1.5)),
    ("shoeburyness",        dict(flood_direction=270, ebb_direction=90, spring_range_m=5.0, spring_max_knots=1.5)),
    ("maplin",              dict(flood_direction=270, ebb_direction=90, spring_range_m=4.8, spring_max_knots=1.5)),
    ("brightlingsea",       dict(flood_direction=265, ebb_direction=85, spring_range_m=4.3, spring_max_knots=1.5)),
    ("west mersea",         dict(flood_direction=265, ebb_direction=85, spring_range_m=4.5, spring_max_knots=1.5)),
    ("mersea",              dict(flood_direction=265, ebb_direction=85, spring_range_m=4.5, spring_max_knots=1.5)),
    ("river blackwater",    dict(flood_direction=265, ebb_direction=85, spring_range_m=4.5, spring_max_knots=1.5)),
    ("blackwater",          dict(flood_direction=265, ebb_direction=85, spring_range_m=4.5, spring_max_knots=1.5)),
    ("river colne",         dict(flood_direction=270, ebb_direction=90, spring_range_m=4.3, spring_max_knots=1.5)),

    # ── North Kent coast ──────────────────────────────────────────────────
    ("herne bay",           dict(flood_direction=270, ebb_direction=90, spring_range_m=5.0, spring_max_knots=1.5)),
    ("whitstable",          dict(flood_direction=270, ebb_direction=90, spring_range_m=5.0, spring_max_knots=1.5)),
    ("margate",             dict(flood_direction=290, ebb_direction=110, spring_range_m=4.7, spring_max_knots=3.5)),
    ("broadstairs",         dict(flood_direction=20, ebb_direction=200, spring_range_m=4.7, spring_max_knots=3.0)),
    ("ramsgate",            dict(flood_direction=20, ebb_direction=197, spring_range_m=4.7, spring_max_knots=3.0)),
    ("sandwich",            dict(flood_direction=19, ebb_direction=200, spring_range_m=6.2, spring_max_knots=2.0)),
    ("deal",                dict(flood_direction=19, ebb_direction=200, spring_range_m=6.7, spring_max_knots=3.0)),

    # ── Dover Strait ──────────────────────────────────────────────────────
    ("dover",               dict(flood_direction=53, ebb_direction=232, spring_range_m=6.7, spring_max_knots=2.5)),
    ("folkestone",          dict(flood_direction=53, ebb_direction=232, spring_range_m=7.3, spring_max_knots=2.0)),
    ("dungeness",           dict(flood_direction=31, ebb_direction=211, spring_range_m=6.5, spring_max_knots=2.0)),
    ("rye",                 dict(flood_direction=40, ebb_direction=221, spring_range_m=6.5, spring_max_knots=1.5)),
    ("hastings",            dict(flood_direction=68, ebb_direction=248, spring_range_m=6.5, spring_max_knots=1.5)),
    ("eastbourne",          dict(flood_direction=68, ebb_direction=248, spring_range_m=6.5, spring_max_knots=1.5)),
    ("newhaven",            dict(flood_direction=105, ebb_direction=285, spring_range_m=6.2, spring_max_knots=1.6)),
    ("brighton",            dict(flood_direction=52, ebb_direction=243, spring_range_m=6.0, spring_max_knots=1.6)),
    ("shoreham",            dict(flood_direction=52, ebb_direction=243, spring_range_m=6.0, spring_max_knots=1.6)),
    ("worthing",            dict(flood_direction=52, ebb_direction=243, spring_range_m=5.8, spring_max_knots=1.5)),
    ("littlehampton",       dict(flood_direction=52, ebb_direction=243, spring_range_m=5.5, spring_max_knots=1.5)),
    ("chichester",          dict(flood_direction=40, ebb_direction=220, spring_range_m=4.9, spring_max_knots=1.5)),

    # ── East Anglian coast ────────────────────────────────────────────────
    ("walton-on-the-naze",  dict(flood_direction=270, ebb_direction=90, spring_range_m=4.0, spring_max_knots=1.5)),
    ("walton on the naze",  dict(flood_direction=270, ebb_direction=90, spring_range_m=4.0, spring_max_knots=1.5)),
    ("clacton",             dict(flood_direction=270, ebb_direction=90, spring_range_m=4.0, spring_max_knots=1.5)),
    ("felixstowe",          dict(flood_direction=255, ebb_direction=75, spring_range_m=4.0, spring_max_knots=2.0)),
    ("harwich",             dict(flood_direction=255, ebb_direction=75, spring_range_m=4.0, spring_max_knots=2.0)),
    ("ipswich",             dict(flood_direction=230, ebb_direction=50, spring_range_m=3.8, spring_max_knots=1.5)),
    ("woodbridge",          dict(flood_direction=250, ebb_direction=70, spring_range_m=3.5, spring_max_knots=2.0)),
    ("orford",              dict(flood_direction=5, ebb_direction=185, spring_range_m=3.0, spring_max_knots=1.5)),
    ("aldeburgh",           dict(flood_direction=5, ebb_direction=185, spring_range_m=2.5, spring_max_knots=1.2)),
    ("southwold",           dict(flood_direction=5, ebb_direction=185, spring_range_m=2.0, spring_max_knots=1.2)),
    ("lowestoft",           dict(flood_direction=185, ebb_direction=5, spring_range_m=2.0, spring_max_knots=2.0)),
    ("great yarmouth",      dict(flood_direction=185, ebb_direction=5, spring_range_m=2.0, spring_max_knots=2.0)),
    ("yarmouth",            dict(flood_direction=185, ebb_direction=5, spring_range_m=2.0, spring_max_knots=2.0)),
    ("caister",             dict(flood_direction=185, ebb_direction=5, spring_range_m=1.9, spring_max_knots=1.5)),
    ("winterton",           dict(flood_direction=355, ebb_direction=175, spring_range_m=2.0, spring_max_knots=1.5)),

    # ── Norfolk coast / The Wash ──────────────────────────────────────────
    ("cromer",              dict(flood_direction=270, ebb_direction=90, spring_range_m=4.5, spring_max_knots=1.5)),
    ("sheringham",          dict(flood_direction=270, ebb_direction=90, spring_range_m=4.5, spring_max_knots=1.0)),
    ("blakeney",            dict(flood_direction=270, ebb_direction=90, spring_range_m=5.0, spring_max_knots=1.0)),
    ("wells-next-the-sea",  dict(flood_direction=270, ebb_direction=90, spring_range_m=5.5, spring_max_knots=1.5)),
    ("wells next the sea",  dict(flood_direction=270, ebb_direction=90, spring_range_m=5.5, spring_max_knots=1.5)),
    ("wells",               dict(flood_direction=270, ebb_direction=90, spring_range_m=5.5, spring_max_knots=1.5)),
    ("hunstanton",          dict(flood_direction=145, ebb_direction=325, spring_range_m=6.5, spring_max_knots=2.0)),
    ("king's lynn",         dict(flood_direction=145, ebb_direction=325, spring_range_m=6.0, spring_max_knots=2.5)),
    ("kings lynn",          dict(flood_direction=145, ebb_direction=325, spring_range_m=6.0, spring_max_knots=2.5)),
    ("boston",              dict(flood_direction=155, ebb_direction=335, spring_range_m=6.0, spring_max_knots=2.5)),
    ("skegness",            dict(flood_direction=180, ebb_direction=0, spring_range_m=5.0, spring_max_knots=1.5)),
]
# fmt: on


def enrich_station(station: dict) -> dict:
    """
    Look up stream direction data for a station by name and merge it in.
    Only fills fields that aren't already set (e.g. from TICON-4 data).
    Returns the station dict (mutated in place and returned).
    """
    if station.get("flood_direction") is not None:
        return station  # already has direction data

    name_lower = station.get("name", "").lower()
    for key, data in STREAM_DATA:
        if key in name_lower:
            for field, value in data.items():
                if station.get(field) is None:
                    station[field] = value
            break

    return station
