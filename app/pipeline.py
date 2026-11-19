"""Transcription (faster-whisper, CPU, gratuit), propositions d'extraits, export du clip."""
import json, re, threading
from pathlib import Path
from . import config, media

_une_a_la_fois = threading.Semaphore(1)   # un seul Whisper à la fois : protège la mémoire du serveur
CLIP_RE = re.compile(r"^clip_\d{1,5}\.mp4$")


def dossier(video_id: str) -> Path:
    return config.DATA_DIR / "sources" / video_id


def transcrire(video_id: str) -> None:
    from faster_whisper import WhisperModel   # importé ici : le serveur démarre même sans lui
    source = dossier(video_id) / "source.mp4"
    with _une_a_la_fois:
        modele = WhisperModel(config.WHISPER_MODEL, device="cpu", compute_type="int8")
        segs, _ = modele.transcribe(str(source), language="fr", vad_filter=True)
        liste = [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()} for s in segs]
    if not liste:
        raise RuntimeError("Aucune parole détectée dans cette vidéo.")
    (dossier(video_id) / "transcript.json").write_text(json.dumps(liste, ensure_ascii=False))


def lire_transcript(video_id: str) -> list[dict]:
    p = dossier(video_id) / "transcript.json"
    if not p.exists():
        raise FileNotFoundError("Pas encore de transcription.")
    return json.loads(p.read_text())


def proposer(segments: list[dict], duree_totale: float, longueur: float = 20.0, n: int = 3) -> list[dict]:
    """Choisit les n fenêtres de `longueur` secondes les plus riches en paroles, sans chevauchement."""
    longueur = min(longueur, duree_totale)
    candidats = []
    for s in segments:
        debut = min(s["start"], max(0.0, duree_totale - longueur))
        fin = debut + longueur
        texte = " ".join(x["text"] for x in segments if x["end"] > debut and x["start"] < fin)
        candidats.append((len(texte), round(debut, 1), texte))
    choisis = []
    for score, debut, texte in sorted(candidats, key=lambda c: -c[0]):
        if all(abs(debut - c["debut"]) >= longueur for c in choisis):
            choisis.append({"debut": debut, "fin": round(debut + longueur, 1), "extrait": texte[:160]})
        if len(choisis) == n:
            break
    return sorted(choisis, key=lambda c: c["debut"])


def exporter(video_id: str, debut: float, longueur: float = 20.0) -> str:
    d = dossier(video_id)
    info = media.sonder(d / "source.mp4")
    debut = max(0.0, min(float(debut), max(0.0, info["duree"] - 1)))
    duree = min(longueur, info["duree"] - debut)
    nom = f"clip_{int(debut)}.mp4"
    srt = d / f"clip_{int(debut)}.srt"
    media.ecrire_srt(lire_transcript(video_id), debut, debut + duree, srt)
    media.rendre_clip(d / "source.mp4", debut, duree, srt, d / nom)
    media.sonder(d / nom)   # on ne déclare rien réussi sans relire le résultat
    return nom
