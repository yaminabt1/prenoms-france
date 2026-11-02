import json
from pathlib import Path

import pandas as pd
import streamlit as st
import altair as alt

st.set_page_config(page_title="Évolution des prénoms en France", layout="wide")

# Couleurs de l'application
GRIS = "#6B7670"
TRAIT = "#DCE1DD"
COULEURS = ["#2A4D69", "#C8553D", "#4B8F8C", "#8C6BB1",
            "#D4A017", "#5B7553", "#A23E48", "#3F88C5"]

# Polices et mise en page (CSS)
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,800&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@500&display=swap');

html, body, .stApp, p, label, input, textarea {
    font-family: 'IBM Plex Sans', system-ui, sans-serif;
}
.block-container { max-width: 1100px; padding-top: 3.5rem; }
[data-testid="stHeader"] { background: transparent; }

.surtitre {
    font-size: 0.75rem; letter-spacing: 0.14em; text-transform: uppercase;
    color: #6B7670; font-weight: 600;
}
.titre {
    font-family: 'Bricolage Grotesque', 'IBM Plex Sans', sans-serif;
    font-weight: 800; font-size: 3.2rem; line-height: 1.05;
    color: #17212B; margin: 0.3rem 0 0.6rem;
}
.sous-titre { color: #4A5550; font-size: 1.05rem; max-width: 60ch; margin-bottom: 2rem; }
.section {
    font-family: 'Bricolage Grotesque', 'IBM Plex Sans', sans-serif;
    font-weight: 600; font-size: 1.15rem; color: #17212B;
    margin: 2rem 0 0.6rem; padding-top: 1rem; border-top: 1px solid #DCE1DD;
}

.cartes {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 12px; margin-bottom: 0.5rem;
}
.carte { background: #FFFFFF; border: 1px solid #DCE1DD; border-radius: 8px; padding: 14px 16px; }
.carte-nom { display: flex; align-items: center; gap: 8px; font-weight: 600; }
.pastille { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
.carte-sexe { color: #6B7670; font-weight: 400; font-size: 0.85rem; }
.carte-total {
    font-family: 'IBM Plex Mono', monospace; font-size: 1.6rem;
    color: #17212B; margin-top: 10px; line-height: 1.1;
}
.carte-unite { color: #6B7670; font-size: 0.8rem; }
.carte-detail {
    color: #4A5550; font-size: 0.85rem; margin-top: 10px;
    padding-top: 10px; border-top: 1px solid #EEF1EE;
}
.rang-ligne { display: flex; justify-content: space-between; gap: 12px; padding: 3px 0; }
.rang-valeur { font-family: 'IBM Plex Mono', monospace; color: #17212B; }
</style>
""", unsafe_allow_html=True)


def nombre(n):
    """Écrit un nombre à la française : 12345 -> 12 345"""
    return f"{int(n):,}".replace(",", "\u202f")


# Le fichier Parquet de l'Insee, rangé à côté de l'app (pour qu'elle fonctionne aussi en ligne)
DOSSIER = Path(__file__).resolve().parent
FICHIER = DOSSIER / "prenoms-2025.parquet"


# 1. Charger le fichier (une seule fois grâce au cache)
@st.cache_data
def charger_donnees():
    # On ne lit que le niveau France : les colonnes y sont stockées en texte
    df = pd.read_parquet(
        FICHIER,
        columns=["sexe", "prenom", "periode", "valeur", "rang"],
        filters=[("niveau_geographique", "==", "FRANCE")],
    )
    df["sexe"] = df["sexe"].astype(int)
    df["periode"] = pd.to_numeric(df["periode"], errors="coerce")
    df = df.dropna(subset=["periode"])
    df["periode"] = df["periode"].astype(int)
    df = df[~df["prenom"].str.startswith("_")]
    df["sexe_texte"] = df["sexe"].map({1: "garçon", 2: "fille"})
    df["libelle"] = df["prenom"] + " (" + df["sexe_texte"] + ")"
    return df


@st.cache_data
def liste_libelles(df):
    totaux = df.groupby("libelle")["valeur"].sum()
    return totaux.sort_values(ascending=False).index.tolist()


# Les deux échelles de la carte (fonds de carte préparés par preparer_fond_de_carte.py)
NIVEAUX = {
    "Départements": {
        "code": "DEP", "fond": DOSSIER / "departements.geojson", "nombre": 101, "mayotte": "976",
        "titre": "Département", "pluriel": "départements",
        "un_meme": "un même département", "aucun": "aucun département",
    },
    "Régions": {
        "code": "REG", "fond": DOSSIER / "regions.geojson", "nombre": 18, "mayotte": "06",
        "titre": "Région", "pluriel": "régions",
        "un_meme": "une même région", "aucun": "aucune région",
    },
}


# Les naissances d'un prénom par département ou par région, lues à la demande
@st.cache_data
def charger_territoires(niveau, prenom, sexe):
    dep = pd.read_parquet(
        FICHIER,
        columns=["geographie", "periode", "valeur"],
        filters=[
            ("niveau_geographique", "==", niveau),
            ("prenom", "==", prenom),
            ("sexe", "==", str(sexe)),
        ],
    )
    dep["periode"] = dep["periode"].astype(int)
    return dep.rename(columns={"geographie": "code"})


# Un fond de carte : la métropole, et les 5 DOM en encarts
@st.cache_data
def fond_de_carte(chemin, date_modif):
    # date_modif : le cache se renouvelle dès que le fichier du fond de carte change
    with open(chemin, encoding="utf-8") as f:
        return json.load(f)["features"]


def pourcent(x):
    """Écrit un pourcentage à la française : 5.6 -> 5,6 %"""
    return f"{x:.1f}".replace(".", ",") + " %"


df = charger_donnees()
annee_min, annee_max = df["periode"].min(), df["periode"].max()

# 2. L'en-tête
st.markdown(
    '<div class="surtitre">Données Insee 2025</div>'
    '<div class="titre">Évolution des prénoms en France</div>'
    '<div class="sous-titre">'
    f'Le nombre de bébés ayant reçu chaque prénom, année par année, de {annee_min} à {annee_max}. '
    "Comparez jusqu'à huit prénoms, filles et garçons confondus."
    '</div>',
    unsafe_allow_html=True,
)

# 3. Le choix des prénoms
options = liste_libelles(df)
par_defaut = [p for p in ["CAMILLE (fille)", "CAMILLE (garçon)"] if p in options]

choix = st.multiselect(
    "Prénoms à comparer",
    options=options,
    default=par_defaut,
    placeholder="Tapez les premières lettres d'un prénom…",
    max_selections=8,
)

if not choix:
    st.info("Choisissez au moins un prénom pour afficher son évolution.")
    st.stop()

resultat = df[df["libelle"].isin(choix)].sort_values("periode")
couleur_de = {lib: COULEURS[i] for i, lib in enumerate(choix)}

# 4. Les fiches résumées
cartes = ""
for lib in choix:
    donnees = resultat[resultat["libelle"] == lib]
    if donnees.empty:
        continue
    record = donnees.loc[donnees["valeur"].idxmax()]
    cartes += (
        '<div class="carte">'
        '<div class="carte-nom">'
        f'<span class="pastille" style="background:{couleur_de[lib]}"></span>'
        f'{record["prenom"]} <span class="carte-sexe">{record["sexe_texte"]}</span>'
        '</div>'
        f'<div class="carte-total">{nombre(donnees["valeur"].sum())}</div>'
        '<div class="carte-unite">naissances au total</div>'
        f'<div class="carte-detail">Record en {record["periode"]} : {nombre(record["valeur"])} bébés</div>'
        '</div>'
    )
st.markdown(f'<div class="cartes">{cartes}</div>', unsafe_allow_html=True)

# 5. Le graphique
st.markdown('<div class="section">Naissances par année</div>', unsafe_allow_html=True)

echelle = alt.Scale(domain=choix, range=[couleur_de[c] for c in choix])
survol = alt.selection_point(nearest=True, on="pointerover", fields=["periode"], empty=False)
# Un clic sur une courbe choisit le prénom et l'année affichés sur la carte
clic = alt.selection_point(name="clic", nearest=True, on="click", fields=["libelle", "periode"])

# Sur un écran étroit (téléphone), on espace les années et on retire les noms au bout des courbes
ETROIT = "containerSize()[0] < 560"

base = alt.Chart(resultat).encode(
    x=alt.X(
        "periode:Q", title=None,
        scale=alt.Scale(domain=[int(resultat["periode"].min()), int(resultat["periode"].max())], nice=False),
        axis=alt.Axis(format="d", tickCount=alt.ExprRef(f"{ETROIT} ? 4 : 10")),
    ),
    y=alt.Y("valeur:Q", title="Naissances"),
    color=alt.Color("libelle:N", scale=echelle, legend=None),
)

lignes = base.mark_line(strokeWidth=2.5, interpolate="monotone")

points = base.mark_circle(size=70).encode(
    opacity=alt.condition(survol, alt.value(1), alt.value(0)),
    tooltip=[
        alt.Tooltip("libelle", title="Prénom"),
        alt.Tooltip("periode", title="Année"),
        alt.Tooltip("valeur", title="Naissances", format=","),
        alt.Tooltip("rang", title="Rang"),
    ],
).add_params(survol, clic)

regle = alt.Chart(resultat).mark_rule(color="#B5BDB8", strokeDash=[4, 4]).encode(
    x="periode:Q"
).transform_filter(survol)

# Le nom de chaque prénom au bout de sa courbe
derniers = resultat.loc[resultat.groupby("libelle")["periode"].idxmax()]
etiquettes = alt.Chart(derniers).mark_text(
    align="left", dx=8, fontWeight=600, fontSize=12
).transform_filter(f"!({ETROIT})").encode(
    x="periode:Q",
    y="valeur:Q",
    text="prenom:N",
    color=alt.Color("libelle:N", scale=echelle, legend=None),
)

graphique = (
    alt.layer(lignes, regle, points, etiquettes)
    .properties(
        height=440,
        padding=alt.ExprRef(f"{{left: 5, right: {ETROIT} ? 12 : 110, top: 10, bottom: 5}}"),
    )
    .configure(font="IBM Plex Sans")
    .configure_view(stroke=None)
    .configure_axis(
        labelColor=GRIS, titleColor=GRIS, labelFontSize=12, titleFontSize=12,
        titleFontWeight=500, domain=False, tickColor=TRAIT, gridColor="#E8ECE9",
    )
    .configure_axisX(grid=False, domain=True, domainColor=TRAIT)
)
evenement = st.altair_chart(
    graphique, theme=None, key="courbes", on_select="rerun", selection_mode=["clic"]
)

# Le clic reste mémorisé d'une exécution à l'autre : on ne l'applique que s'il est nouveau
selection = evenement.selection.get("clic") or []
if selection:
    clique = (selection[0].get("libelle"), selection[0].get("periode"))
    if clique != st.session_state.get("dernier_clic") and clique[0] in choix:
        st.session_state["dernier_clic"] = clique
        st.session_state["prenom_carte"] = clique[0]
        st.session_state["annee_carte"] = int(clique[1])
        st.session_state["prenom_carte_prec"] = clique[0]

# 6. La carte : où sont nés les bébés qui portent ce prénom ?
COULEUR_VIDE = "#E3E5E0"
DEGRADE = ["#C2D3E2", "#2A4D69"]


@st.fragment
def section_carte(choix):
    st.markdown('<div class="section">Où ce prénom est-il donné ?</div>', unsafe_allow_html=True)

    if st.session_state.get("prenom_carte") not in choix:
        st.session_state["prenom_carte"] = choix[0]
    lib = st.radio("Prénom affiché", choix, key="prenom_carte", horizontal=True,
                   label_visibility="collapsed")
    niveau = NIVEAUX[st.radio("Échelle", list(NIVEAUX), key="niveau_carte", horizontal=True,
                              label_visibility="collapsed")]

    infos = df[df["libelle"] == lib]
    prenom, sexe = infos["prenom"].iloc[0], int(infos["sexe"].iloc[0])
    dep = charger_territoires(niveau["code"], prenom, sexe)
    if dep.empty:
        st.info(f"{prenom} n'a jamais été donné 5 fois ou plus la même année dans {niveau['un_meme']}.")
        return

    debut, fin = int(dep["periode"].min()), int(dep["periode"].max())
    # Nouveau prénom : la carte s'ouvre sur son année record
    if st.session_state.get("prenom_carte_prec") != lib:
        st.session_state["prenom_carte_prec"] = lib
        st.session_state["annee_carte"] = int(infos.loc[infos["valeur"].idxmax(), "periode"])
    st.session_state["annee_carte"] = min(max(st.session_state["annee_carte"], debut), fin)

    if debut < fin:
        annee = st.slider("Année", debut, fin, key="annee_carte")
    else:
        annee = debut
    st.caption("Astuce : cliquez sur une courbe pour afficher la carte de ce prénom à cette année-là.")

    an = dep[dep["periode"] == annee].set_index("code")["valeur"]
    total = an.sum()

    # On range chiffres et texte de l'info-bulle dans chaque territoire du fond de carte
    fond_carte = fond_de_carte(niveau["fond"], niveau["fond"].stat().st_mtime)
    noms = {f["properties"]["code"]: f["properties"]["nom"] for f in fond_carte}
    territoires = []
    for f in fond_carte:
        code = f["properties"]["code"]
        valeur = an.get(code)
        if code == niveau["mayotte"] and annee < 2012:
            proprietes = {**f["properties"], "part": None, "texte": "pas de données avant 2012"}
        elif valeur is None:
            proprietes = {**f["properties"], "part": None, "texte": "moins de 5 naissances"}
        else:
            part = valeur / total * 100
            proprietes = {**f["properties"], "part": part,
                          "texte": f"{nombre(valeur)} bébés · {pourcent(part)}"}
        territoires.append({**f, "properties": proprietes})

    gauche, droite = st.columns([3, 2], gap="large")

    with gauche:
        source = alt.Data(values=territoires)
        infobulle = [
            alt.Tooltip("properties.nom:N", title=niveau["titre"]),
            alt.Tooltip("properties.texte:N", title=f"En {annee}"),
        ]
        fond = alt.Chart(source).mark_geoshape(
            fill=COULEUR_VIDE, stroke="#FFFFFF", strokeWidth=0.7
        ).encode(tooltip=infobulle)
        remplis = alt.Chart(source).mark_geoshape(
            stroke="#FFFFFF", strokeWidth=0.7
        ).encode(
            color=alt.Color(
                "properties.part:Q",
                scale=alt.Scale(domain=[0, float(an.max() / total * 100) if total else 1],
                                range=DEGRADE),
                legend=alt.Legend(title="Part des naissances (%)", orient="bottom",
                                  direction="horizontal", gradientLength=260, format=".1f"),
            ),
            tooltip=infobulle,
        ).transform_filter("isValid(datum.properties.part)")
        # Le nom de chaque DOM sous son encart
        noms_dom = alt.Chart(source).mark_text(fontSize=10, color=GRIS).encode(
            longitude="properties.etiquette_lon:Q",
            latitude="properties.etiquette_lat:Q",
            text="properties.nom:N",
        ).transform_filter("isValid(datum.properties.etiquette_lon)")

        carte = (
            alt.layer(fond, remplis, noms_dom)
            .project(type="conicConformal", parallels=[44, 49], rotate=[-3, 0])
            # La carte prend la largeur de sa colonne : elle se réduit sur téléphone
            .properties(width="container", height=480)
            .configure(font="IBM Plex Sans")
            .configure_view(stroke=None)
            .configure_legend(labelColor=GRIS, titleColor=GRIS, titleFontWeight=500)
        )
        st.altair_chart(carte, theme=None, width="stretch")

    with droite:
        # Mayotte : données à partir de 2012
        nb_territoires = niveau["nombre"] if annee >= 2012 else niveau["nombre"] - 1
        if not total:
            st.info(f"En {annee}, {niveau['aucun']} ne compte 5 naissances ou plus de {prenom}.")
            return
        lignes = "".join(
            f'<div class="rang-ligne"><span>{i}. {noms.get(code, code)}</span>'
            f'<span class="rang-valeur">{pourcent(v / total * 100)}</span></div>'
            for i, (code, v) in enumerate(an.sort_values(ascending=False).head(5).items(), 1)
        )
        st.markdown(
            '<div class="carte">'
            f'<div class="carte-nom">{prenom} <span class="carte-sexe">{infos["sexe_texte"].iloc[0]} · {annee}</span></div>'
            f'<div class="carte-total">{nombre(total)}</div>'
            '<div class="carte-unite">bébés en France</div>'
            f'<div class="carte-detail">{lignes}</div>'
            f'<div class="carte-detail">Présent dans {len(an)} {niveau["pluriel"]} sur {nb_territoires}.'
            + (' Les autres, en gris, comptent moins de 5 naissances.' if len(an) < nb_territoires else '')
            + '</div>'
            '</div>',
            unsafe_allow_html=True,
        )


section_carte(choix)

# 7. Le détail, rangé dans un panneau dépliable
with st.expander("Voir les chiffres année par année"):
    tableau = resultat.pivot_table(index="periode", columns="libelle", values="valeur")
    tableau = tableau[[c for c in choix if c in tableau.columns]].fillna(0).astype(int)
    tableau.index = tableau.index.astype(str)
    tableau.index.name = "Année"
    st.dataframe(tableau, width="stretch")

st.caption(
    f"Source : Insee, fichier des prénoms, {annee_min}–{annee_max}. "
    "Fonds de carte : projet france-geojson, d'après les contours IGN."
)