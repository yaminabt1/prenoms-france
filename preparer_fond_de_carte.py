"""Ajoute les 5 DOM aux fonds de carte, en petits encarts sous la métropole.

À lancer une seule fois (le résultat est enregistré dans departements.geojson et regions.geojson) :
    .venv/bin/python preparer_fond_de_carte.py chemin/vers/departements-avec-outre-mer.geojson \
        chemin/vers/regions-version-simplifiee.geojson

Les fichiers sources viennent du projet france-geojson :
https://github.com/gregoiredavid/france-geojson
"""
import json
import math
import sys
from pathlib import Path

FOND = Path(__file__).resolve().parent / "departements.geojson"
FOND_REGIONS = Path(__file__).resolve().parent / "regions.geojson"

# L'ordre des encarts, de gauche à droite
DOM = ["971", "972", "973", "974", "976"]
# Chaque DOM est aussi une région, avec son propre code
REGION_DU_DOM = {"971": "01", "972": "02", "973": "03", "974": "04", "976": "06"}

# La rangée d'encarts, en degrés, dans la mer au sud de la métropole
BAS, HAUTEUR = 39.7, 1.3   # latitude du bas des encarts et leur hauteur
LARGEUR_MAX = 2.0          # largeur maximale d'un encart (en longitude)
DEPART, ECART = -4.6, 0.55  # longitude du premier encart et espace entre deux encarts
LAT_ARRIVEE = BAS + HAUTEUR / 2


def simplifier(points, tolerance):
    """Retire les points inutiles d'un contour (algorithme de Douglas-Peucker)."""
    if len(points) < 3:
        return points
    (x1, y1), (x2, y2) = points[0], points[-1]
    dx, dy = x2 - x1, y2 - y1
    longueur = math.hypot(dx, dy) or 1e-12
    distances = [abs(dy * x - dx * y + x2 * y1 - y2 * x1) / longueur for x, y in points[1:-1]]
    i = max(range(len(distances)), key=distances.__getitem__) + 1
    if distances[i - 1] <= tolerance:
        return [points[0], points[-1]]
    return simplifier(points[: i + 1], tolerance)[:-1] + simplifier(points[i:], tolerance)


def simplifier_anneau(anneau, tolerance):
    """Un contour fermé commence et finit au même point : on le coupe en deux au point le plus éloigné."""
    x0, y0 = anneau[0]
    k = max(range(len(anneau)), key=lambda i: math.hypot(anneau[i][0] - x0, anneau[i][1] - y0))
    return simplifier(anneau[: k + 1], tolerance)[:-1] + simplifier(anneau[k:], tolerance)


def surface(anneau):
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(anneau, anneau[1:]))) / 2


def deplacer(feature, gauche):
    """Réduit un DOM, le place dans son encart et renvoie la longitude du bord droit."""
    geo = feature["geometry"]
    polygones = geo["coordinates"] if geo["type"] == "MultiPolygon" else [geo["coordinates"]]
    points = [p for poly in polygones for anneau in poly for p in anneau]
    xmin, xmax = min(p[0] for p in points), max(p[0] for p in points)
    ymin, ymax = min(p[1] for p in points), max(p[1] for p in points)

    # On corrige l'écart entre degrés de longitude et de latitude pour garder la forme du territoire
    correction = math.cos(math.radians((ymin + ymax) / 2)) / math.cos(math.radians(LAT_ARRIVEE))
    echelle = min(HAUTEUR / (ymax - ymin), LARGEUR_MAX / ((xmax - xmin) * correction))
    largeur = (xmax - xmin) * correction * echelle
    haut_vide = (HAUTEUR - (ymax - ymin) * echelle) / 2

    # On garde les îles de taille notable et on allège les contours
    plus_grande = max(surface(poly[0]) for poly in polygones)
    tolerance = max(xmax - xmin, ymax - ymin) / 200
    nouveaux = []
    for poly in polygones:
        if surface(poly[0]) < plus_grande * 0.01:
            continue
        anneaux = []
        for anneau in poly:
            allege = simplifier_anneau(anneau, tolerance)
            if len(allege) >= 4:
                anneaux.append([
                    [round(gauche + (x - xmin) * correction * echelle, 4),
                     round(BAS + haut_vide + (y - ymin) * echelle, 4)]
                    for x, y in allege
                ])
        if anneaux:
            nouveaux.append(anneaux)

    feature["geometry"] = {"type": "MultiPolygon", "coordinates": nouveaux}
    # Où écrire le nom du DOM, sous son encart
    feature["properties"]["etiquette_lon"] = round(gauche + largeur / 2, 4)
    feature["properties"]["etiquette_lat"] = BAS - 0.35
    return gauche + largeur


def main(source, source_regions):
    fond = json.loads(FOND.read_text(encoding="utf-8"))
    metropole = [f for f in fond["features"] if not f["properties"]["code"].startswith("97")]

    outre_mer = {f["properties"]["code"]: f for f in json.loads(Path(source).read_text(encoding="utf-8"))["features"]}
    gauche, encarts = DEPART, []
    for code in DOM:
        f = outre_mer[code]
        f = {"type": "Feature", "properties": {"code": code, "nom": f["properties"]["nom"]}, "geometry": f["geometry"]}
        gauche = deplacer(f, gauche) + ECART
        encarts.append(f)

    fond["features"] = metropole + encarts
    FOND.write_text(json.dumps(fond, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(metropole)} départements de métropole + {len(encarts)} DOM -> {FOND.name}")

    # Les régions : les 13 de métropole, et les mêmes encarts DOM avec leur code de région
    regions = json.loads(Path(source_regions).read_text(encoding="utf-8"))
    regions["features"] = [f for f in regions["features"] if f["properties"]["code"] not in REGION_DU_DOM.values()]
    nb_metropole = len(regions["features"])
    for f in encarts:
        code = REGION_DU_DOM[f["properties"]["code"]]
        regions["features"].append({**f, "properties": {**f["properties"], "code": code}})
    FOND_REGIONS.write_text(json.dumps(regions, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{nb_metropole} régions de métropole + {len(encarts)} DOM -> {FOND_REGIONS.name}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
