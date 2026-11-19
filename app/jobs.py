"""Suivi des tâches, sur disque (survit à un redémarrage si DATA_DIR est un Volume)."""
import json, threading, time
from pathlib import Path
from . import config

_lock = threading.Lock()


def _f(video_id: str) -> Path:
    d = config.DATA_DIR / "jobs"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{video_id}.json"


def lire(video_id: str) -> dict | None:
    p = _f(video_id)
    return json.loads(p.read_text()) if p.exists() else None


def ecrire(video_id: str, **champs) -> dict:
    with _lock:
        job = lire(video_id) or {"video_id": video_id, "etat": "en_attente", "tentatives": [], "cree": time.time()}
        job.update(champs)
        job["maj"] = time.time()
        _f(video_id).write_text(json.dumps(job, ensure_ascii=False, indent=1))
        return job


def ajouter_tentative(video_id: str, methode: str, ok: bool, detail: str) -> None:
    job = lire(video_id) or {}
    t = job.get("tentatives", []) + [{"methode": methode, "ok": ok, "detail": detail[:600], "t": time.time()}]
    ecrire(video_id, tentatives=t)


def demarrer(video_id: str, travail) -> tuple[dict, bool]:
    """Double clic : si une tâche tourne ou est terminée, on la renvoie sans rien relancer."""
    with _lock:
        job = lire(video_id)
        if job and job["etat"] in ("en_cours", "termine"):
            return job, False
    job = ecrire(video_id, etat="en_cours", erreur=None)
    threading.Thread(target=travail, args=(video_id,), daemon=True).start()
    return job, True


def reprise_apres_redemarrage() -> None:
    d = config.DATA_DIR / "jobs"
    if not d.exists():
        return
    for p in d.glob("*.json"):
        j = json.loads(p.read_text())
        if j.get("etat") == "en_cours":
            ecrire(j["video_id"], etat="echec", erreur="Tâche interrompue par un redémarrage du serveur. Relance-la (le fichier déjà récupéré sera réutilisé).")
