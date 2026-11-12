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
    """Une ligne par consommateur : type, position, énergie, facture, part HC, prix moyen."""
    requete = f"""
        SELECT c.id_consommateur                                   AS site,
               c.type,
               c.latitude                                          AS lat,
               c.longitude                                         AS lon,
               SUM(r.puissance_kw * 5.0 / 60)                      AS energie_kWh,
               SUM(CASE WHEN t.plage = 'HC' THEN r.puissance_kw * 5.0 / 60 ELSE 0 END) AS energie_HC_kWh,
               SUM(r.puissance_kw * 5.0 / 60 * t.prix_kwh)         AS cout_EUR
        FROM releves r
        {JOINTURE_TARIF}
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