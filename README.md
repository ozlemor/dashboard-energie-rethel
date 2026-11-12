# Dashboard – Consommation électrique de 10 sites (Rethel)

**👉 Dashboard en ligne : https://dashboard-energie-rethel.onrender.com**

> ⏳ Hébergé sur le plan gratuit de Render : après 15 minutes sans visite, le service se met en veille.
> Le premier chargement peut donc prendre 30 à 60 secondes.

Projet réalisé dans le module **Visualisation interactive** (MSc2 DATA).
Le dashboard réunit dans une seule page les analyses Plotly (TP1), la carte Folium (TP2),
l'application Dash (TP3) et la base SQLite (TP4), puis il est mis en ligne (TP5).

---

## Le contexte

Un fournisseur d'électricité suit **10 clients** autour de Rethel (Ardennes) :
4 agriculteurs, 4 industriels et 2 sites publics.
Pour chaque site, on a une mesure de puissance **toutes les 5 minutes pendant un an**,
soit **1 051 776 relevés**.

**Question :** qui consomme, quand, et combien ça coûte ?
Peut-on réduire la facture en déplaçant une partie de la consommation vers les **heures creuses** (22h – 6h) ?

## Ce que montre le dashboard

| Élément | Ce qu'il montre |
|---|---|
| **Chiffres clés** | Nombre de sites, consommation annuelle (MWh), facture annuelle (k€) |
| **Heatmap jour × heure** | Quand chaque type de client consomme. Seulement **22 %** de l'énergie est consommée en heures creuses |
| **Nuage de points** | Part en heures creuses vs prix moyen payé, une bulle par site (taille = facture). Le contrat pèse plus que le comportement |
| **Carte Folium** | Position des sites, couleur par type, anneau par tranche de facture, fiche détaillée au clic |
| **Filtre transversal** | Les cases à cocher (Agriculteurs / Industriels / Sites publics) mettent à jour **tous** les éléments en même temps |
| **Bouton Refresh** | Relance les requêtes SQL sur la base et remet tous les filtres |

**Quelques résultats :** 2 408 MWh consommés et **411 k€** facturés sur un an.
Les industriels représentent 49 % de l'énergie mais **63 % de la facture**.

## Architecture

```
CSV (data/)  ──►  init_db.py  ──►  energie.db (SQLite)  ──►  db.py (requêtes SQL)  ──►  app.py (Dash)
                  au démarrage                                                         graphiques + carte
```

| Fichier | Rôle |
|---|---|
| `app.py` | Application Dash : mise en page, graphiques Plotly, carte Folium, callback. Expose `server = app.server` pour gunicorn |
| `db.py` | Toutes les requêtes SQL. Chaque fonction ouvre une connexion, exécute la requête et la referme |
| `init_db.py` | Crée la base SQLite à partir des CSV. Appelé à chaque démarrage de l'application |
| `convertir_csv.py` | Script lancé une seule fois : convertit les fichiers Excel d'origine en CSV |
| `data/*.csv` | Les relevés des 10 sites (une ligne = une mesure de 5 minutes) |
| `requirements.txt` | Librairies nécessaires (dash, plotly, folium, pandas, numpy, gunicorn) |

### Base de données (SQLite)

- **consommateurs** : `id_consommateur`, `type`, `latitude`, `longitude`, `id_contrat`
- **releves** : `id_releve`, `id_consommateur`, `horodatage`, `puissance_kw`
- **tarifs** : `id_contrat`, `plage` (HP / HC), `heure_debut`, `heure_fin`, `prix_kwh`

Chaque client a son propre contrat. Les heures creuses (22h → 6h) passent minuit :
elles sont découpées en deux lignes (0h–6h et 22h–24h) pour que la jointure
`heure_debut <= heure < heure_fin` fonctionne toujours.

## Lancer le projet en local

```bash
pip install -r requirements.txt
python app.py
```

Puis ouvrir http://127.0.0.1:8050. La base `energie.db` est créée automatiquement au démarrage.

## Déploiement (Render)

| Paramètre | Valeur |
|---|---|
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn app:server --preload --timeout 120` |
| Plan | Free |

- Le fichier `.db` n'est **pas** sur GitHub (voir `.gitignore`) : sur le plan gratuit,
  le disque n'est pas conservé, donc la base est recréée à chaque démarrage à partir des CSV.
- **Optimisation :** le plan gratuit n'a que 0,1 CPU. La requête de facturation additionne d'abord
  l'énergie par site et par heure (1 million de lignes → 240 lignes), puis applique le tarif.
  Résultat identique, environ 5 fois plus rapide.
- `--preload` charge la base et les données une seule fois au démarrage ;
  `--timeout 120` laisse le temps au bouton Refresh de relancer les requêtes.

## Outils

Python · Dash · Plotly · Folium · SQLite · pandas · gunicorn · Render · GitHub

## Données

Relevés de puissance fournis dans le cadre du cours (10 sites, pas de 5 minutes, un an par site).
Les positions des sites sur la carte sont représentatives (choisies autour de Rethel pour le TP2).
