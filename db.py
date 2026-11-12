"""
TP4 / TP5 — Module d'accès aux données.
Toutes les lectures de la base passent par ici. Chaque fonction ouvre une
connexion, exécute sa requête, puis ferme la connexion (pas de connexion permanente).
La base est la seule source de vérité : le bouton « Refresh » relance simplement
ces requêtes, donc toute modification faite dans la base apparaît dans le dashboard.
"""
import sqlite3
from contextlib import closing

import pandas as pd

from init_db import FICHIER_DB    # même nom de fichier que dans init_db.py

# Morceau de SQL réutilisé : relier chaque relevé à la bonne ligne tarifaire
# (même contrat que le consommateur ET heure du relevé dans la plage horaire)
JOINTURE_TARIF = """
    JOIN consommateurs c ON c.id_consommateur = r.id_consommateur
    JOIN tarifs t        ON t.id_contrat = c.id_contrat
                        AND CAST(strftime('%H', r.horodatage) AS INTEGER) >= t.heure_debut
                        AND CAST(strftime('%H', r.horodatage) AS INTEGER) <  t.heure_fin
"""


def executer(requete, parametres=()):
    """Ouvre une connexion, exécute la requête, renvoie un DataFrame, puis ferme la connexion."""
    with closing(sqlite3.connect(FICHIER_DB)) as con:
        return pd.read_sql_query(requete, con, params=parametres)


def synthese_par_site():
    """Une ligne par consommateur : type, position, énergie, facture, part HC, prix moyen.
    Optimisation (TP5) : on additionne d'abord l'énergie par site et par heure
    (1 million de relevés -> 240 lignes), puis on applique le tarif sur ces 240 lignes.
    Résultat identique, mais beaucoup plus rapide sur le petit serveur gratuit de Render."""
    requete = """
        WITH energie_par_heure AS (
            SELECT id_consommateur,
                   CAST(substr(horodatage, 12, 2) AS INTEGER) AS heure,     -- 'AAAA-MM-JJ HH:MM:SS' -> HH
                   SUM(puissance_kw * 5.0 / 60)               AS energie_kWh
            FROM releves
            GROUP BY id_consommateur, heure
        )
        SELECT c.id_consommateur                                           AS site,
               c.type,
               c.latitude                                                  AS lat,
               c.longitude                                                 AS lon,
               SUM(e.energie_kWh)                                          AS energie_kWh,
               SUM(CASE WHEN t.plage = 'HC' THEN e.energie_kWh ELSE 0 END) AS energie_HC_kWh,
               SUM(e.energie_kWh * t.prix_kwh)                             AS cout_EUR
        FROM energie_par_heure e
        JOIN consommateurs c ON c.id_consommateur = e.id_consommateur
        JOIN tarifs t        ON t.id_contrat = c.id_contrat
                            AND e.heure >= t.heure_debut
                            AND e.heure <  t.heure_fin
        GROUP BY c.id_consommateur, c.type, c.latitude, c.longitude
        ORDER BY c.id_consommateur
    """
    sites = executer(requete)
    sites["part_HC"] = sites["energie_HC_kWh"] / sites["energie_kWh"] * 100      # %
    sites["prix_moyen"] = sites["cout_EUR"] / sites["energie_kWh"] * 100          # c€/kWh
    sites["conso_MWh"] = sites["energie_kWh"] / 1000
    sites["facture_kEUR"] = sites["cout_EUR"] / 1000
    return sites


def profil_horaire():
    """Puissance moyenne (kW) par type, jour de la semaine (0 = lundi) et heure : pour la heatmap."""
    requete = """
        SELECT c.type,
               (CAST(strftime('%w', r.horodatage) AS INTEGER) + 6) % 7 AS jour,
               CAST(strftime('%H', r.horodatage) AS INTEGER)           AS heure,
               AVG(r.puissance_kw)                                     AS puissance_kw
        FROM releves r
        JOIN consommateurs c ON c.id_consommateur = r.id_consommateur
        GROUP BY c.type, jour, heure
    """
    return executer(requete)


def nombre_releves():
    """Nombre total de relevés dans la base (affiché dans le dashboard)."""
    return int(executer("SELECT COUNT(*) AS n FROM releves")["n"].iloc[0])