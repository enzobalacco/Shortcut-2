"""Contrôle des fichiers (ffprobe) et rendu vertical sous-titré (ffmpeg)."""
import json
import subprocess
from pathlib import Path


class FichierIllisible(RuntimeError):
    pass


def sonder(chemin: str | Path) -> dict:
    """Preuve de réussite : un vrai fichier avec une piste vidéo ET une piste audio."""
    p = Path(chemin)
    if not p.is_file() or p.stat().st_size == 0:
        raise FichierIllisible("Aucun fichier récupéré (absent ou vide).")
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(p)],
        capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise FichierIllisible(f"ffprobe ne reconnaît pas le fichier : {r.stderr.strip()[:200]}")
    info = json.loads(r.stdout)
    types = {s.get("codec_type") for s in info.get("streams", [])}
    if "video" not in types:
        raise FichierIllisible("Le fichier n'a pas de piste vidéo.")
    if "audio" not in types:
        raise FichierIllisible("Le fichier n'a pas de piste audio.")
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    return {"duree": float(info["format"].get("duration", 0)),
            "largeur": v["width"], "hauteur": v["height"],
            "taille": int(info["format"].get("size", 0))}


def _t(s: float) -> str:
    h, r = divmod(s, 3600); m, r = divmod(r, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(r):02d},{int(round((r % 1) * 1000)):03d}"


def ecrire_srt(segments: list[dict], debut: float, fin: float, sortie: str | Path) -> None:
    """segments : [{start, end, text}] en secondes de la source ; recalés sur le début du clip."""
    n, lignes = 0, []
    for s in segments:
        if s["end"] <= debut or s["start"] >= fin:
            continue
        n += 1
        a, b = max(s["start"], debut) - debut, min(s["end"], fin) - debut
        lignes.append(f"{n}\n{_t(a)} --> {_t(b)}\n{s['text'].strip()}\n")
    Path(sortie).write_text("\n".join(lignes), encoding="utf-8")


def rendre_clip(source, debut: float, duree: float, srt, sortie) -> None:
    """MP4 vertical 1080x1920, fond flouté, sous-titres incrustés."""
    srt_f = str(srt).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    fc = ("[0:v]split=2[a][b];"
          "[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=30:5[bg];"
          "[b]scale=1080:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,"
          f"subtitles='{srt_f}':force_style='Fontsize=14,Alignment=2,MarginV=180,Outline=2'[v]")
    r = subprocess.run(
        ["ffmpeg", "-y", "-ss", str(debut), "-t", str(duree), "-i", str(source),
         "-filter_complex", fc, "-map", "[v]", "-map", "0:a:0",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(sortie)],
        capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg a échoué : {r.stderr[-300:]}")
