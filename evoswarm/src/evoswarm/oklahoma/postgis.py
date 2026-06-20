"""PostGIS query helpers for Oklahoma PLSS tracts.

Parameterized SQL only (psycopg style placeholders) — no f-string interpolation
into SQL, ever. Assumes a `plss_tracts` table with a `geom geometry(Polygon,4326)`
column and a `wells` table with `geom geometry(Point,4326)`.
"""

from __future__ import annotations

# Tracts whose centroid falls inside a county boundary polygon.
TRACTS_IN_COUNTY = """
SELECT t.legal, ST_AsGeoJSON(t.geom) AS geojson, t.net_mineral_acres
FROM plss_tracts t
JOIN county_boundaries c ON ST_Contains(c.geom, ST_Centroid(t.geom))
WHERE c.name = %(county)s
ORDER BY t.net_mineral_acres DESC
LIMIT %(limit)s;
"""

# Active wells within `radius_m` meters of a tract (geography cast for true meters).
WELLS_NEAR_TRACT = """
SELECT w.api_number, w.well_name, w.status,
       ST_Distance(w.geom::geography, t.geom::geography) AS dist_m
FROM wells w
JOIN plss_tracts t ON t.legal = %(legal)s
WHERE ST_DWithin(w.geom::geography, t.geom::geography, %(radius_m)s)
  AND w.status = 'ACTIVE'
ORDER BY dist_m ASC;
"""

# Spacing-unit acreage a tract overlaps, for DOI denominator validation.
UNIT_OVERLAP_ACRES = """
SELECT u.unit_id,
       ST_Area(ST_Intersection(u.geom, t.geom)::geography) / 4046.8564224 AS overlap_acres
FROM spacing_units u
JOIN plss_tracts t ON t.legal = %(legal)s
WHERE ST_Intersects(u.geom, t.geom);
"""


def fetch_tracts_in_county(cur, county: str, limit: int = 100) -> list[dict]:
    cur.execute(TRACTS_IN_COUNTY, {"county": county, "limit": limit})
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]
