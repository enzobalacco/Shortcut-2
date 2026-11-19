"""Validation des liens YouTube côté serveur (aucune autre URL n'est acceptée)."""
import re
from urllib.parse import urlparse, parse_qs

_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}


class LienInvalide(ValueError):
    pass


def extraire_id_youtube(url: str) -> str:
    """Retourne l'identifiant de 11 caractères, ou lève LienInvalide."""
    p = urlparse((url or "").strip())
    if p.scheme not in ("http", "https") or p.username or p.password:
        raise LienInvalide("Lien refusé : il doit commencer par https:// et ne pas contenir d'identifiants.")
    host = (p.hostname or "").lower()
    if p.port not in (None, 80, 443):
        raise LienInvalide("Lien refusé : port non autorisé.")
    vid = None
    if host == "youtu.be":
        vid = p.path.lstrip("/").split("/")[0]
    elif host in _HOSTS:
        if p.path == "/watch":
            vid = (parse_qs(p.query).get("v") or [None])[0]
        else:
            m = re.match(r"^/(shorts|live|embed)/([^/]+)", p.path)
            vid = m.group(2) if m else None
    else:
        raise LienInvalide("Lien refusé : seuls les liens YouTube sont acceptés.")
    if not vid or not _ID.match(vid):
        raise LienInvalide("Lien refusé : identifiant de vidéo YouTube introuvable.")
    return vid


def url_canonique(video_id: str) -> str:
    """L'URL envoyée à l'importeur est toujours reconstruite, jamais copiée de l'utilisateur."""
    return f"https://www.youtube.com/watch?v={video_id}"


def id_valide(identifiant: str) -> bool:
    return bool(_ID.match(identifiant or ""))
