import pytest
from app.urlcheck import extraire_id_youtube, LienInvalide

@pytest.mark.parametrize("u", [
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "https://youtu.be/dQw4w9WgXcQ?t=3",
    "https://youtube.com/shorts/dQw4w9WgXcQ", "https://m.youtube.com/watch?v=dQw4w9WgXcQ&x=1"])
def test_ok(u):
    assert extraire_id_youtube(u) == "dQw4w9WgXcQ"

@pytest.mark.parametrize("u", [
    "http://127.0.0.1/x", "https://evil.com/watch?v=dQw4w9WgXcQ",
    "https://youtube.com.evil.com/watch?v=dQw4w9WgXcQ", "file:///etc/passwd",
    "https://user:pw@www.youtube.com/watch?v=dQw4w9WgXcQ", "https://www.youtube.com/watch?v=court",
    "https://www.youtube.com:8080/watch?v=dQw4w9WgXcQ", "", "javascript:alert(1)"])
def test_refuse(u):
    with pytest.raises(LienInvalide):
        extraire_id_youtube(u)
