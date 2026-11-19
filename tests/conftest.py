import subprocess, pytest
from app import config

@pytest.fixture
def data(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(config, "SECRET", "x" * 32)
    monkeypatch.setattr(config, "APP_PASSWORD", "secret-test")
    return tmp_path

@pytest.fixture
def mp4(tmp_path):
    out = tmp_path / "ref.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=25:duration=5",
                    "-f", "lavfi", "-i", "sine=frequency=300:duration=5", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", str(out)], check=True, capture_output=True)
    return out
