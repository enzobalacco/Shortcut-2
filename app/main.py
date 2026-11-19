import secrets, shutil
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

PAGE = """<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>ShortCuT</title><body style="font-family:system-ui;max-width:680px;margin:6vh auto;padding:0 16px">
<h1>ShortCuT</h1>
<h3>1. Ta vidéo</h3>
<p><b>Déposer un fichier</b> (méthode fiable) :<br><input type=file id=f accept="video/*"> <button id=bf>Envoyer</button></p>
<p><b>Ou coller un lien YouTube</b> (souvent bloqué par YouTube depuis un serveur) :<br>
<input id=u placeholder="https://www.youtube.com/watch?v=..." style="width:100%;padding:8px;font-size:16px"><button id=bu style="margin-top:6px">Récupérer par lien</button></p>
<pre id=o style="white-space:pre-wrap;background:#f4f4f4;padding:12px"></pre>
<div id=suite></div>
<script>
const $=id=>document.getElementById(id),o=$('o'),suite=$('suite');let vid=null;
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function api(u,opt){const r=await fetch(u,opt);let d={};try{d=await r.json()}catch(e){}
 if(!r.ok)throw new Error(d.erreur||d.detail||('Erreur '+r.status));return d}
function post(u,b){return api(u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b||{})})}
async function suivre(id){for(;;){const j=await api('/api/jobs/'+id);
 o.textContent='État : '+j.etat+(j.erreur?'\nErreur : '+j.erreur:'')+(j.info?'\nFichier OK : '+j.info.duree.toFixed(1)+' s, '+j.info.largeur+'x'+j.info.hauteur+' (vidéo + audio vérifiés)':'')+'\n\nTentatives :\n'+(j.tentatives||[]).map(t=>'- '+t.methode+' : '+(t.ok?'OK ':'ÉCHEC ')+t.detail).join('\n');
 if(j.etat!='en_cours')return j;await sleep(3000)}}
async function etape(id,nom){for(;;){const j=await api('/api/jobs/'+id);const e=(j.etapes||{})[nom]||{};
 if(e.etat=='termine')return;if(e.etat=='echec')throw new Error(e.erreur||'Échec');await sleep(3000)}}
async function apres(id){vid=id;suite.innerHTML='<h3>2. Transcription</h3><p id=t>Transcription du français en cours (1ère fois : téléchargement du modèle, quelques minutes)...</p>';
 try{await post('/api/jobs/'+id+'/transcrire');await etape(id,'transcription');
 const p=await api('/api/jobs/'+id+'/propositions');$('t').textContent='Transcription terminée.';
 suite.innerHTML+='<h3>3. Extraits proposés (20 s)</h3>'+p.propositions.map(x=>'<p><b>'+x.debut+' s → '+x.fin+' s</b><br>'+x.extrait.replace(/</g,'&lt;')+'<br><button data-d="'+x.debut+'">Exporter ce clip vertical</button></p>').join('')+'<div id=res></div>';
 suite.querySelectorAll('button[data-d]').forEach(b=>b.onclick=()=>exporter(id,b));}
 catch(e){$('t').textContent='Erreur : '+e.message}}
async function exporter(id,b){b.disabled=true;$('res').textContent='Création du clip...';
 try{const r=await post('/api/jobs/'+id+'/exporter',{debut:parseFloat(b.dataset.d)});await etape(id,r.etape);
 const u='/api/jobs/'+id+'/clips/'+r.fichier;$('res').innerHTML='<video src="'+u+'" controls playsinline style="max-width:270px"></video><p><a href="'+u+'" download>Télécharger le MP4</a></p>'}
 catch(e){$('res').textContent='Erreur : '+e.message}b.disabled=false}
$('bf').onclick=async()=>{const f=$('f').files[0];if(!f){o.textContent='Choisis un fichier.';return}
 $('bf').disabled=true;o.textContent='Envoi en cours...';
 try{const fd=new FormData();fd.append('fichier',f);const d=await api('/api/upload',{method:'POST',body:fd});await suivre(d.video_id);await apres(d.video_id)}
 catch(e){o.textContent='Erreur : '+e.message}$('bf').disabled=false};
$('bu').onclick=async()=>{$('bu').disabled=true;o.textContent='Envoi...';
 try{const d=await post('/api/import',{url:$('u').value});o.textContent=d.nouveau?'Import lancé...':'Un import existe déjà : réutilisé, rien n\'est relancé.';
 const j=await suivre(d.video_id);if(j.etat=='termine')await apres(d.video_id)}
 catch(e){o.textContent='Erreur : '+e.message}$('bu').disabled=false};
</script></body>"""
