import re, shutil, subprocess, pytest
from pathlib import Path

HTML = Path(__file__).parent.parent / "app" / "static" / "index.html"

@pytest.mark.skipif(not shutil.which("node"), reason="node absent")
def test_le_javascript_de_la_page_est_valide(tmp_path):
    js = re.search(r"<script>(.*)</script>", HTML.read_text(encoding="utf-8"), re.S).group(1)
    f = tmp_path / "page.js"; f.write_text(js, encoding="utf-8")
    r = subprocess.run(["node", "--check", str(f)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr

def test_les_deux_boutons_et_leurs_actions_existent():
    h = HTML.read_text(encoding="utf-8")
    for x in ["id=bf", "id=bu", "$('bf').onclick", "$('bu').onclick", "/api/upload", "/api/import"]:
        assert x in h
