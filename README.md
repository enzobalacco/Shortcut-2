# ShortCuT

Transforme une vidéo YouTube longue en clip vertical sous-titré (1080×1920).

## Version déployée
- **Branche déployée : `main`**
- **Version : v0.2 « mode gratuit, dépôt de fichier »** — parcours : dépôt d'un fichier (ou lien YouTube, qui échoue depuis Railway) → transcription française (faster-whisper, CPU) → 3 extraits proposés → export d'un MP4 vertical de 20 s avec sous-titres.
- **Import par lien YouTube : bloqué en ligne** (vérifié le 2026-11-19 : YouTube demande une connexion anti-robot à l'adresse du serveur Railway). Apify et proxy payants non utilisés (budget 0 €).

## Variables à définir sur le serveur (jamais dans le code)
| Variable | Rôle |
|---|---|
| `APP_PASSWORD` | mot de passe de connexion |
| `SECRET` | texte aléatoire de 16+ caractères (signe le cookie) |
| `DATA_DIR` | dossier des projets ; sur Railway, le **Volume** (`/data`) |
| `ALLOW_APIFY` | laisser `0` (import payant désactivé) |
| `WHISPER_MODEL` | `base` (défaut) ou `small` (plus précis, plus lent) |
| `APIFY_TOKEN`, `APIFY_ACTOR`, `APIFY_INPUT_JSON` | Apify ; `APIFY_INPUT_JSON` contient `{url}` |
| `APIFY_MAX_USD` | plafond par exécution (défaut `1.0`) |
| `MAX_DURATION_S`, `MAX_BYTES` | limites (défaut 300 s, 300 Mo) |

## Installation et démarrage en local
```bash
pip install -r requirements-dev.txt     # + ffmpeg installé sur la machine
python -m pytest -q                      # tests
APP_PASSWORD=test SECRET=une-longue-phrase-aleatoire DATA_DIR=./data \
  uvicorn app.main:app --port 8000       # puis http://localhost:8000
```

## Ce qui est vérifié (honnêtement)
| Statut | Quoi |
|---|---|
| **Testé en local** (34 tests) | validation des liens, contrôle ffprobe vidéo+audio, rendu vertical 1080×1920 avec sous-titres, double clic = une seule tâche, tâches interrompues par un redémarrage, authentification et limite d'essais, liste blanche des hôtes Apify |
| **Simulé** | l'import : un faux `yt-dlp` copie un MP4 de test. Cela ne prouve **pas** que YouTube laisse passer le serveur |
| **Réellement fonctionné en ligne** (Railway, 2026-11-19) | démarrage, connexion par mot de passe, import par lien **refusé** avec message explicite (anti-robot YouTube). Dépôt de fichier, transcription et export : **pas encore testés en ligne** |
| **Non testé** | routes FastAPI jamais exécutées dans l'environnement de développement (FastAPI absent), faster-whisper (absent), appel Apify |

## Règle d'or de l'import
Un import n'est « réussi » que si `ffprobe` lit un fichier avec une piste vidéo **et** une piste audio. Un statut « Succeeded » d'un fournisseur ne suffit pas.
