import json, pytest
from app import pipeline, jobs, media

SEGS = [{"start": 0, "end": 4, "text": "ok"},
        {"start": 10, "end": 18, "text": "ceci est un long passage avec beaucoup de paroles intéressantes"},
        {"start": 18, "end": 30, "text": "et la suite du passage qui continue encore longtemps ici"},
        {"start": 60, "end": 70, "text": "un autre passage plus loin dans la vidéo avec du contenu"}]

def test_propositions_sans_chevauchement_et_dans_la_video():
    p = pipeline.proposer(SEGS, duree_totale=75, longueur=20, n=3)
    assert 1 <= len(p) <= 3
    for a, b in zip(p, p[1:]):
        assert b["debut"] - a["debut"] >= 20
    assert all(0 <= x["debut"] and x["fin"] <= 75.1 for x in p)
    assert p[0]["debut"] <= 18 and "long passage" in p[0]["extrait"]

def test_video_plus_courte_que_20s():
    p = pipeline.proposer(SEGS[:1], duree_totale=8, longueur=20, n=3)
    assert p[0]["fin"] - p[0]["debut"] == 8

def test_nom_de_clip_securise():
    assert pipeline.CLIP_RE.match("clip_30.mp4")
    for mauvais in ["../x.mp4", "clip_30.mp4/../a", "clip_a.mp4", "source.mp4", "clip_1.srt"]:
        assert not pipeline.CLIP_RE.match(mauvais)

def test_export_complet_20s_vertical(data, mp4):
    # simulé côté transcription (faux segments) ; ffmpeg réel pour le rendu
    d = pipeline.dossier("abcdefghijk"); d.mkdir(parents=True)
    (d / "source.mp4").write_bytes(mp4.read_bytes())
    (d / "transcript.json").write_text(json.dumps([{"start": 0.5, "end": 3, "text": "Bonjour tout le monde"}]))
    nom = pipeline.exporter("abcdefghijk", 0, longueur=4)
    i = media.sonder(d / nom)
    assert (i["largeur"], i["hauteur"]) == (1080, 1920) and 3.5 < i["duree"] < 4.5

def test_etape_lancee_une_seule_fois(data):
    import time
    n = []
    jobs.ecrire("abcdefghijk", etat="termine")
    assert jobs.lancer_etape("abcdefghijk", "transcription", lambda: (n.append(1), time.sleep(0.2)))
    assert not jobs.lancer_etape("abcdefghijk", "transcription", lambda: n.append(1))
    time.sleep(0.5)
    assert jobs.lire("abcdefghijk")["etapes"]["transcription"]["etat"] == "termine" and n == [1]

def test_etape_en_echec_message_clair(data):
    import time
    jobs.ecrire("abcdefghijk", etat="termine")
    def boom(): raise RuntimeError("Aucune parole détectée dans cette vidéo.")
    jobs.lancer_etape("abcdefghijk", "transcription", boom); time.sleep(0.3)
    e = jobs.lire("abcdefghijk")["etapes"]["transcription"]
    assert e["etat"] == "echec" and "parole" in e["erreur"]
