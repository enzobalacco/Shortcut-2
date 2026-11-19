import secrets, shutil
from pathlib import Path
from fastapi import FastAPI, Request, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse
from . import config, jobs, auth, importer, pipeline, media
from .urlcheck import extraire_id_youtube, LienInvalide, id_valide

app = FastAPI(title="ShortCuT")


@app.on_event("startup")
def demarrage():
    if not config.APP_PASSWORD or len(config.SECRET) < 16:
        raise RuntimeError("Définis APP_PASSWORD et SECRET (16 caractères minimum) dans les variables du serveur.")
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    jobs.reprise_apres_redemarrage()


def _connecte(request: Request) -> None:
    if not auth.cookie_valide(request.cookies.get("sc")):
        raise HTTPException(401, "Connexion requise.")


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/", response_class=HTMLResponse)
def accueil(request: Request):
    if not auth.cookie_valide(request.cookies.get("sc")):
        return LOGIN
    return PAGE


@app.post("/login")
def login(request: Request, mot_de_passe: str = Form(...)):
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[0].strip()
    if not auth.mot_de_passe_ok(mot_de_passe, ip):
        return HTMLResponse(LOGIN.replace("<!--err-->", "<p style='color:#c00'>Mot de passe refusé (ou trop d'essais, attends 10 min).</p>"), status_code=401)
    r = RedirectResponse("/", status_code=303)
    r.set_cookie("sc", auth.creer_cookie(), httponly=True, secure=True, samesite="lax", max_age=auth.DUREE)
    return r


@app.post("/api/import")
async def lancer_import(request: Request):
    _connecte(request)
    corps = await request.json()
    try:
        vid = extraire_id_youtube(str(corps.get("url", "")))
    except LienInvalide as e:
        return JSONResponse({"erreur": str(e)}, status_code=400)
    job, nouveau = jobs.demarrer(vid, importer.importer)
    return {"video_id": vid, "nouveau": nouveau, "etat": job["etat"]}


def _job(video_id: str) -> dict:
    if not id_valide(video_id):
        raise HTTPException(400, "Identifiant invalide.")
    job = jobs.lire(video_id)
    if not job:
        raise HTTPException(404, "Aucune tâche pour cette vidéo.")
    return job


@app.get("/api/jobs/{video_id}")
def etat(video_id: str, request: Request):
    _connecte(request)
    return _job(video_id)


@app.post("/api/upload")
async def deposer(request: Request, fichier: UploadFile = File(...)):
    _connecte(request)
    vid = "u" + secrets.token_urlsafe(7)
    dossier = importer.dossier_source(vid)
    dest = dossier / "source.mp4"
    taille = 0
    with open(dest, "wb") as f:
        while chunk := await fichier.read(1 << 20):
            taille += len(chunk)
            if taille > config.MAX_BYTES:
                f.close(); shutil.rmtree(dossier, ignore_errors=True)
                return JSONResponse({"erreur": f"Fichier trop volumineux (maximum {config.MAX_BYTES // 1048576} Mo)."}, status_code=413)
            f.write(chunk)
    try:
        info = importer._verifier(dest)
    except Exception as e:
        shutil.rmtree(dossier, ignore_errors=True)
        return JSONResponse({"erreur": str(e)}, status_code=400)
    jobs.ecrire(vid, etat="termine", fichier=str(dest), info=info, origine="depot")
    jobs.ajouter_tentative(vid, "depot", True, f"{info['duree']:.1f} s, {info['largeur']}x{info['hauteur']}")
    return {"video_id": vid}


@app.post("/api/jobs/{video_id}/transcrire")
def transcrire(video_id: str, request: Request):
    _connecte(request)
    if _job(video_id)["etat"] != "termine":
        raise HTTPException(409, "La vidéo n'est pas encore récupérée.")
    return {"nouveau": jobs.lancer_etape(video_id, "transcription", lambda: pipeline.transcrire(video_id))}


@app.get("/api/jobs/{video_id}/propositions")
def propositions(video_id: str, request: Request):
    _connecte(request)
    job = _job(video_id)
    try:
        segs = pipeline.lire_transcript(video_id)
    except FileNotFoundError:
        raise HTTPException(409, "Transcris d'abord la vidéo.")
    return {"propositions": pipeline.proposer(segs, job["info"]["duree"]), "transcript": segs}


@app.post("/api/jobs/{video_id}/exporter")
async def exporter(video_id: str, request: Request):
    _connecte(request)
    _job(video_id)
    try:
        debut = float((await request.json()).get("debut", 0))
    except (TypeError, ValueError):
        raise HTTPException(400, "Début invalide.")
    nom = f"clip_{int(max(debut, 0))}"
    nouveau = jobs.lancer_etape(video_id, nom, lambda: pipeline.exporter(video_id, debut))
    return {"etape": nom, "nouveau": nouveau, "fichier": nom + ".mp4"}


@app.get("/api/jobs/{video_id}/clips/{nom}")
def telecharger(video_id: str, nom: str, request: Request):
    _connecte(request)
    _job(video_id)
    if not pipeline.CLIP_RE.match(nom):
        raise HTTPException(400, "Nom de clip invalide.")
    p = pipeline.dossier(video_id) / nom
    if not p.is_file():
        raise HTTPException(404, "Clip introuvable.")
    return FileResponse(p, media_type="video/mp4", filename=f"shortcut_{video_id}_{nom}")


LOGIN = """<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>ShortCuT</title><body style="font-family:system-ui;max-width:420px;margin:15vh auto;padding:0 16px">
<h1>ShortCuT</h1><!--err--><form method=post action=/login>
<input type=password name=mot_de_passe placeholder="Mot de passe" autofocus style="width:100%;padding:10px;font-size:16px">
<button style="margin-top:10px;padding:10px 16px;font-size:16px">Entrer</button></form></body>"""

PAGE = (Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8")
