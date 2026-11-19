import hmac, hashlib, time, secrets
from . import config

DUREE = 7 * 24 * 3600
_echecs: dict[str, list[float]] = {}


def _sig(exp: str) -> str:
    return hmac.new(config.SECRET.encode(), exp.encode(), hashlib.sha256).hexdigest()


def creer_cookie() -> str:
    exp = str(int(time.time()) + DUREE)
    return f"{exp}.{_sig(exp)}"


def cookie_valide(c: str | None) -> bool:
    if not c or "." not in c or not config.SECRET:
        return False
    exp, sig = c.split(".", 1)
    return exp.isdigit() and int(exp) > time.time() and hmac.compare_digest(sig, _sig(exp))


def mot_de_passe_ok(saisi: str, ip: str) -> bool:
    """Max 5 essais ratés par 10 minutes et par adresse."""
    now = time.time()
    recents = [t for t in _echecs.get(ip, []) if now - t < 600]
    if len(recents) >= 5:
        _echecs[ip] = recents
        return False
    ok = bool(config.APP_PASSWORD) and secrets.compare_digest(saisi.encode(), config.APP_PASSWORD.encode())
    if not ok:
        _echecs[ip] = recents + [now]
    return ok
