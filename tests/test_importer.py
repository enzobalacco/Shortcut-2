"""SIMULÉ : un faux `yt-dlp` copie un MP4 de test. Ne prouve PAS que YouTube laisse passer le serveur."""
import os, stat, pytest
from app import importer, jobs, config

def faux_ytdlp(tmp_path, monkeypatch, corps):
    bin_ = tmp_path / "bin"; bin_.mkdir(exist_ok=True)
    s = bin_ / "yt-dlp"; s.write_text("#!/bin/sh\n" + corps); s.chmod(s.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{bin_}:{os.environ['PATH']}")

def test_succes_simule_et_reutilisation(data, mp4, monkeypatch):
    faux_ytdlp(data, monkeypatch, f'while [ "$1" != "-o" ]; do shift; done; cp {mp4} "$2"\n')
    importer.importer("zBjJUV-lzHo")
    j = jobs.lire("zBjJUV-lzHo")
    assert j["etat"] == "termine" and j["info"]["duree"] > 4
    faux_ytdlp(data, monkeypatch, "exit 1\n")   # plus aucun import possible : on doit réutiliser le fichier
    importer.importer("zBjJUV-lzHo")
    assert jobs.lire("zBjJUV-lzHo")["tentatives"][-1]["methode"] == "reutilisation"

def test_blocage_anti_robot_message_explicite(data, monkeypatch):
    faux_ytdlp(data, monkeypatch, 'echo "ERROR: Sign in to confirm you\'re not a bot" >&2; exit 1\n')
    importer.importer("zBjJUV-lzHo")
    j = jobs.lire("zBjJUV-lzHo")
    assert j["etat"] == "echec" and "anti-robot" in j["erreur"]

def test_succes_sans_fichier_n_est_pas_un_succes(data, monkeypatch):
    faux_ytdlp(data, monkeypatch, "exit 0\n")   # « réussi » mais aucun fichier (comme NO_RESULTS)
    importer.importer("zBjJUV-lzHo")
    assert jobs.lire("zBjJUV-lzHo")["etat"] == "echec"

def test_video_trop_longue_refusee(data, mp4, monkeypatch):
    monkeypatch.setattr(config, "MAX_DURATION_S", 2)
    faux_ytdlp(data, monkeypatch, f'while [ "$1" != "-o" ]; do shift; done; cp {mp4} "$2"\n')
    importer.importer("zBjJUV-lzHo")
    assert "trop longue" in jobs.lire("zBjJUV-lzHo")["erreur"]

@pytest.mark.parametrize("u,ok", [
    ("https://api.apify.com/v2/key-value-stores/x/records/y", True),
    ("https://abc.apifyusercontent.com/f.mp4", True),
    ("http://api.apify.com/x", False), ("https://evil.com/x", False),
    ("https://apify.com.evil.com/x", False), ("https://127.0.0.1/x", False)])
def test_hotes_apify(u, ok):
    assert importer.hote_apify_autorise(u) is ok
