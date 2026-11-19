from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from . import config, jobs, auth, importer
from .urlcheck import extraire_id_youtube, LienInvalide

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


@app.get("/api/jobs/{video_id}")
def etat(video_id: str, request: Request):
    _connecte(request)
    try:
        extraire_id_youtube(f"https://youtu.be/{video_id}")
    except LienInvalide:
        raise HTTPException(400, "Identifiant invalide.")
    job = jobs.lire(video_id)
    if not job:
        raise HTTPException(404, "Aucune tâche pour cette vidéo.")
    return job


LOGIN = """<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>ShortCuT</title><body style="font-family:system-ui;max-width:420px;margin:15vh auto;padding:0 16px">
<h1>ShortCuT</h1><!--err--><form method=post action=/login>
<input type=password name=mot_de_passe placeholder="Mot de passe" autofocus style="width:100%;padding:10px;font-size:16px">
<button style="margin-top:10px;padding:10px 16px;font-size:16px">Entrer</button></form></body>"""

PAGE = """<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>ShortCuT</title><body style="font-family:system-ui;max-width:640px;margin:8vh auto;padding:0 16px">
<h1>ShortCuT</h1><p>Colle un lien YouTube :</p>
<input id=u placeholder="https://www.youtube.com/watch?v=..." style="width:100%;padding:10px;font-size:16px">
<button id=b style="margin-top:10px;padding:10px 16px;font-size:16px">Récupérer la vidéo</button>
<pre id=o style="white-space:pre-wrap;background:#f4f4f4;padding:12px;margin-top:16px"></pre>
<script>
const o=document.getElementById('o'),b=document.getElementById('b');
b.onclick=async()=>{b.disabled=true;o.textContent='Envoi...';
 try{const r=await fetch('/api/import',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:document.getElementById('u').value})});
 const d=await r.json();if(!r.ok){o.textContent=d.erreur||d.detail||'Erreur';b.disabled=false;return}
 o.textContent=d.nouveau?'Import lancé...':'Un import existe déjà pour cette vidéo : réutilisé, rien n\\'est relancé.';
 const t=setInterval(async()=>{const j=await (await fetch('/api/jobs/'+d.video_id)).json();
  o.textContent='État : '+j.etat+(j.erreur?'\\nErreur : '+j.erreur:'')+(j.info?'\\nFichier OK : '+j.info.duree.toFixed(1)+' s, '+j.info.largeur+'x'+j.info.hauteur+' (vidéo + audio vérifiés)':'')+'\\n\\nTentatives :\\n'+(j.tentatives||[]).map(t=>'- '+t.methode+' : '+(t.ok?'OK ':'ÉCHEC ')+t.detail).join('\\n');
  if(j.etat!='en_cours'){clearInterval(t);b.disabled=false}},3000)}
 catch(e){o.textContent='Erreur réseau';b.disabled=false}};
</script></body>"""
