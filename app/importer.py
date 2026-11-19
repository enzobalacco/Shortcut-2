"""Import de la vidéo : yt-dlp d'abord (gratuit), Apify ensuite (payant, seulement si autorisé)."""
import json, shutil, subprocess, time, urllib.request, urllib.error
from pathlib import Path
from urllib.parse import urlparse
from . import config, jobs
from .media import sonder, FichierIllisible
from .urlcheck import url_canonique


class ImportEchoue(RuntimeError):
    pass


def classer_erreur(texte: str) -> str:
    t = texte.lower()
    if "sign in to confirm" in t or "not a bot" in t:
        return "YouTube a refusé l'importeur : il demande de se connecter pour prouver que ce n'est pas un robot (blocage anti-robot sur l'adresse du serveur)."
    if "private video" in t:
        return "La vidéo est privée : passe-la en « non répertoriée » ou « publique »."
    if "unavailable" in t or "not available" in t:
        return "La vidéo est indisponible depuis ce serveur (supprimée, restreinte ou bloquée)."
    if "429" in t or "too many requests" in t:
        return "YouTube limite les requêtes de ce serveur (erreur 429). Réessaie plus tard."
    return "Erreur de l'importeur : " + texte.strip()[-300:]


def dossier_source(video_id: str) -> Path:
    d = config.DATA_DIR / "sources" / video_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _verifier(chemin: Path) -> dict:
    info = sonder(chemin)
    if info["duree"] > config.MAX_DURATION_S + 2:
        raise ImportEchoue(f"Vidéo trop longue ({info['duree']:.0f} s, maximum {config.MAX_DURATION_S} s).")
    if info["taille"] > config.MAX_BYTES:
        raise ImportEchoue("Fichier trop volumineux.")
    return info


def via_ytdlp(video_id: str, dest: Path) -> None:
    cmd = ["yt-dlp", "--no-playlist", "--no-progress", "--socket-timeout", "30",
           "--max-filesize", str(config.MAX_BYTES),
           "--match-filters", f"duration<={config.MAX_DURATION_S}",
           "-f", "bv*[height<=720]+ba/b[height<=720]/b", "--merge-output-format", "mp4",
           *config.YTDLP_EXTRA_ARGS, "-o", str(dest), url_canonique(video_id)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=config.YTDLP_TIMEOUT_S)
    except FileNotFoundError:
        raise ImportEchoue("yt-dlp n'est pas installé sur ce serveur.")
    except subprocess.TimeoutExpired:
        raise ImportEchoue("Délai dépassé pendant la récupération de la vidéo.")
    if r.returncode != 0:
        raise ImportEchoue(classer_erreur(r.stderr or r.stdout))
    if not dest.exists():
        raise ImportEchoue(f"Aucun fichier récupéré (vidéo plus longue que {config.MAX_DURATION_S} s ou filtrée).")


# ---------- Apify ----------
def hote_apify_autorise(url: str) -> bool:
    p = urlparse(url)
    h = (p.hostname or "").lower()
    return p.scheme == "https" and (h == "apify.com" or h.endswith(".apify.com") or h.endswith(".apifyusercontent.com"))


def _api(chemin: str, methode="GET", corps=None, params=""):
    req = urllib.request.Request(f"https://api.apify.com/v2/{chemin}{params}", method=methode,
                                 data=json.dumps(corps).encode() if corps is not None else None,
                                 headers={"Authorization": f"Bearer {config.APIFY_TOKEN}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read() or b"null")


def via_apify(video_id: str, dest: Path) -> None:
    if not (config.APIFY_TOKEN and config.APIFY_ACTOR and config.APIFY_INPUT_JSON):
        raise ImportEchoue("Apify n'est pas configuré (APIFY_TOKEN, APIFY_ACTOR, APIFY_INPUT_JSON).")
    job = jobs.lire(video_id) or {}
    run_id = job.get("apify_run_id")
    try:
        if not run_id:  # une seule exécution payante par vidéo ; ensuite on RELIT le résultat
            corps = json.loads(config.APIFY_INPUT_JSON.replace("{url}", url_canonique(video_id)))
            run = _api(f"acts/{config.APIFY_ACTOR}/runs", "POST", corps, f"?maxTotalChargeUsd={config.APIFY_MAX_USD}")["data"]
            run_id = run["id"]
            jobs.ecrire(video_id, apify_run_id=run_id)
        fin = time.time() + config.APIFY_TIMEOUT_S
        while True:
            run = _api(f"actor-runs/{run_id}")["data"]
            if run["status"] in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
                break
            if time.time() > fin:
                raise ImportEchoue(f"Apify : délai dépassé (exécution {run_id} toujours en cours, rien n'est relancé).")
            time.sleep(5)
        items = _api(f"datasets/{run['defaultDatasetId']}/items", params="?clean=true") or []
        fichiers = [i for i in items if isinstance(i, dict) and i.get("downloadedFileUrl")]
        if not fichiers:
            try:
                req = urllib.request.Request(f"https://api.apify.com/v2/logs/{run_id}",
                                             headers={"Authorization": f"Bearer {config.APIFY_TOKEN}"})
                log = urllib.request.urlopen(req, timeout=30).read().decode("utf8", "replace")[-1500:]
            except Exception:
                log = ""
            statut = f"statut Apify « {run['status']} »"
            raise ImportEchoue(f"Apify n'a produit aucun fichier ({statut}, résultat : {json.dumps(items)[:200]}). "
                               + classer_erreur(log) if log else f"Apify n'a produit aucun fichier ({statut}).")
        item = fichiers[0]
        if video_id not in json.dumps(item):
            raise ImportEchoue("Le fichier Apify ne correspond pas à la vidéo demandée.")
        url = item["downloadedFileUrl"]
        if not hote_apify_autorise(url):
            raise ImportEchoue("Adresse de fichier refusée (hôte non autorisé).")
        req = urllib.request.Request(url)
        if (urlparse(url).hostname or "") == "api.apify.com":
            req.add_header("Authorization", f"Bearer {config.APIFY_TOKEN}")
        tmp = dest.with_suffix(".part")
        taille = 0
        with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
            while chunk := r.read(1 << 20):
                taille += len(chunk)
                if taille > config.MAX_BYTES:
                    raise ImportEchoue("Fichier trop volumineux.")
                f.write(chunk)
        tmp.replace(dest)
    except urllib.error.HTTPError as e:
        raise ImportEchoue(f"Erreur du fournisseur Apify (HTTP {e.code}).")
    except urllib.error.URLError as e:
        raise ImportEchoue(f"Apify injoignable : {e.reason}")


def importer(video_id: str) -> None:
    """Tâche complète. Le succès n'est déclaré qu'après vérification ffprobe."""
    dest = dossier_source(video_id) / "source.mp4"
    try:
        if dest.exists():
            try:
                info = _verifier(dest)
                jobs.ajouter_tentative(video_id, "reutilisation", True, "fichier déjà présent")
                return jobs.ecrire(video_id, etat="termine", fichier=str(dest), info=info)
            except (FichierIllisible, ImportEchoue):
                dest.unlink(missing_ok=True)
        methodes = [("yt-dlp", via_ytdlp)]
        if config.ALLOW_APIFY:
            methodes.append(("apify", via_apify))
        derniere = "Aucune méthode d'import disponible."
        for nom, fn in methodes:
            try:
                fn(video_id, dest)
                info = _verifier(dest)
                jobs.ajouter_tentative(video_id, nom, True, f"{info['duree']:.1f} s, {info['largeur']}x{info['hauteur']}")
                return jobs.ecrire(video_id, etat="termine", fichier=str(dest), info=info)
            except (ImportEchoue, FichierIllisible) as e:
                dest.unlink(missing_ok=True)
                derniere = str(e)
                jobs.ajouter_tentative(video_id, nom, False, derniere)
        jobs.ecrire(video_id, etat="echec", erreur=derniere)
    except Exception as e:  # jamais de tâche bloquée « en cours »
        jobs.ecrire(video_id, etat="echec", erreur=f"Erreur inattendue : {e}")
