import time
from app import jobs, auth

def test_double_clic_ne_relance_pas(data):
    appels = []
    def travail(vid):
        appels.append(vid); time.sleep(0.3); jobs.ecrire(vid, etat="termine")
    j1, n1 = jobs.demarrer("abcdefghijk", travail)
    j2, n2 = jobs.demarrer("abcdefghijk", travail)
    assert n1 and not n2
    time.sleep(0.6)
    j3, n3 = jobs.demarrer("abcdefghijk", travail)  # déjà terminé : réutilisé
    assert not n3 and appels == ["abcdefghijk"]

def test_redemarrage_marque_les_taches_interrompues(data):
    jobs.ecrire("abcdefghijk", etat="en_cours")
    jobs.reprise_apres_redemarrage()
    j = jobs.lire("abcdefghijk")
    assert j["etat"] == "echec" and "redémarrage" in j["erreur"]

def test_cookie_et_limite_essais(data):
    assert auth.cookie_valide(auth.creer_cookie())
    assert not auth.cookie_valide("123.abc") and not auth.cookie_valide(None)
    assert auth.mot_de_passe_ok("secret-test", "1.1.1.1")
    for _ in range(5): assert not auth.mot_de_passe_ok("faux", "2.2.2.2")
    assert not auth.mot_de_passe_ok("secret-test", "2.2.2.2")  # bloqué après 5 échecs
