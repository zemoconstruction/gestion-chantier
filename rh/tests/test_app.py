import os
import re
import sys
import tempfile

os.environ["DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402
import app as A  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402


def csrf(client):
    return re.search(r'name="_csrf" value="([^"]+)"', client.get("/login").get_data(as_text=True)).group(1)


def post(client, url, data=None, **kw):
    return client.post(url, data={**(data or {}), "_csrf": csrf(client)}, **kw)


@pytest.fixture(scope="module")
def admin():
    A.seed_demo()
    import sqlite3
    db = sqlite3.connect(A.DB_PATH)
    db.execute("UPDATE users SET password=?, must_change=0 WHERE username='admin'", (generate_password_hash("adminpass1"),))
    db.commit()
    c = A.app.test_client()
    assert post(c, "/login", {"username": "admin", "password": "adminpass1"}).status_code == 302
    return c


def test_all_pages_render(admin):
    urls = ["/dashboard", "/calendrier", "/rapports", "/parametres", "/employes/1", "/candidats/1",
            "/utilisateurs", "/journal", "/paie/1/bulletin"]
    urls += [f"/m/{k}" for k in A.MODULES] + [f"/m/{k}/nouveau" for k in A.MODULES]
    for u in urls:
        assert admin.get(u).status_code == 200, u


def test_backup_download(admin):
    r = post(admin, "/sauvegarde")
    assert r.status_code == 200 and r.data.startswith(b"SQLite format 3")


def test_validation(admin):
    r = post(admin, "/m/evaluations/nouveau", {"employe_id": "1", "date": "2026-10-01", "note": "9"}, follow_redirects=True)
    assert "compris entre" in r.get_data(as_text=True)
    r = post(admin, "/m/candidats/nouveau", {"prenom": "A", "nom": "B", "poste_vise": "X", "etape": "HACK"}, follow_redirects=True)
    assert "Valeur invalide" in r.get_data(as_text=True)


def test_leave_overlap_and_holidays():
    assert A.jours_ouvres("2026-12-21", "2026-12-25") == 5
    assert A.jours_ouvres("2026-12-21", "2026-12-25", {"2026-12-25"}) == 4


def test_payroll_math():
    d = A.calcul_paie({"salaire_base": 100000, "primes": 0}, {"cot_sal": "5", "cot_pat": "16", "impot": "10"})
    assert (d["brut"], d["cot_sal"], d["impot"], d["net"], d["cot_pat"]) == (100000, 5000, 9500, 85500, 16000)


def test_csrf_required(admin):
    assert admin.post("/m/employes/1/supprimer", data={}).status_code == 400


def test_employee_isolation(admin):
    r = post(admin, "/employes/1/acces", follow_redirects=True)
    user, pwd = re.search(r"identifiant : (\S+) · mot de passe provisoire : (\S+)", r.get_data(as_text=True)).groups()
    e = A.app.test_client()
    post(e, "/login", {"username": user, "password": pwd})
    assert e.get("/portail", follow_redirects=False).status_code == 302   # changement de mot de passe imposé
    post(e, "/mot-de-passe", {"actuel": pwd, "nouveau": "nouveaupass1"})
    assert e.get("/portail").status_code == 200
    for u in ["/dashboard", "/m/employes", "/m/paies", "/rapports", "/utilisateurs", "/journal", "/m/employes/1/modifier"]:
        assert e.get(u).status_code == 403, u
    assert e.get("/paie/2/bulletin").status_code == 403
