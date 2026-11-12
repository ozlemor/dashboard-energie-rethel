# Dashboard – Consommation électrique (Rethel)

**En ligne : https://dashboard-energie-rethel.onrender.com**
(plan gratuit : le premier chargement peut prendre 30 à 60 secondes)

Projet du module **Visualisation interactive** (MSc2 DATA) : dashboard Dash qui réunit
les graphiques Plotly (TP1), la carte Folium (TP2) et la base SQLite (TP4), mis en ligne sur Render (TP5).

10 sites (agriculteurs, industriels, sites publics), une mesure toutes les 5 minutes pendant un an
(1 051 776 relevés). Un filtre par type de client met à jour les graphiques et la carte,
et le bouton **Refresh** relance les requêtes SQL sur la base.

## Fichiers

| Fichier | Rôle |
|---|---|
| `app.py` | Application Dash (graphiques, carte, callback) – expose `server = app.server` |
| `db.py` | Requêtes SQL sur la base |
| `init_db.py` | Crée la base SQLite à partir des CSV, à chaque démarrage |
| `convertir_csv.py` | Conversion unique des fichiers Excel en CSV |
| `data/*.csv` | Relevés des 10 sites |
| `requirements.txt` | Librairies nécessaires |
