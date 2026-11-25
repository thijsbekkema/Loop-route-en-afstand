#!/usr/bin/env python3
"""Maakt de padentegels voor de Afstand-app.

Gebruik:
  python maak_paden.py --bbox                  -> toont het uitsnijgebied (voor osmium extract)
  python maak_paden.py wegen.osm.pbf paden/v1  -> schrijft de tegels en index.json

De tegels gebruiken hetzelfde raster als de app (0,04 x 0,06 graden) en hetzelfde
formaat als de app intern gebruikt: [wegId, [knoopIds], [lat, lon, lat, lon, ...], {tags}].
"""
import datetime
import glob
import json
import math
import os
import sys

TILE_LAT, TILE_LON = 0.04, 0.06
CENTER = (53.1665, 5.9690)   # Garyp
HALF_KM = 25.0               # 50 x 50 km
KEEP = ('highway', 'surface', 'tracktype', 'foot', 'access', 'bicycle', 'area')
NO_HW = {'motorway', 'motorway_link', 'trunk', 'trunk_link', 'construction', 'proposed', 'raceway',
         'bus_guideway', 'platform', 'elevator', 'abandoned', 'disused', 'services', 'rest_area',
         'busway', 'corridor', 'via_ferrata'}


def region():
    """Tegelbereik (i0, i1, j0, j1) dat het 50 x 50 km-vierkant rond Garyp helemaal afdekt."""
    dlat = HALF_KM / 111.32
    dlon = HALF_KM / (111.32 * math.cos(math.radians(CENTER[0])))
    return (math.floor((CENTER[0] - dlat) / TILE_LAT), math.floor((CENTER[0] + dlat) / TILE_LAT),
            math.floor((CENTER[1] - dlon) / TILE_LON), math.floor((CENTER[1] + dlon) / TILE_LON))


def extract_bbox():
    i0, i1, j0, j1 = region()
    return (round(j0 * TILE_LON - 0.015, 4), round(i0 * TILE_LAT - 0.01, 4),
            round((j1 + 1) * TILE_LON + 0.015, 4), round((i1 + 1) * TILE_LAT + 0.01, 4))


def build(src, out):
    import osmium

    i0, i1, j0, j1 = region()
    tiles = {}
    count = 0

    class Wegen(osmium.SimpleHandler):
        def way(self, w):
            nonlocal count
            t = w.tags
            hw = t.get('highway')
            if not hw or hw in NO_HW or t.get('area') == 'yes':
                return
            ids, flat = [], []
            for nd in w.nodes:
                loc = nd.location
                if not loc.valid():
                    continue
                ids.append(nd.ref)
                flat.append(round(loc.lat, 6))
                flat.append(round(loc.lon, 6))
            if len(ids) < 2:
                return
            tags = {k: t.get(k) for k in KEEP if k in t}
            rec = [w.id, ids, flat, tags]
            keys = set()
            for k in range(len(ids)):
                la, lo = flat[2 * k], flat[2 * k + 1]
                keys.add((math.floor(la / TILE_LAT), math.floor(lo / TILE_LON)))
                if k:  # ook tegels waar een lang stuk tussen twee knopen doorheen loopt
                    pla, plo = flat[2 * k - 2], flat[2 * k - 1]
                    for i in range(math.floor(min(la, pla) / TILE_LAT), math.floor(max(la, pla) / TILE_LAT) + 1):
                        for j in range(math.floor(min(lo, plo) / TILE_LON), math.floor(max(lo, plo) / TILE_LON) + 1):
                            keys.add((i, j))
            for (i, j) in keys:
                if i0 <= i <= i1 and j0 <= j <= j1:
                    tiles.setdefault((i, j), []).append(rec)
            count += 1

    Wegen().apply_file(src, locations=True, idx='flex_mem')

    os.makedirs(out, exist_ok=True)
    for f in glob.glob(os.path.join(out, '*.json')):
        os.remove(f)
    for i in range(i0, i1 + 1):
        for j in range(j0, j1 + 1):
            with open(os.path.join(out, f'{i}_{j}.json'), 'w') as fh:
                json.dump(tiles.get((i, j), []), fh, separators=(',', ':'))
    meta = {
        'versie': 1,
        'gemaakt': datetime.date.today().isoformat(),
        'tileLat': TILE_LAT, 'tileLon': TILE_LON,
        'i': [i0, i1], 'j': [j0, j1],
        'wegen': count,
    }
    with open(os.path.join(out, 'index.json'), 'w') as fh:
        json.dump(meta, fh, separators=(',', ':'))
    print(f'{count} wegen in {(i1 - i0 + 1) * (j1 - j0 + 1)} tegels geschreven naar {out}')


if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == '--bbox':
        print(','.join(str(v) for v in extract_bbox()))
    elif len(sys.argv) == 3:
        build(sys.argv[1], sys.argv[2])
    else:
        print(__doc__)
        sys.exit(1)
