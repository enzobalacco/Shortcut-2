import subprocess, pytest
from app.media import sonder, ecrire_srt, rendre_clip, FichierIllisible

def _src(tmp_path, audio=True):
    out = tmp_path / "src.mp4"
    cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=25:duration=6"]
    if audio: cmd += ["-f", "lavfi", "-i", "sine=frequency=440:duration=6"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p"] + (["-c:a", "aac"] if audio else []) + [str(out)]
    subprocess.run(cmd, check=True, capture_output=True)
    return out

def test_sonder_refuse_vide_et_sans_audio(tmp_path):
    (tmp_path / "v.mp4").write_bytes(b"")
    with pytest.raises(FichierIllisible): sonder(tmp_path / "v.mp4")
    with pytest.raises(FichierIllisible): sonder(tmp_path / "absent.mp4")
    with pytest.raises(FichierIllisible, match="audio"): sonder(_src(tmp_path, audio=False))

def test_rendu_vertical(tmp_path):
    src = _src(tmp_path)
    srt = tmp_path / "c.srt"
    ecrire_srt([{"start": 0.5, "end": 2.5, "text": "Bonjour à tous"}], 0, 4, srt)
    out = tmp_path / "clip.mp4"
    rendre_clip(src, 0, 4, srt, out)
    i = sonder(out)
    assert (i["largeur"], i["hauteur"]) == (1080, 1920)
    assert 3.8 < i["duree"] < 4.3
