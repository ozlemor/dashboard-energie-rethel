"""
TP5 — Script à lancer UNE SEULE FOIS sur votre ordinateur.
Convertit les 10 fichiers Excel de data/ en fichiers CSV (même nom, extension .csv).
Pourquoi : le TP5 demande de régénérer la base à partir des CSV au démarrage,
et un CSV se lit beaucoup plus vite qu'un Excel (démarrage plus rapide sur Render).
Usage : python3 convertir_csv.py
"""
import glob
import os

import pandas as pd

from init_db import convertir_dates      # même fonction de dates que dans le TP4

for chemin in sorted(glob.glob(os.path.join("data", "*.xlsx"))):
    d = pd.read_excel(chemin)
    d.columns = ["horodatage", "puissance_W"]
    # On écrit toutes les dates dans UN SEUL format : AAAA-MM-JJ HH:MM:SS
    d["horodatage"] = convertir_dates(d["horodatage"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    chemin_csv = chemin.replace(".xlsx", ".csv")
    d.to_csv(chemin_csv, index=False)
    print(f"{os.path.basename(chemin):28s} -> {os.path.basename(chemin_csv)} ({len(d)} lignes)")