"""
TP5 — Dashboard du TP4, prêt à être déployé sur Render.
En local : python3 app.py   puis ouvrir http://127.0.0.1:8050 dans le navigateur
Sur Render : gunicorn app:server   (gunicorn lance la variable « server » définie plus bas)
Au démarrage, la base SQLite est recréée à partir des CSV de data/ (init_db.py du TP4).
Le bouton « Refresh » interroge de nouveau la base et remet tous les filtres.
"""
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import folium
from folium.plugins import MarkerCluster
from dash import Dash, html, dcc, Input, Output, ctx

import db                     # module d'accès à la base SQLite (TP4)
import init_db                # script de création de la base (TP4)

# TP5 : on recrée la base à CHAQUE démarrage de l'application.
# Sur Render (plan gratuit), le disque n'est pas conservé : le fichier .db
# disparaît à chaque redémarrage. On le reconstruit donc à partir des CSV.
init_db.main()


# =====================================================================
# 1. DONNÉES : lues dans la base SQLite via le module db.py (TP4)
#    Plus de lecture de fichiers ici : le dashboard interroge la base.
# =====================================================================
# Tranches de facture (TP2)
SEUILS = [0, 20, 60, float("inf")]
TRANCHES = ["Facture faible (< 20 k€)", "Facture moyenne (20 à 60 k€)", "Facture élevée (> 60 k€)"]

# Mêmes couleurs que dans les TP1 et TP2
TYPES = ["Agriculteur", "Industriel", "Site public"]
COULEURS = {"Agriculteur": "#4A8C3A", "Industriel": "#D9822B", "Site public": "#1B6A8F"}
NOMS_GROUPES = {"Agriculteur": "Agriculteurs", "Industriel": "Industriels", "Site public": "Sites publics"}
JOURS = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]

DONNEES = {"sites": None, "profil": None, "info": ""}


def charger_donnees():
    """Interroge la base (via db.py) et garde les résultats en mémoire jusqu'au prochain « Refresh ».
    Toute modification faite directement dans la base apparaît donc après un clic sur « Refresh »."""
    sites = db.synthese_par_site()
    sites["tranche"] = pd.cut(sites["facture_kEUR"], bins=SEUILS, labels=TRANCHES)
    DONNEES["sites"] = sites
    DONNEES["profil"] = db.profil_horaire()
    DONNEES["info"] = (f"Données lues dans la base SQLite à {datetime.now():%H:%M:%S} · "
                       f"{len(sites)} sites · {fr(db.nombre_releves())} relevés")


def fr(x, dec=0):
    """Format français : espace pour les milliers, virgule pour les décimales."""
    return f"{x:,.{dec}f}".replace(",", " ").replace(".", ",")


def mise_en_forme(fig, titre, sous_titre=None, hauteur=420):
    """Style commun épuré du TP1 : titre-message + sous-titre, fond blanc."""
    texte = f"<b>{titre}</b>"
    if sous_titre:
        texte += f"<br><span style='font-size:12px;color:#6B7280'>{sous_titre}</span>"
    fig.update_layout(template="simple_white", height=hauteur, separators=", ",
                      title=dict(text=texte, x=0.02, xanchor="left", font=dict(size=16)),
                      font=dict(family="Arial", size=12, color="#1F2937"),
                      margin=dict(t=110, l=50, r=20, b=40))
    return fig


def figure_vide(message):
    """Figure affichée quand aucun type n'est sélectionné."""
    fig = go.Figure()
    fig.add_annotation(text=message, x=0.5, y=0.5, xref="paper", yref="paper",
                       showarrow=False, font=dict(size=15, color="#6B7280"))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return mise_en_forme(fig, "Aucun type sélectionné", hauteur=300)


# =====================================================================
# 2. GRAPHIQUES DU TP1, recalculés pour les types sélectionnés
# =====================================================================
def figure_heatmap(types):
    """TP1 – Q3 : heatmap heure × jour, un panneau par type sélectionné."""
    sites, profil = DONNEES["sites"], DONNEES["profil"]
    sel = sites[sites["type"].isin(types)]
    part_hc = sel["energie_HC_kWh"].sum() / sel["energie_kWh"].sum() * 100

    fig = make_subplots(rows=1, cols=len(types), subplot_titles=types, shared_yaxes=True,
                        horizontal_spacing=0.04)
    for annotation in fig.layout.annotations:
        annotation.font = dict(color=COULEURS[annotation.text], size=13)

    for i, t in enumerate(types, start=1):
        m = profil[profil["type"] == t].pivot_table(index="jour", columns="heure", values="puissance_kw")
        indice = m / m.values.max() * 100
        fig.add_trace(go.Heatmap(
            z=indice.values, x=indice.columns, y=JOURS, customdata=m.values,
            colorscale=[[0, "white"], [1, COULEURS[t]]], zmin=0, zmax=100, showscale=False,
            hovertemplate="%{y} %{x}h<br>%{customdata:.1f} kW en moyenne<extra>" + t + "</extra>"),
            row=1, col=i)
        for x in (5.5, 21.5):     # limites HP / HC (6h et 22h)
            fig.add_vline(x=x, line=dict(color="#1F2937", width=1, dash="dot"), row=1, col=i)

    fig.update_xaxes(tickvals=[0, 6, 12, 18, 22], ticktext=["0h", "6h", "12h", "18h", "22h"],
                     showline=False, ticks="")
    fig.update_yaxes(autorange="reversed", showline=False, ticks="")
    return mise_en_forme(fig,
                         f"Seulement {fr(part_hc)} % de l'énergie consommée en heures creuses",
                         "Puissance moyenne par jour et par heure (plus foncé = plus chargé) · pointillés : 6h et 22h",
                         hauteur=380)


def figure_scatter(types):
    """TP1 – Q6 : part HC vs prix moyen, une bulle par site des types sélectionnés."""
    sites = DONNEES["sites"]
    d = sites[sites["type"].isin(types)].copy()
    d["taille"] = 14 + 40 * np.sqrt(d["cout_EUR"] / sites["cout_EUR"].max())
    # Position des étiquettes pour éviter les chevauchements (comme au TP1)
    positions = {"Industriel 2": "middle right", "Agri 1": "bottom center", "Agri 2": "bottom left",
                 "Industriel 4": "bottom right", "SP 2": "middle right"}
    d["pos"] = d["site"].map(positions).fillna("top center")

    fig = go.Figure()
    for t in types:
        dt = d[d["type"] == t]
        fig.add_trace(go.Scatter(
            x=dt["part_HC"], y=dt["prix_moyen"], mode="markers+text", name=t,
            marker=dict(size=dt["taille"], color=COULEURS[t], opacity=0.85),
            text=dt["site"], textposition=dt["pos"], textfont=dict(color=COULEURS[t], size=11),
            customdata=dt["facture_kEUR"],
            hovertemplate="%{text} : %{y:.1f} c€/kWh, facture %{customdata:.1f} k€<extra></extra>"))

    fig.add_vline(x=33.3, line=dict(color="#6B7280", width=1, dash="dot"))
    fig.add_annotation(x=33.3, y=33, text="répartition uniforme (33 %)", xanchor="left",
                       showarrow=False, font=dict(color="#6B7280", size=10))
    fig.update_xaxes(title="Part de l'énergie en heures creuses (%)", range=[0, 42])
    fig.update_yaxes(title="Prix moyen payé (c€/kWh)", range=[3, 35])
    fig.update_layout(legend=dict(orientation="h", x=0, y=-0.2, title=None))
    return mise_en_forme(fig,
                         "Le contrat pèse plus que le comportement",
                         "Une bulle = un site (taille = facture annuelle)",
                         hauteur=460)


# =====================================================================
# 3. CARTE DU TP2, recalculée pour les types sélectionnés
# =====================================================================
STYLE_TRANCHE = {
    TRANCHES[0]: {"rayon": 14, "couleur": "#9CA3AF"},
    TRANCHES[1]: {"rayon": 19, "couleur": "#4B5563"},
    TRANCHES[2]: {"rayon": 25, "couleur": "#B4483F"},
}


def fiche(s):
    couleur = COULEURS[s["type"]]
    return f"""
    <div style="font-family: Arial; font-size: 13px; min-width: 200px;">
        <b style="font-size: 15px; color: {couleur};">{s['site']}</b><br>
        <span style="color: #6B7280;">{s['type']} · {s['tranche']}</span>
        <hr style="margin: 6px 0;">
        Consommation annuelle : <b>{fr(s['conso_MWh'])} MWh</b><br>
        Facture annuelle : <b>{fr(s['facture_kEUR'], 1)} k€</b><br>
        Prix moyen : <b>{fr(s['prix_moyen'], 1)} c€/kWh</b>
    </div>
    """


def icone_cluster(couleur):
    return f"""
    function(cluster) {{
        return L.divIcon({{
            html: '<div style="background:{couleur}; color:white; border:2px solid white; border-radius:50%;'
                + ' width:32px; height:32px; line-height:28px; text-align:center; font-weight:bold;'
                + ' box-shadow:0 0 0 3px rgba(0,0,0,0.15);">' + cluster.getChildCount() + '</div>',
            className: '',
            iconSize: L.point(32, 32)
        }});
    }}
    """


def carte_html(types):
    """Construit la carte Folium du TP2 pour les types sélectionnés et renvoie son code HTML."""
    sites = DONNEES["sites"]
    centre = [sites["lat"].mean(), sites["lon"].mean()]
    carte = folium.Map(location=centre, zoom_start=12)
    d = sites[sites["type"].isin(types)]

    for t in types:
        groupe = folium.FeatureGroup(name=f"<span style='color:{COULEURS[t]}'>●</span> {NOMS_GROUPES[t]}").add_to(carte)
        cluster = MarkerCluster(icon_create_function=icone_cluster(COULEURS[t]),
                                options={"disableClusteringAtZoom": 15}).add_to(groupe)
        for _, s in d[d["type"] == t].iterrows():
            folium.CircleMarker(
                location=[s["lat"], s["lon"]], radius=9,
                color="white", weight=2, fill=True, fill_color=COULEURS[t], fill_opacity=0.9,
                tooltip=f"{s['site']} ({t})", popup=folium.Popup(fiche(s), max_width=280),
            ).add_to(cluster)

    for tranche in TRANCHES:
        style = STYLE_TRANCHE[tranche]
        groupe = folium.FeatureGroup(name=f"<span style='color:{style['couleur']}'>◯</span> {tranche}",
                                     show=False).add_to(carte)
        for _, s in d[d["tranche"] == tranche].iterrows():
            folium.CircleMarker(
                location=[s["lat"], s["lon"]], radius=style["rayon"],
                color=style["couleur"], weight=3, fill=False,
                tooltip=f"{s['site']} : {tranche}", popup=folium.Popup(fiche(s), max_width=280),
            ).add_to(groupe)

    folium.LayerControl(collapsed=False).add_to(carte)

    # Légende compacte (TP2), limitée aux types sélectionnés
    lignes_types = "".join(
        f"<div><span style='display:inline-block;width:10px;height:10px;border-radius:50%;"
        f"background:{COULEURS[t]};margin-right:6px;'></span>{t}</div>" for t in types)
    lignes_tranches = "".join(
        f"<div><span style='display:inline-block;width:{STYLE_TRANCHE[tr]['rayon'] // 2}px;"
        f"height:{STYLE_TRANCHE[tr]['rayon'] // 2}px;border-radius:50%;border:2px solid {STYLE_TRANCHE[tr]['couleur']};"
        f"margin-right:6px;vertical-align:middle;'></span>{tr.replace('Facture ', '').capitalize()}</div>"
        for tr in TRANCHES)
    legende = f"""
    <div style="position: fixed; bottom: 25px; right: 10px; z-index: 9999; max-width: 210px;
                background: rgba(255,255,255,0.92); padding: 8px 10px; border-radius: 6px;
                box-shadow: 0 1px 4px rgba(0,0,0,0.3); font-family: Arial; font-size: 11px; line-height: 1.45;">
      <b>Type (point)</b>{lignes_types}
      <b style="display:block; margin-top:4px;">Facture annuelle (anneau)</b>{lignes_tranches}
      <div style="margin-top:4px; color:#6B7280;">Positions représentatives.</div>
    </div>
    """
    carte.get_root().html.add_child(folium.Element(legende))

    return carte.get_root().render()       # la carte devient une page HTML, affichée dans un html.Iframe


# =====================================================================
# 4. LAYOUT : organisation des éléments à l'écran
# =====================================================================
app = Dash(__name__)
app.title = "Consommation électrique — Rethel"
server = app.server           # TP5 : c'est cette variable que gunicorn lance sur Render


# TP5 : premier chargement des données dès le démarrage (et pas à la 1re visite),
# pour que la page s'affiche tout de suite, même sur le petit serveur de Render.
charger_donnees()

STYLE_BLOC = {"background": "white", "borderRadius": "8px", "padding": "10px",
               "boxShadow": "0 1px 4px rgba(0,0,0,0.15)"}

app.layout = html.Div(style={"fontFamily": "Arial", "background": "#F3F4F6", "padding": "20px 30px"}, children=[

    # Titre
    html.H1("Consommation électrique de nos clients", style={"marginBottom": "0", "color": "#1F2937"}),
    html.P("10 sites autour de Rethel · analyses du TP1 et carte du TP2 réunies dans un seul tableau de bord",
           style={"color": "#6B7280", "marginTop": "4px"}),

    # Zone du filtre transversal
    html.Div(style={**STYLE_BLOC, "display": "flex", "alignItems": "center", "gap": "20px"}, children=[
        html.Label("Type de consommateur :", style={"fontWeight": "bold"}),
        dcc.Checklist(
            id="filtre-type",
            options=[{"label": NOMS_GROUPES[t], "value": t} for t in TYPES],   # libellés clairs
            value=TYPES,                                                     # tout est coché au départ
            inline=True,
            inputStyle={"marginRight": "6px", "marginLeft": "14px"},
        ),
        html.Div(id="chiffres-cles", style={"marginLeft": "auto", "color": "#1F2937"}),
        html.Button("Refresh", id="bouton-actualiser", n_clicks=0,
                    style={"padding": "8px 14px", "borderRadius": "6px", "border": "1px solid #D1D5DB",
                           "background": "#1F2937", "color": "white", "cursor": "pointer"}),
    ]),
    html.Div(id="info-donnees", style={"color": "#6B7280", "fontSize": "12px", "margin": "6px 4px 0"}),

    # Zone graphique 1 : heatmap (TP1 – Q3)
    html.Div(style={**STYLE_BLOC, "marginTop": "16px"}, children=[
        dcc.Loading(dcc.Graph(id="graph-heatmap"), type="circle")]),

    # Zone graphique 2 + carte, côte à côte
    html.Div(style={"display": "flex", "gap": "16px", "marginTop": "16px"}, children=[
        html.Div(style={**STYLE_BLOC, "flex": "1"}, children=[
            dcc.Loading(dcc.Graph(id="graph-scatter"), type="circle")]),
        html.Div(style={**STYLE_BLOC, "flex": "1"}, children=[
            html.H3("Où sont les sites ?", style={"margin": "4px 0 8px 6px", "fontSize": "16px"}),
            html.Iframe(id="carte", style={"width": "100%", "height": "420px", "border": "none"}),
        ]),
    ]),
])


# =====================================================================
# 5. CALLBACK : le filtre OU le bouton « Refresh » mettent à jour
#    les chiffres clés, les graphiques ET la carte en même temps
# =====================================================================
@app.callback(
    Output("chiffres-cles", "children"),
    Output("graph-heatmap", "figure"),
    Output("graph-scatter", "figure"),
    Output("carte", "srcDoc"),
    Output("info-donnees", "children"),
    Output("filtre-type", "value"),            # le bouton re-coche aussi tous les filtres
    Input("filtre-type", "value"),
    Input("bouton-actualiser", "n_clicks"),
)
def mettre_a_jour(types_choisis, n_clics):
    # Au premier affichage, ou après un clic sur « Refresh » : interroger la base
    if DONNEES["sites"] is None or ctx.triggered_id == "bouton-actualiser":
        charger_donnees()

    # Clic sur « Refresh » : on remet tous les types cochés
    if ctx.triggered_id == "bouton-actualiser":
        types_choisis = TYPES

    # Garder l'ordre habituel des types (Agriculteur, Industriel, Site public)
    types = [t for t in TYPES if t in (types_choisis or [])]

    if not types:
        vide = figure_vide("Cochez au moins un type de consommateur")
        return ("Aucun site sélectionné", vide, vide,
                "<p style='font-family:Arial'>Aucun site à afficher.</p>", DONNEES["info"], types)

    sites = DONNEES["sites"]
    selection = sites[sites["type"].isin(types)]
    chiffres = [
        html.B(f"{len(selection)} sites"), " · ",
        html.B(f"{fr(selection['conso_MWh'].sum())} MWh"), " · ",
        html.B(f"{fr(selection['facture_kEUR'].sum())} k€"), " par an",
    ]
    return (chiffres, figure_heatmap(types), figure_scatter(types), carte_html(types), DONNEES["info"], types)


# =====================================================================
# 6. LANCEMENT
# =====================================================================
# En local seulement (sur Render, c'est gunicorn qui lance « server »).
# debug=False : avec debug=True, Dash relance le fichier une 2e fois au démarrage
# et la base serait reconstruite deux fois.
if __name__ == "__main__":
    app.run(debug=False)