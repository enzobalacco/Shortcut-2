# ShortCuT

Transforme une vidéo YouTube longue en clip vertical sous-titré (1080×1920).

## Version déployée
- **Branche déployée : `main`**
- **Version : v0.1 « test d'import »** — seule l'étape *lien YouTube → fichier vérifié* est dans l'application web. La transcription Whisper, les extraits et l'export du clip sont à venir (le rendu vertical existe dans `app/media.py`, testé en local, pas encore branché sur la page).

## Variables à définir sur le serveur (jamais dans le code)
| Variable | Rôle |
|---|---|
| `APP_PASSWORD` | mot de passe de connexion |
| `SECRET` | texte aléatoire de 16+ caractères (signe le cookie) |
| `DATA_DIR` | dossier des projets ; sur Railway, le **Volume** (`/data`) |
| `ALLOW_APIFY` | `1` pour autoriser l'import payant Apify (défaut : `0`) |
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
| **Testé en local** (28 tests) | validation des liens, contrôle ffprobe vidéo+audio, rendu vertical 1080×1920 avec sous-titres, double clic = une seule tâche, tâches interrompues par un redémarrage, authentification et limite d'essais, liste blanche des hôtes Apify |
| **Simulé** | l'import : un faux `yt-dlp` copie un MP4 de test. Cela ne prouve **pas** que YouTube laisse passer le serveur |
| **Réellement fonctionné en ligne** | rien pour l'instant. À remplir après le test sur Railway |
| **Non écrit / non testé** | page FastAPI jamais lancée dans l'environnement de développement (FastAPI absent), appel Apify, Whisper, export du clip depuis la page |

## Règle d'or de l'import
Un import n'est « réussi » que si `ffprobe` lit un fichier avec une piste vidéo **et** une piste audio. Un statut « Succeeded » d'un fournisseur ne suffit pas.
