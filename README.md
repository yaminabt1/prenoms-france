# Évolution des prénoms en France

Une application Streamlit pour explorer le fichier des prénoms de l'Insee (1900–2025) :

- comparer jusqu'à huit prénoms et leur nombre de naissances année par année ;
- voir sur une carte, par département ou par région, où sont nés les bébés qui portent un prénom une année donnée.

## Les fichiers

| Fichier | Rôle |
|---|---|
| `app.py` | L'application |
| `prenoms-2025.parquet` | Les données de l'Insee (France, régions, départements) |
| `departements.geojson`, `regions.geojson` | Les fonds de carte, DOM en encarts |
| `preparer_fond_de_carte.py` | Le script qui a fabriqué les fonds de carte (à ne relancer que pour les refaire) |
| `requirements.txt` | Les modules à installer, en local et sur Streamlit Community Cloud |
| `.streamlit/config.toml` | Les couleurs de l'application |

## Lancer l'application sur son ordinateur

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run app.py
```

## Sources

- Données : Insee, fichier des prénoms, édition 2025 (Licence Ouverte).
- Fonds de carte : [france-geojson](https://github.com/gregoiredavid/france-geojson), d'après les contours de l'IGN.
