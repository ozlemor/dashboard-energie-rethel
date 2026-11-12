"""
TP4 et TP5 — Création de la base SQLite à partir des fichiers CSV de data/.
Usage : python3 init_db.py(recrée entièrement le fichier energie.db)
TP5 : main() est aussi appelée au démarrage de app.py,
car sur Render le fichier .db disparaît à chaque redémarrage.
"""
import glob
import os
import re
import sqlite3

import pandas as pd

FICHIER_DB = "energie.db"
DOSSIER = "data"

# ---------------------------------------------------------------------
# Informations sur les consommateurs (TP1 : type et tarif, TP2 : position)
# Chaque consommateur a SON PROPRE contrat (id_contrat).
# ---------------------------------------------------------------------
CONSOMMATEURS = {
    # id_consommateur: (type, latitude, longitude, id_contrat, prix HP €/kWh, prix HC €/kWh)
    "Agri 1":       ("Agriculteur", 49.5350, 4.3600, "CTR-AGRI-1", 0.0952, 0.0528),
    "Agri 2":       ("Agriculteur", 49.5100, 4.4050, "CTR-AGRI-2", 0.1303, 0.0962),
    "Agri 3":       ("Agriculteur", 49.4850, 4.3700, "CTR-AGRI-3", 0.1531, 0.1008),
    "Agri 4":       ("Agriculteur", 49.5145, 4.3275, "CTR-AGRI-4", 0.1417, 0.1007),
    "Industriel 1": ("Industriel",  49.5205, 4.3770, "CTR-IND-1",  0.2312, 0.1715),
    "Industriel 2": ("Industriel",  49.5195, 4.3790, "CTR-IND-2",  0.3354, 0.1715),
    "Industriel 3": ("Industriel",  49.5185, 4.3765, "CTR-IND-3",  0.1627, 0.1108),
    "Industriel 4": ("Industriel",  49.5200, 4.3810, "CTR-IND-4",  0.1238, 0.0925),
    "SP 1":         ("Site public", 49.5089, 4.3655, "CTR-SP-1",   0.1421, 0.1132),
    "SP 2":         ("Site public", 49.5160, 4.3722, "CTR-SP-2",   0.1398, 0.0767),
}


def convertir_dates(colonne):
    """Deux formats dans les fichiers Excel : de vraies dates, ou du texte « JJ/MM/AAAA HH:MM:SS ».
    (Utilisée par convertir_csv.py au moment de créer les CSV.)"""
    if pd.api.types.is_datetime64_any_dtype(colonne):
        return colonne                                            # déjà des dates : rien à faire
    return pd.to_datetime(colonne.astype(str), format="%d/%m/%Y %H:%M:%S")   # texte jour/mois/année


# ---------------------------------------------------------------------
# 1. Création de la base et des 3 tables (schéma imposé)
# ---------------------------------------------------------------------
SCHEMA = """
CREATE TABLE consommateurs (
    id_consommateur TEXT PRIMARY KEY,
    type            TEXT NOT NULL,
    latitude        REAL,
    longitude       REAL,
    id_contrat      TEXT NOT NULL
);

CREATE TABLE releves (
    id_releve       INTEGER PRIMARY KEY AUTOINCREMENT,
    id_consommateur TEXT NOT NULL REFERENCES consommateurs(id_consommateur),
    horodatage      TEXT NOT NULL,          -- format 'AAAA-MM-JJ HH:MM:SS'
    puissance_kw    REAL NOT NULL           -- puissance moyenne sur 5 minutes
);

CREATE TABLE tarifs (
    id_tarif        INTEGER PRIMARY KEY AUTOINCREMENT,
    id_contrat      TEXT NOT NULL,
    plage           TEXT NOT NULL CHECK (plage IN ('HP', 'HC')),
    heure_debut     INTEGER NOT NULL,       -- incluse
    heure_fin       INTEGER NOT NULL,       -- exclue
    prix_kwh        REAL NOT NULL           -- en € par kWh
);

-- Index pour accélérer les requêtes du dashboard
CREATE INDEX idx_releves_conso ON releves(id_consommateur);
CREATE INDEX idx_tarifs_contrat ON tarifs(id_contrat);
"""


def main():
    if os.path.exists(FICHIER_DB):
        os.remove(FICHIER_DB)                       # on repart toujours d'une base vide

    con = sqlite3.connect(FICHIER_DB)
    try:
        con.execute("PRAGMA foreign_keys = ON")
        con.executescript(SCHEMA)

        # ---------------------------------------------------------------
        # 2a. Table consommateurs : un consommateur par ligne
        # ---------------------------------------------------------------
        con.executemany(
            "INSERT INTO consommateurs VALUES (?, ?, ?, ?, ?)",
            [(cid, t, lat, lon, ctr) for cid, (t, lat, lon, ctr, _, _) in CONSOMMATEURS.items()])

        # ---------------------------------------------------------------
        # 2b. Table tarifs : une plage tarifaire par ligne
        #     Les heures creuses (22h -> 6h) passent minuit : on les découpe en
        #     deux lignes (0h-6h et 22h-24h) pour que la condition
        #     « heure_debut <= heure < heure_fin » marche toujours.
        # ---------------------------------------------------------------
        lignes_tarifs = []
        for cid, (_, _, _, ctr, prix_hp, prix_hc) in CONSOMMATEURS.items():
            lignes_tarifs += [(ctr, "HC", 0, 6, prix_hc),
                              (ctr, "HP", 6, 22, prix_hp),
                              (ctr, "HC", 22, 24, prix_hc)]
        con.executemany(
            "INSERT INTO tarifs (id_contrat, plage, heure_debut, heure_fin, prix_kwh) VALUES (?, ?, ?, ?, ?)",
            lignes_tarifs)

        # ---------------------------------------------------------------
        # 2c. Table releves : un relevé (mesure de 5 minutes) par ligne
        #     TP5 : on lit les CSV (créés une fois par convertir_csv.py)
        # ---------------------------------------------------------------
        for chemin in sorted(glob.glob(os.path.join(DOSSIER, "*.csv"))):
            nom = os.path.basename(chemin)
            m = re.match(r"(Agri|Industriel|SP)_?(\d)_(\d{4})", nom)
            if m is None:
                print(f"  fichier ignoré : {nom}")
                continue
            cid = f"{m.group(1)} {m.group(2)}"

            d = pd.read_csv(chemin)                 # CSV créés par convertir_csv.py
            d.columns = ["horodatage", "puissance_W"]
            d["horodatage"] = pd.to_datetime(d["horodatage"], format="%Y-%m-%d %H:%M:%S")
            releves = pd.DataFrame({
                "id_consommateur": cid,
                "horodatage": d["horodatage"].dt.strftime("%Y-%m-%d %H:%M:%S"),
                "puissance_kw": d["puissance_W"] / 1000,
            })
            releves.to_sql("releves", con, if_exists="append", index=False)
            print(f"  {nom:28s} -> {len(releves):>7} relevés ({cid})")

        con.commit()

        # Petit bilan
        for table in ["consommateurs", "releves", "tarifs"]:
            n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"Table {table:14s}: {n} lignes")
    finally:
        con.close()
    print(f"Base créée : {FICHIER_DB}")


if __name__ == "__main__":
    main()