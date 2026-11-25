# vols-collector

Releve les vols qui atterrissent en France metropolitaine (aeroports LF*) sur **IVAO** et **VATSIM**, via GitHub Actions (gratuit, sans serveur).

## Fonctionnement
- Le workflow `collect` demarre toutes les 30 min et boucle ~27 min, avec un releve toutes les 2 min.
- L'etat et les arrivees sont ecrits sur la branche `data` : `arrivals.csv` (un vol par ligne) et `state.json`.
- La liste des aeroports (OurAirports) est telechargee a chaque lancement.
- Pas de secret ni de donnee personnelle : ni nom de pilote, ni CID (cle = hash).

## Mise en service
Le fichier `ci/collect.yml` doit etre deplace vers `.github/workflows/collect.yml` (l'acces GitHub de Matteo ne permet pas d'ecrire dans `.github/workflows`). Sur GitHub : ouvrir le fichier, crayon, changer le chemin en `.github/workflows/collect.yml`, commit. Puis onglet Actions, `collect`, Run workflow pour un premier test.

## Limites
- Les demarrages planifies de GitHub Actions peuvent avoir du retard : de courts trous de suivi sont possibles.
- GitHub desactive les workflows planifies apres 60 jours sans activite sur la branche par defaut.

## Local
```
pip install -r requirements.txt pytest
python -m pytest -q tests
OUT_DIR=out DURATION=60 INTERVAL=30 python collector/collector.py
```
