"""
RH Pro — logiciel de gestion des ressources humaines (Flask + SQLite).

Modules : employés, performance, recrutement, congés, calendrier des absences,
paie, déclarations, formation, compétences, talents, rapports, conformité,
portail employé, feedbacks.
"""
import csv
import io
import os
import re
import secrets
import sqlite3
import sys
import uuid
from datetime import date, datetime, timedelta
from functools import wraps

from flask import (Flask, abort, flash, g, redirect, render_template, request,
                   Response, send_from_directory, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

# ------------------------------------------------------------------ chemins
if getattr(sys, "frozen", False):
    RESOURCE_DIR = sys._MEIPASS
    APP_DIR = os.path.dirname(sys.executable)
else:
    RESOURCE_DIR = APP_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(APP_DIR, "data"))
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
DB_PATH = os.path.join(DATA_DIR, "rh.db")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__, template_folder=os.path.join(RESOURCE_DIR, "templates"))
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


def _secret_key():
    if os.environ.get("SECRET_KEY"):
        return os.environ["SECRET_KEY"]
    path = os.path.join(DATA_DIR, ".secret_key")
    if not os.path.exists(path):
        with open(path, "w") as fh:
            fh.write(secrets.token_hex(32))
    with open(path) as fh:
        return fh.read().strip()


app.secret_key = _secret_key()
ALLOWED_EXT = {"pdf", "doc", "docx", "png", "jpg", "jpeg", "txt", "xlsx"}

# ------------------------------------------------------------------ schéma
# Types : text textarea email tel date datetime number select fk bool file calc
F = lambda name, label, type="text", opts=None, req=False: dict(
    name=name, label=label, type=type, opts=opts, req=req)

EMP = ("employes", "prenom || ' ' || nom")
CAND = ("candidats", "prenom || ' ' || nom")

MODULES = {
    "employes": dict(
        table="employes", title="Employés", singular="employé", icon="👥",
        fields=[
            F("matricule", "Matricule"),
            F("prenom", "Prénom", req=True), F("nom", "Nom", req=True),
            F("email", "Email", "email"), F("telephone", "Téléphone", "tel"),
            F("date_naissance", "Date de naissance", "date"),
            F("adresse", "Adresse"),
            F("poste", "Poste", req=True), F("departement", "Département"),
            F("date_embauche", "Date d'embauche", "date"),
            F("type_contrat", "Type de contrat", "select", ["CDI", "CDD", "Stage", "Intérim", "Consultant"]),
            F("salaire_base", "Salaire de base (mensuel)", "number"),
            F("statut", "Statut", "select", ["Actif", "En congé", "Parti"]),
            F("contact_urgence", "Contact d'urgence"),
            F("notes", "Notes internes", "textarea"),
        ],
        list=["matricule", "nom", "poste", "departement", "type_contrat", "statut"],
        search=["nom", "prenom", "matricule", "poste", "departement", "email"],
        filter="statut", detail=True, sort="nom"),
    "evaluations": dict(
        table="evaluations", title="Performance", singular="évaluation", icon="📈",
        fields=[
            F("employe_id", "Employé", "fk", EMP, True),
            F("date", "Date", "date", None, True),
            F("type", "Type", "select", ["Évaluation annuelle", "Évaluation semestrielle", "Entretien 1-to-1", "Feedback 360°", "Période d'essai"]),
            F("note", "Note globale (1 à 5)", "number"),
            F("objectifs", "Objectifs fixés", "textarea"),
            F("points_forts", "Points forts", "textarea"),
            F("axes", "Axes d'amélioration", "textarea"),
            F("evaluateur", "Évaluateur"),
        ],
        list=["employe_id", "date", "type", "note", "evaluateur"],
        search=["type", "evaluateur"], filter="type", sort="date DESC"),
    "candidats": dict(
        table="candidats", title="Candidatures", singular="candidature", icon="🎯",
        fields=[
            F("prenom", "Prénom", req=True), F("nom", "Nom", req=True),
            F("email", "Email", "email"), F("telephone", "Téléphone", "tel"),
            F("poste_vise", "Poste visé", req=True),
            F("source", "Source", "select", ["Site carrière", "LinkedIn", "Cooptation", "Candidature spontanée", "Annonce", "Autre"]),
            F("etape", "Étape", "select", ["Reçue", "Présélectionné", "Entretien", "Offre", "Embauché", "Refusé"]),
            F("note", "Note (1 à 5)", "number"),
            F("cv", "CV (PDF/Word)", "file"),
            F("commentaires", "Commentaires", "textarea"),
            F("date_candidature", "Date de candidature", "date"),
        ],
        list=["nom", "poste_vise", "source", "etape", "note", "date_candidature"],
        search=["nom", "prenom", "poste_vise", "email"], filter="etape",
        detail=True, sort="date_candidature DESC"),
    "entretiens": dict(
        table="entretiens", title="Entretiens", singular="entretien", icon="🗓️",
        fields=[
            F("candidat_id", "Candidat", "fk", CAND, True),
            F("date_heure", "Date et heure", "datetime", None, True),
            F("type", "Type", "select", ["Téléphonique", "RH", "Technique", "Manager", "Final"]),
            F("lieu", "Lieu / lien visio"), F("intervieweur", "Intervieweur"),
            F("statut", "Statut", "select", ["Planifié", "Réalisé", "Annulé"]),
            F("feedback", "Retour de l'entretien", "textarea"),
        ],
        list=["candidat_id", "date_heure", "type", "intervieweur", "statut"],
        search=["intervieweur", "lieu"], filter="statut", sort="date_heure DESC"),
    "conges": dict(
        table="conges", title="Congés & absences", singular="demande", icon="🌴",
        fields=[
            F("employe_id", "Employé", "fk", EMP, True),
            F("type", "Type", "select", ["Congé annuel", "Maladie", "Maternité / Paternité", "Sans solde", "Exceptionnel", "Télétravail"], True),
            F("date_debut", "Du", "date", None, True), F("date_fin", "Au", "date", None, True),
            F("jours", "Jours ouvrés", "calc"),
            F("motif", "Motif", "textarea"),
            F("statut", "Statut", "select", ["En attente", "Approuvé", "Refusé"]),
            F("commentaire_rh", "Commentaire RH", "textarea"),
        ],
        list=["employe_id", "type", "date_debut", "date_fin", "jours", "statut"],
        search=["type", "motif"], filter="statut", sort="date_debut DESC", custom_new=True),
    "paies": dict(
        table="paies", title="Paie", singular="ligne de paie", icon="💶",
        fields=[
            F("employe_id", "Employé", "fk", EMP, True),
            F("periode", "Période (AAAA-MM)", "text", None, True),
            F("salaire_base", "Salaire de base", "number"),
            F("primes", "Primes", "number"), F("heures_sup", "Heures supplémentaires (montant)", "number"),
            F("retenues", "Autres retenues / avances", "number"),
            F("brut", "Brut", "calc"), F("cot_sal", "Cotisations salariales", "calc"),
            F("impot", "Impôt sur salaire", "calc"), F("net", "Net à payer", "calc"),
            F("cot_pat", "Charges patronales", "calc"),
            F("statut", "Statut", "select", ["Brouillon", "Validée", "Payée"]),
        ],
        list=["employe_id", "periode", "brut", "net", "statut"],
        search=["periode"], filter="statut", sort="periode DESC", custom_new=True),
    "declarations": dict(
        table="declarations", title="Déclarations fiscales", singular="déclaration", icon="🏛️",
        fields=[
            F("type", "Déclaration", "select", ["Impôt sur salaires (IRPP/ITS)", "Cotisations sociales (CNSS/CNPS)", "TVA", "Taxe de formation", "Déclaration annuelle des salaires", "Autre"], True),
            F("periode", "Période", "text", None, True),
            F("echeance", "Échéance", "date"), F("montant", "Montant à déclarer", "number"),
            F("statut", "Statut", "select", ["À préparer", "Préparée", "Soumise", "Payée"]),
            F("reference", "Référence de dépôt"), F("notes", "Notes", "textarea"),
        ],
        list=["type", "periode", "echeance", "montant", "statut"],
        search=["type", "periode", "reference"], filter="statut", sort="echeance DESC"),
    "formations": dict(
        table="formations", title="Formations", singular="formation", icon="🎓",
        fields=[
            F("employe_id", "Employé", "fk", EMP, True),
            F("intitule", "Intitulé de la formation", "text", None, True),
            F("organisme", "Organisme"),
            F("statut", "Statut", "select", ["Besoin identifié", "Planifiée", "En cours", "Terminée", "Annulée"]),
            F("date_debut", "Début", "date"), F("date_fin", "Fin", "date"),
            F("cout", "Coût", "number"),
            F("objectif", "Besoin / objectif", "textarea"),
        ],
        list=["employe_id", "intitule", "organisme", "statut", "date_debut", "cout"],
        search=["intitule", "organisme"], filter="statut", sort="date_debut DESC"),
    "competences": dict(
        table="competences", title="Compétences", singular="compétence", icon="🧩",
        fields=[
            F("employe_id", "Employé", "fk", EMP, True),
            F("competence", "Compétence", "text", None, True),
            F("categorie", "Catégorie", "select", ["Technique", "Management", "Communication", "Langues", "Sécurité", "Autre"]),
            F("niveau", "Niveau actuel (1 à 5)", "number"),
            F("cible", "Niveau cible (1 à 5)", "number"),
            F("plan", "Plan de développement", "textarea"),
        ],
        list=["employe_id", "competence", "categorie", "niveau", "cible"],
        search=["competence"], filter="categorie", sort="competence"),
    "talents": dict(
        table="talents", title="Plan de succession", singular="poste clé", icon="⭐",
        fields=[
            F("poste_cle", "Poste clé", "text", None, True),
            F("titulaire_id", "Titulaire actuel", "fk", EMP),
            F("successeur_id", "Successeur identifié", "fk", EMP),
            F("preparation", "Niveau de préparation", "select", ["Prêt maintenant", "Prêt dans 1-2 ans", "Prêt dans 3 ans et +", "Aucun successeur"]),
            F("risque", "Risque de départ", "select", ["Faible", "Moyen", "Élevé"]),
            F("potentiel", "Potentiel du successeur", "select", ["Fort", "Moyen", "À développer"]),
            F("notes", "Actions de relève", "textarea"),
        ],
        list=["poste_cle", "titulaire_id", "successeur_id", "preparation", "risque"],
        search=["poste_cle"], filter="preparation", sort="poste_cle"),
    "conformite": dict(
        table="conformite", title="Conformité", singular="obligation", icon="🛡️",
        fields=[
            F("intitule", "Obligation / réglementation", "text", None, True),
            F("categorie", "Domaine", "select", ["Droit du travail", "Sécurité & santé", "Fiscal", "Protection des données", "Social"]),
            F("reference", "Référence légale"), F("responsable", "Responsable"),
            F("echeance", "Prochaine échéance", "date"),
            F("statut", "Statut", "select", ["Conforme", "À faire", "En retard"]),
            F("notes", "Actions / preuves", "textarea"),
        ],
        list=["intitule", "categorie", "responsable", "echeance", "statut"],
        search=["intitule", "reference", "responsable"], filter="statut", sort="echeance"),
    "annonces": dict(
        table="annonces", title="Portail : documents & annonces", singular="publication", icon="📢",
        fields=[
            F("titre", "Titre", "text", None, True),
            F("categorie", "Catégorie", "select", ["Annonce", "Politique interne", "Règlement", "Document RH", "Procédure"]),
            F("contenu", "Contenu", "textarea"),
            F("fichier", "Pièce jointe", "file"),
            F("date", "Date", "date"),
        ],
        list=["titre", "categorie", "date"],
        search=["titre", "contenu"], filter="categorie", sort="date DESC"),
    "feedbacks": dict(
        table="feedbacks", title="Feedbacks employés", singular="feedback", icon="💬",
        fields=[
            F("auteur", "Auteur"),
            F("categorie", "Thème", "select", ["Ambiance de travail", "Management", "Conditions de travail", "Rémunération", "Formation", "Idée d'amélioration", "Autre"]),
            F("note", "Satisfaction (1 à 5)", "number"),
            F("message", "Message", "textarea", None, True),
            F("date", "Date", "date"),
            F("traite", "Traité", "bool"),
        ],
        list=["date", "auteur", "categorie", "note", "traite"],
        search=["message", "auteur"], filter="categorie", sort="date DESC", custom_new=True),
}

SQL_TYPE = {"number": "REAL", "calc": "REAL", "fk": "INTEGER", "bool": "INTEGER"}
DEFAULT_SETTINGS = {
    "entreprise": "Mon Entreprise", "devise": "FCFA",
    "cot_sal": "5.0", "cot_pat": "16.0", "impot": "10.0", "conges_annuels": "25",
}


# ------------------------------------------------------------------ base de données
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL, nom_complet TEXT,
        role TEXT NOT NULL CHECK(role IN ('admin','employe')),
        employe_id INTEGER, actif INTEGER DEFAULT 1)""")
    conn.execute("CREATE TABLE IF NOT EXISTS settings (cle TEXT PRIMARY KEY, valeur TEXT)")
    for m in MODULES.values():
        cols = ["id INTEGER PRIMARY KEY AUTOINCREMENT"]
        for f in m["fields"]:
            cols.append(f'{f["name"]} {SQL_TYPE.get(f["type"], "TEXT")}')
        cols.append("created_at TEXT")
        conn.execute(f'CREATE TABLE IF NOT EXISTS {m["table"]} ({", ".join(cols)})')
    conn.execute("""CREATE TABLE IF NOT EXISTS messages_candidat (
        id INTEGER PRIMARY KEY AUTOINCREMENT, candidat_id INTEGER NOT NULL,
        date TEXT, sujet TEXT, corps TEXT)""")
    for k, v in DEFAULT_SETTINGS.items():
        conn.execute("INSERT OR IGNORE INTO settings VALUES (?,?)", (k, v))
    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        pwd = secrets.token_urlsafe(9)
        conn.execute("INSERT INTO users (username,password,nom_complet,role) VALUES (?,?,?,?)",
                     ("admin", generate_password_hash(pwd), "Responsable RH", "admin"))
        print("=" * 60)
        print(" Compte créé -> identifiant : admin   mot de passe :", pwd)
        print(" (changez-le dans « Mon mot de passe » après connexion)")
        print("=" * 60)
    conn.commit()
    conn.close()


def settings():
    return {r["cle"]: r["valeur"] for r in get_db().execute("SELECT * FROM settings")}


def fnum(v, default=0.0):
    try:
        return float(str(v).replace(" ", "").replace(",", "."))
    except (TypeError, ValueError):
        return default


# ------------------------------------------------------------------ métier
def jours_ouvres(d1, d2):
    d1, d2 = date.fromisoformat(d1), date.fromisoformat(d2)
    n, d = 0, d1
    while d <= d2:
        if d.weekday() < 5:
            n += 1
        d += timedelta(days=1)
    return float(n)


def pre_conges(d, db, rid=None):
    if d["date_fin"] < d["date_debut"]:
        raise ValueError("La date de fin est antérieure à la date de début.")
    d["jours"] = jours_ouvres(d["date_debut"], d["date_fin"])
    if d["jours"] == 0:
        raise ValueError("La période ne contient aucun jour ouvré.")
    d["statut"] = d.get("statut") or "En attente"
    if d["statut"] != "Refusé":
        q = ("SELECT 1 FROM conges WHERE employe_id=? AND statut!='Refusé' AND id!=? "
             "AND date_debut<=? AND date_fin>=?")
        if db.execute(q, (d["employe_id"], rid or 0, d["date_fin"], d["date_debut"])).fetchone():
            raise ValueError("Cet employé a déjà une absence qui chevauche cette période.")
    return d


def calcul_paie(d, cfg):
    base, primes, hs = fnum(d.get("salaire_base")), fnum(d.get("primes")), fnum(d.get("heures_sup"))
    brut = base + primes + hs
    cot = brut * fnum(cfg["cot_sal"]) / 100
    imposable = brut - cot
    impot = max(imposable, 0) * fnum(cfg["impot"]) / 100
    d.update(brut=round(brut, 2), cot_sal=round(cot, 2), impot=round(impot, 2),
             cot_pat=round(brut * fnum(cfg["cot_pat"]) / 100, 2),
             net=round(brut - cot - impot - fnum(d.get("retenues")), 2))
    return d


def pre_paies(d, db, rid=None):
    try:
        datetime.strptime(d["periode"], "%Y-%m")
    except ValueError:
        raise ValueError("La période doit être au format AAAA-MM (ex : 2026-10).")
    if db.execute("SELECT 1 FROM paies WHERE employe_id=? AND periode=? AND id!=?",
                  (d["employe_id"], d["periode"], rid or 0)).fetchone():
        raise ValueError("Une ligne de paie existe déjà pour cet employé et cette période.")
    return calcul_paie(d, settings())


def pre_notes(*names):
    def hook(d, db, rid=None):
        for n in names:
            if d.get(n) not in (None, "") and not 0 <= fnum(d[n]) <= 5:
                raise ValueError("Les notes et niveaux doivent être compris entre 0 et 5.")
        return d
    return hook


HOOKS = {
    "conges": pre_conges, "paies": pre_paies,
    "evaluations": pre_notes("note"), "candidats": pre_notes("note"),
    "competences": pre_notes("niveau", "cible"), "feedbacks": pre_notes("note"),
}


def solde_conges(emp_id, annee=None):
    annee = annee or date.today().year
    cfg = settings()
    pris = get_db().execute(
        "SELECT COALESCE(SUM(jours),0) FROM conges WHERE employe_id=? AND type='Congé annuel' "
        "AND statut='Approuvé' AND substr(date_debut,1,4)=?", (emp_id, str(annee))).fetchone()[0]
    droit = fnum(cfg["conges_annuels"])
    return dict(droit=droit, pris=pris, reste=droit - pris)


# ------------------------------------------------------------------ auth & sécurité
def login_required(f):
    @wraps(f)
    def deco(*a, **kw):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*a, **kw)
    return deco


def admin_required(f):
    @wraps(f)
    @login_required
    def deco(*a, **kw):
        if session.get("role") != "admin":
            abort(403)
        return f(*a, **kw)
    return deco


def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(16)
    return session["_csrf"]


@app.before_request
def check_csrf():
    if request.method == "POST" and request.endpoint != "static":
        tok = request.form.get("_csrf", "")
        if not tok or not secrets.compare_digest(tok, session.get("_csrf", "")):
            abort(400, "Jeton de sécurité invalide — rechargez la page.")


@app.after_request
def headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "same-origin"
    return resp


@app.errorhandler(403)
def e403(_):
    return render_template("message.html", titre="Accès refusé",
                           texte="Cette page est réservée à l'équipe RH."), 403


@app.errorhandler(404)
def e404(_):
    return render_template("message.html", titre="Introuvable", texte="Cette page n'existe pas."), 404


@app.errorhandler(400)
def e400(e):
    return render_template("message.html", titre="Requête invalide", texte=getattr(e, "description", "")), 400


_fails = {}


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        ip = request.remote_addr
        now = datetime.now().timestamp()
        recent = [t for t in _fails.get(ip, []) if now - t < 300]
        if len(recent) >= 8:
            flash("Trop de tentatives. Réessayez dans quelques minutes.", "danger")
            return render_template("login.html"), 429
        u = get_db().execute("SELECT * FROM users WHERE username=? AND actif=1",
                             (request.form.get("username", "").strip(),)).fetchone()
        if u and check_password_hash(u["password"], request.form.get("password", "")):
            session.clear()
            session.update(user_id=u["id"], role=u["role"], nom=u["nom_complet"] or u["username"],
                           employe_id=u["employe_id"])
            _fails.pop(ip, None)
            return redirect(url_for("dashboard" if u["role"] == "admin" else "portail"))
        _fails[ip] = recent + [now]
        flash("Identifiant ou mot de passe incorrect.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/mot-de-passe", methods=["GET", "POST"])
@login_required
def mot_de_passe():
    if request.method == "POST":
        db = get_db()
        u = db.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
        new = request.form.get("nouveau", "")
        if not check_password_hash(u["password"], request.form.get("actuel", "")):
            flash("Mot de passe actuel incorrect.", "danger")
        elif len(new) < 8:
            flash("Le nouveau mot de passe doit contenir au moins 8 caractères.", "danger")
        else:
            db.execute("UPDATE users SET password=? WHERE id=?", (generate_password_hash(new), u["id"]))
            db.commit()
            flash("Mot de passe modifié.", "success")
            return redirect(url_for("index"))
    return render_template("password.html")


@app.route("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return redirect(url_for("dashboard" if session["role"] == "admin" else "portail"))


# ------------------------------------------------------------------ filtres Jinja
MONTHS = ["", "janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
          "septembre", "octobre", "novembre", "décembre"]


@app.template_filter("dfr")
def dfr(v):
    if not v:
        return "—"
    try:
        if len(v) > 10:
            return datetime.fromisoformat(v).strftime("%d/%m/%Y %H:%M")
        return datetime.strptime(v, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return v


@app.template_filter("money")
def money(v):
    try:
        return f"{float(v or 0):,.0f}".replace(",", " ") + " " + settings()["devise"]
    except (TypeError, ValueError):
        return "—"


@app.template_filter("badge")
def badge(v):
    v = str(v or "")
    if v in ("Actif", "Approuvé", "Conforme", "Terminée", "Embauché", "Payée", "Validée", "Réalisé",
             "Prêt maintenant", "Faible", "Soumise", "Fort", "Préparée"):
        return "ok"
    if v in ("Refusé", "En retard", "Parti", "Annulé", "Annulée", "Élevé", "Aucun successeur"):
        return "bad"
    if v in ("En attente", "À faire", "Brouillon", "Planifié", "Planifiée", "Besoin identifié", "Moyen",
             "À préparer", "Reçue", "Entretien", "Offre", "Présélectionné", "En cours", "En congé",
             "Prêt dans 1-2 ans", "Prêt dans 3 ans et +", "À développer"):
        return "warn"
    return "neutral"


@app.context_processor
def inject():
    return dict(csrf_token=csrf_token, MODULES=MODULES, cfg=settings() if "user_id" in session else {},
                today=date.today().isoformat(), pending=_pending())


def _pending():
    if session.get("role") != "admin":
        return 0
    return get_db().execute("SELECT COUNT(*) FROM conges WHERE statut='En attente'").fetchone()[0]


# ------------------------------------------------------------------ tableau de bord
def count_by(db, sql):
    return [(r[0] or "Non renseigné", r[1]) for r in db.execute(sql)]


@app.route("/dashboard")
@admin_required
def dashboard():
    db, cfg = get_db(), settings()
    q = lambda sql, *a: db.execute(sql, a).fetchone()[0]
    today = date.today()
    actifs = q("SELECT COUNT(*) FROM employes WHERE statut!='Parti'")
    partis_12m = q("SELECT COUNT(*) FROM employes WHERE statut='Parti'")
    dernier = db.execute("SELECT MAX(periode) FROM paies").fetchone()[0]
    masse = q("SELECT COALESCE(SUM(brut+cot_pat),0) FROM paies WHERE periode=?", dernier) if dernier else 0
    anc = [(today - date.fromisoformat(r[0])).days / 365.25 for r in
           db.execute("SELECT date_embauche FROM employes WHERE statut!='Parti' AND date_embauche!=''")]
    ages = [(today - date.fromisoformat(r[0])).days / 365.25 for r in
            db.execute("SELECT date_naissance FROM employes WHERE statut!='Parti' AND date_naissance!=''")]
    kpi = dict(
        effectif=actifs,
        turnover=round(100 * partis_12m / (actifs + partis_12m), 1) if actifs + partis_12m else 0,
        anciennete=round(sum(anc) / len(anc), 1) if anc else 0,
        age=round(sum(ages) / len(ages), 1) if ages else 0,
        masse=masse, masse_periode=dernier,
        note=round(q("SELECT COALESCE(AVG(note),0) FROM evaluations WHERE note>0"), 2),
        conges_attente=q("SELECT COUNT(*) FROM conges WHERE statut='En attente'"),
        absents=q("SELECT COUNT(DISTINCT employe_id) FROM conges WHERE statut='Approuvé' AND date_debut<=? AND date_fin>=?",
                  today.isoformat(), today.isoformat()),
        candidats=q("SELECT COUNT(*) FROM candidats WHERE etape NOT IN ('Embauché','Refusé')"),
        budget_formation=q("SELECT COALESCE(SUM(cout),0) FROM formations WHERE statut!='Annulée' AND substr(date_debut,1,4)=?", str(today.year)),
        satisfaction=round(q("SELECT COALESCE(AVG(note),0) FROM feedbacks WHERE note>0"), 2),
    )
    charts = dict(
        dept=count_by(db, "SELECT departement, COUNT(*) FROM employes WHERE statut!='Parti' GROUP BY 1 ORDER BY 2 DESC"),
        contrat=count_by(db, "SELECT type_contrat, COUNT(*) FROM employes WHERE statut!='Parti' GROUP BY 1 ORDER BY 2 DESC"),
        pipeline=count_by(db, "SELECT etape, COUNT(*) FROM candidats GROUP BY 1 ORDER BY 2 DESC"),
        absences=count_by(db, "SELECT type, COALESCE(SUM(jours),0) FROM conges WHERE statut='Approuvé' AND substr(date_debut,1,4)='%d' GROUP BY 1 ORDER BY 2 DESC" % today.year),
        masse=[(r[0], r[1]) for r in db.execute("SELECT periode, SUM(brut) FROM paies GROUP BY 1 ORDER BY 1 DESC LIMIT 6")][::-1],
    )
    alertes = dict(
        conformite=db.execute("SELECT * FROM conformite WHERE statut!='Conforme' OR (echeance!='' AND echeance<=?) ORDER BY echeance LIMIT 5",
                              ((today + timedelta(days=30)).isoformat(),)).fetchall(),
        declarations=db.execute("SELECT * FROM declarations WHERE statut IN ('À préparer','Préparée') ORDER BY echeance LIMIT 5").fetchall(),
        entretiens=db.execute("SELECT e.*, c.prenom||' '||c.nom AS cand FROM entretiens e JOIN candidats c ON c.id=e.candidat_id "
                              "WHERE e.statut='Planifié' AND e.date_heure>=? ORDER BY e.date_heure LIMIT 5", (today.isoformat(),)).fetchall(),
        essais=db.execute("SELECT * FROM employes WHERE type_contrat='CDD' AND statut!='Parti' LIMIT 0").fetchall(),
    )
    return render_template("dashboard.html", kpi=kpi, charts=charts, alertes=alertes)


# ------------------------------------------------------------------ CRUD générique
def _module(key):
    m = MODULES.get(key)
    if not m:
        abort(404)
    return m


def _select_sql(m, where="", params=()):
    joins, extra = [], []
    for f in m["fields"]:
        if f["type"] == "fk":
            tbl, expr = f["opts"]
            alias = "j_" + f["name"]
            joins.append(f"LEFT JOIN {tbl} {alias} ON {alias}.id = t.{f['name']}")
            e = re.sub(r"\b(prenom|nom)\b", alias + r".\1", expr)
            extra.append(f"({e}) AS {f['name']}__label")
    sql = f"SELECT t.*{', ' if extra else ''}{', '.join(extra)} FROM {m['table']} t {' '.join(joins)} {where}"
    return sql, params


def fk_options(m):
    db, out = get_db(), {}
    for f in m["fields"]:
        if f["type"] == "fk":
            tbl, expr = f["opts"]
            w = "WHERE statut!='Parti'" if tbl == "employes" else ""
            out[f["name"]] = db.execute(f"SELECT id, {expr} AS l FROM {tbl} {w} ORDER BY l").fetchall()
    return out


def _can_access(key):
    """RH : tout. Employé : uniquement les annonces (lecture)."""
    return session.get("role") == "admin"


@app.route("/m/<key>")
@admin_required
def liste(key):
    m = _module(key)
    q, flt = request.args.get("q", "").strip(), request.args.get("f", "")
    where, params = [], []
    if q:
        where.append("(" + " OR ".join(f"t.{c} LIKE ?" for c in m["search"]) + ")")
        params += [f"%{q}%"] * len(m["search"])
    if flt and m.get("filter"):
        where.append(f"t.{m['filter']} = ?")
        params.append(flt)
    sql, params = _select_sql(m, ("WHERE " + " AND ".join(where)) if where else "", params)
    sort = m["sort"] if m["sort"].split()[0] in [f["name"] for f in m["fields"]] else "id"
    rows = get_db().execute(f"{sql} ORDER BY t.{sort}", params).fetchall()
    fdef = next((f for f in m["fields"] if f["name"] == m.get("filter")), None)
    cols = [f for n in m["list"] for f in m["fields"] if f["name"] == n]
    return render_template("liste.html", m=m, key=key, rows=rows, cols=cols, q=q, flt=flt, fdef=fdef)


def _collect(m, existing=None):
    d, files = {}, {}
    for f in m["fields"]:
        n, t = f["name"], f["type"]
        if t == "calc":
            continue
        if t == "file":
            up = request.files.get(n)
            if up and up.filename:
                ext = up.filename.rsplit(".", 1)[-1].lower()
                if ext not in ALLOWED_EXT:
                    raise ValueError("Type de fichier non autorisé (PDF, Word, Excel, image, texte).")
                name = f"{uuid.uuid4().hex[:12]}_{secure_filename(up.filename)}"
                files[n] = (up, name)
                d[n] = name
            else:
                d[n] = existing[n] if existing else ""
            continue
        v = request.form.get(n, "").strip()
        if t == "bool":
            d[n] = 1 if request.form.get(n) else 0
        elif t == "number":
            if v and not _isnum(v):
                raise ValueError(f"« {f['label']} » doit être un nombre.")
            d[n] = fnum(v)
        elif t == "fk":
            d[n] = int(v) if v.isdigit() else None
        else:
            if t == "select" and v and v not in f["opts"]:
                raise ValueError(f"Valeur invalide pour « {f['label']} ».")
            d[n] = v
        if f["req"] and d[n] in ("", None):
            raise ValueError(f"Le champ « {f['label']} » est obligatoire.")
    return d, files


def _isnum(v):
    try:
        float(v.replace(" ", "").replace(",", "."))
        return True
    except ValueError:
        return False


def _save(key, rid=None):
    m, db = _module(key), get_db()
    existing = db.execute(f"SELECT * FROM {m['table']} WHERE id=?", (rid,)).fetchone() if rid else None
    d, files = _collect(m, existing)
    if key in HOOKS:
        d = HOOKS[key](d, db, rid)
    if rid:
        sets = ", ".join(f"{k}=?" for k in d)
        db.execute(f"UPDATE {m['table']} SET {sets} WHERE id=?", (*d.values(), rid))
    else:
        cols = ", ".join(d) + ", created_at"
        db.execute(f"INSERT INTO {m['table']} ({cols}) VALUES ({', '.join('?' * (len(d) + 1))})",
                   (*d.values(), datetime.now().isoformat()))
        rid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    db.commit()
    for up, name in files.values():
        up.save(os.path.join(UPLOAD_DIR, name))
    return rid


@app.route("/m/<key>/nouveau", methods=["GET", "POST"])
@admin_required
def nouveau(key):
    m = _module(key)
    defaults = {k: v for k, v in request.args.items()}
    if request.method == "POST":
        try:
            _save(key)
            flash(f"{m['singular'].capitalize()} enregistré(e).", "success")
            return redirect(url_for("liste", key=key))
        except ValueError as e:
            flash(str(e), "danger")
            defaults = request.form
    return render_template("form.html", m=m, key=key, row=defaults, opts=fk_options(m), edit=False)


@app.route("/m/<key>/<int:rid>/modifier", methods=["GET", "POST"])
@admin_required
def modifier(key, rid):
    m = _module(key)
    row = get_db().execute(f"SELECT * FROM {m['table']} WHERE id=?", (rid,)).fetchone() or abort(404)
    if request.method == "POST":
        try:
            _save(key, rid)
            flash("Modifications enregistrées.", "success")
            return redirect(request.form.get("next") or url_for("liste", key=key))
        except ValueError as e:
            flash(str(e), "danger")
            row = request.form
    return render_template("form.html", m=m, key=key, row=row, opts=fk_options(m), edit=True, rid=rid)


@app.route("/m/<key>/<int:rid>/supprimer", methods=["POST"])
@admin_required
def supprimer(key, rid):
    m = _module(key)
    get_db().execute(f"DELETE FROM {m['table']} WHERE id=?", (rid,))
    get_db().commit()
    flash("Élément supprimé.", "success")
    return redirect(request.form.get("next") or url_for("liste", key=key))


@app.route("/fichiers/<name>")
@login_required
def fichier(name):
    name = secure_filename(name)
    if session["role"] != "admin":
        ok = get_db().execute("SELECT 1 FROM annonces WHERE fichier=?", (name,)).fetchone()
        if not ok:
            abort(403)
    return send_from_directory(UPLOAD_DIR, name, as_attachment=True)


# ------------------------------------------------------------------ employés
@app.route("/employes/<int:eid>")
@admin_required
def employe(eid):
    db = get_db()
    e = db.execute("SELECT * FROM employes WHERE id=?", (eid,)).fetchone() or abort(404)
    rel = lambda t, o: db.execute(f"SELECT * FROM {t} WHERE employe_id=? ORDER BY {o}", (eid,)).fetchall()
    compte = db.execute("SELECT * FROM users WHERE employe_id=?", (eid,)).fetchone()
    return render_template("employe.html", e=e, compte=compte, solde=solde_conges(eid),
                           evals=rel("evaluations", "date DESC"), conges=rel("conges", "date_debut DESC"),
                           forms=rel("formations", "date_debut DESC"), comps=rel("competences", "competence"),
                           paies=rel("paies", "periode DESC"))


@app.route("/employes/<int:eid>/acces", methods=["POST"])
@admin_required
def creer_acces(eid):
    db = get_db()
    e = db.execute("SELECT * FROM employes WHERE id=?", (eid,)).fetchone() or abort(404)
    base = (e["email"].split("@")[0] if e["email"] else f"{e['prenom']}.{e['nom']}").lower().replace(" ", "")
    username, i = base, 1
    while db.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
        i += 1
        username = f"{base}{i}"
    pwd = secrets.token_urlsafe(8)
    if db.execute("SELECT 1 FROM users WHERE employe_id=?", (eid,)).fetchone():
        flash("Cet employé a déjà un accès.", "danger")
    else:
        db.execute("INSERT INTO users (username,password,nom_complet,role,employe_id) VALUES (?,?,?,?,?)",
                   (username, generate_password_hash(pwd), f"{e['prenom']} {e['nom']}", "employe", eid))
        db.commit()
        flash(f"Accès créé — identifiant : {username} · mot de passe provisoire : {pwd} (à communiquer à l'employé).", "success")
    return redirect(url_for("employe", eid=eid))


@app.route("/employes/<int:eid>/acces/reinit", methods=["POST"])
@admin_required
def reinit_acces(eid):
    pwd = secrets.token_urlsafe(8)
    db = get_db()
    db.execute("UPDATE users SET password=? WHERE employe_id=?", (generate_password_hash(pwd), eid))
    db.commit()
    flash(f"Nouveau mot de passe provisoire : {pwd}", "success")
    return redirect(url_for("employe", eid=eid))


# ------------------------------------------------------------------ recrutement
@app.route("/candidats/<int:cid>", methods=["GET", "POST"])
@admin_required
def candidat(cid):
    db = get_db()
    c = db.execute("SELECT * FROM candidats WHERE id=?", (cid,)).fetchone() or abort(404)
    if request.method == "POST":
        act = request.form.get("action")
        if act == "etape" and request.form.get("etape") in MODULES["candidats"]["fields"][6]["opts"]:
            db.execute("UPDATE candidats SET etape=? WHERE id=?", (request.form["etape"], cid))
        elif act == "message" and request.form.get("corps", "").strip():
            db.execute("INSERT INTO messages_candidat (candidat_id,date,sujet,corps) VALUES (?,?,?,?)",
                       (cid, datetime.now().isoformat(timespec="minutes"),
                        request.form.get("sujet", "").strip(), request.form["corps"].strip()))
        elif act == "embaucher":
            db.execute("INSERT INTO employes (prenom,nom,email,telephone,poste,statut,type_contrat,date_embauche,created_at) "
                       "VALUES (?,?,?,?,?,?,?,?,?)",
                       (c["prenom"], c["nom"], c["email"], c["telephone"], c["poste_vise"], "Actif", "CDI",
                        date.today().isoformat(), datetime.now().isoformat()))
            db.execute("UPDATE candidats SET etape='Embauché' WHERE id=?", (cid,))
            flash("Candidat converti en employé : complétez sa fiche.", "success")
            db.commit()
            return redirect(url_for("employe", eid=db.execute("SELECT last_insert_rowid()").fetchone()[0]))
        db.commit()
        return redirect(url_for("candidat", cid=cid))
    entretiens = db.execute("SELECT * FROM entretiens WHERE candidat_id=? ORDER BY date_heure", (cid,)).fetchall()
    msgs = db.execute("SELECT * FROM messages_candidat WHERE candidat_id=? ORDER BY date DESC", (cid,)).fetchall()
    return render_template("candidat.html", c=c, entretiens=entretiens, msgs=msgs,
                           etapes=MODULES["candidats"]["fields"][6]["opts"])


# ------------------------------------------------------------------ congés
@app.route("/conges/<int:cid>/decision", methods=["POST"])
@admin_required
def decision_conge(cid):
    statut = request.form.get("statut")
    if statut not in ("Approuvé", "Refusé"):
        abort(400)
    db = get_db()
    db.execute("UPDATE conges SET statut=?, commentaire_rh=? WHERE id=?",
               (statut, request.form.get("commentaire", "").strip(), cid))
    db.commit()
    flash(f"Demande {statut.lower()}e.".replace("Approuvée", "approuvée"), "success")
    return redirect(request.form.get("next") or url_for("liste", key="conges"))


@app.route("/calendrier")
@login_required
def calendrier():
    mois = request.args.get("mois") or date.today().strftime("%Y-%m")
    try:
        y, mth = map(int, mois.split("-"))
        first = date(y, mth, 1)
    except ValueError:
        abort(400)
    nxt = date(y + (mth == 12), mth % 12 + 1, 1)
    days = [first + timedelta(days=i) for i in range((nxt - first).days)]
    db, dept = get_db(), request.args.get("dept", "")
    emps = db.execute("SELECT * FROM employes WHERE statut!='Parti'" + (" AND departement=?" if dept else "") + " ORDER BY nom",
                      (dept,) if dept else ()).fetchall()
    abs_ = db.execute("SELECT * FROM conges WHERE statut!='Refusé' AND date_debut<=? AND date_fin>=?",
                      (days[-1].isoformat(), days[0].isoformat())).fetchall()
    grid = {}
    for a in abs_:
        for d in days:
            if a["date_debut"] <= d.isoformat() <= a["date_fin"]:
                grid[(a["employe_id"], d.isoformat())] = a
    depts = [r[0] for r in db.execute("SELECT DISTINCT departement FROM employes WHERE departement!='' ORDER BY 1")]
    prev = (first - timedelta(days=1)).strftime("%Y-%m")
    return render_template("calendrier.html", days=days, emps=emps, grid=grid, depts=depts, dept=dept,
                           titre=f"{MONTHS[mth].capitalize()} {y}", prev=prev, nxt=nxt.strftime("%Y-%m"))


# ------------------------------------------------------------------ paie & déclarations
@app.route("/paie/generer", methods=["POST"])
@admin_required
def generer_paie():
    periode = request.form.get("periode", "")
    try:
        datetime.strptime(periode, "%Y-%m")
    except ValueError:
        flash("Période invalide (AAAA-MM).", "danger")
        return redirect(url_for("liste", key="paies"))
    db, cfg, n = get_db(), settings(), 0
    for e in db.execute("SELECT * FROM employes WHERE statut!='Parti'").fetchall():
        if db.execute("SELECT 1 FROM paies WHERE employe_id=? AND periode=?", (e["id"], periode)).fetchone():
            continue
        d = calcul_paie(dict(salaire_base=e["salaire_base"], primes=0, heures_sup=0, retenues=0), cfg)
        db.execute("INSERT INTO paies (employe_id,periode,salaire_base,primes,heures_sup,retenues,brut,cot_sal,impot,net,cot_pat,statut,created_at) "
                   "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (e["id"], periode, d["salaire_base"], 0, 0, 0, d["brut"], d["cot_sal"], d["impot"], d["net"],
                    d["cot_pat"], "Brouillon", datetime.now().isoformat()))
        n += 1
    db.commit()
    flash(f"{n} ligne(s) de paie générée(s) pour {periode}. Ajoutez les primes puis validez.", "success")
    return redirect(url_for("liste", key="paies", q=periode))


@app.route("/paie/valider", methods=["POST"])
@admin_required
def valider_paie():
    p, st = request.form.get("periode", ""), request.form.get("statut")
    if st not in ("Validée", "Payée"):
        abort(400)
    db = get_db()
    db.execute("UPDATE paies SET statut=? WHERE periode=? AND statut!='Payée'", (st, p))
    db.commit()
    flash(f"Paie {p} : {st.lower()}.", "success")
    return redirect(url_for("liste", key="paies", q=p))


@app.route("/paie/<int:pid>/bulletin")
@login_required
def bulletin(pid):
    db = get_db()
    p = db.execute("SELECT * FROM paies WHERE id=?", (pid,)).fetchone() or abort(404)
    if session["role"] != "admin" and (p["employe_id"] != session.get("employe_id") or p["statut"] == "Brouillon"):
        abort(403)
    e = db.execute("SELECT * FROM employes WHERE id=?", (p["employe_id"],)).fetchone()
    return render_template("bulletin.html", p=p, e=e)


@app.route("/declarations/generer", methods=["POST"])
@admin_required
def generer_declarations():
    periode = request.form.get("periode", "")
    db = get_db()
    r = db.execute("SELECT COALESCE(SUM(impot),0), COALESCE(SUM(cot_sal+cot_pat),0), COUNT(*) FROM paies WHERE periode=? AND statut!='Brouillon'",
                   (periode,)).fetchone()
    if not r[2]:
        flash("Aucune paie validée pour cette période.", "danger")
        return redirect(url_for("liste", key="declarations"))
    try:
        y, m = map(int, periode.split("-"))
        ech = date(y + (m == 12), m % 12 + 1, 15).isoformat()
    except ValueError:
        abort(400)
    for typ, mt in (("Impôt sur salaires (IRPP/ITS)", r[0]), ("Cotisations sociales (CNSS/CNPS)", r[1])):
        if not db.execute("SELECT 1 FROM declarations WHERE type=? AND periode=?", (typ, periode)).fetchone():
            db.execute("INSERT INTO declarations (type,periode,echeance,montant,statut,created_at) VALUES (?,?,?,?,?,?)",
                       (typ, periode, ech, mt, "À préparer", datetime.now().isoformat()))
    db.commit()
    flash("Déclarations préparées à partir de la paie validée.", "success")
    return redirect(url_for("liste", key="declarations"))


@app.route("/parametres", methods=["GET", "POST"])
@admin_required
def parametres():
    if request.method == "POST":
        db = get_db()
        for k in DEFAULT_SETTINGS:
            v = request.form.get(k, "").strip()
            if k not in ("entreprise", "devise") and not _isnum(v):
                flash(f"Valeur numérique attendue pour {k}.", "danger")
                return redirect(url_for("parametres"))
            db.execute("UPDATE settings SET valeur=? WHERE cle=?", (v, k))
        db.commit()
        flash("Paramètres enregistrés (appliqués aux prochains calculs de paie).", "success")
        return redirect(url_for("parametres"))
    return render_template("parametres.html")


# ------------------------------------------------------------------ rapports
@app.route("/rapports")
@admin_required
def rapports():
    key = request.args.get("module", "employes")
    m = _module(key)
    fields = [f for f in m["fields"] if f["type"] != "file"]
    chosen = request.args.getlist("col") or m["list"]
    cols = [f for f in fields if f["name"] in chosen]
    q = request.args.get("q", "").strip()
    sql, params = _select_sql(m, ("WHERE " + " OR ".join(f"t.{c} LIKE ?" for c in m["search"])) if q else "",
                              [f"%{q}%"] * len(m["search"]) if q else [])
    rows = get_db().execute(sql, params).fetchall()
    if request.args.get("csv"):
        out = io.StringIO()
        w = csv.writer(out, delimiter=";")
        w.writerow([f["label"] for f in cols])
        for r in rows:
            w.writerow([r[f["name"] + "__label"] if f["type"] == "fk" else r[f["name"]] for f in cols])
        return Response("﻿" + out.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": f"attachment; filename=rapport_{key}.csv"})
    return render_template("rapports.html", key=key, m=m, fields=fields, cols=cols, rows=rows, q=q,
                           chosen=[c["name"] for c in cols])


# ------------------------------------------------------------------ portail employé
@app.route("/portail")
@login_required
def portail():
    db, eid = get_db(), session.get("employe_id")
    e = db.execute("SELECT * FROM employes WHERE id=?", (eid,)).fetchone() if eid else None
    rel = lambda t, o, extra="": db.execute(f"SELECT * FROM {t} WHERE employe_id=? {extra} ORDER BY {o}", (eid,)).fetchall() if eid else []
    return render_template("portail.html", e=e, solde=solde_conges(eid) if eid else None,
                           conges=rel("conges", "date_debut DESC"),
                           paies=rel("paies", "periode DESC", "AND statut!='Brouillon'"),
                           evals=rel("evaluations", "date DESC"), forms=rel("formations", "date_debut DESC"),
                           comps=rel("competences", "competence"),
                           annonces=db.execute("SELECT * FROM annonces ORDER BY date DESC").fetchall(),
                           types=MODULES["conges"]["fields"][1]["opts"],
                           themes=MODULES["feedbacks"]["fields"][1]["opts"])


@app.route("/portail/conge", methods=["POST"])
@login_required
def portail_conge():
    eid = session.get("employe_id") or abort(403)
    try:
        d = dict(employe_id=eid, type=request.form.get("type"), date_debut=request.form.get("date_debut", ""),
                 date_fin=request.form.get("date_fin", ""), motif=request.form.get("motif", "").strip(),
                 statut="En attente", commentaire_rh="")
        if d["type"] not in MODULES["conges"]["fields"][1]["opts"]:
            raise ValueError("Type de congé invalide.")
        date.fromisoformat(d["date_debut"]), date.fromisoformat(d["date_fin"])
        d = pre_conges(d, get_db())
        db = get_db()
        db.execute("INSERT INTO conges (employe_id,type,date_debut,date_fin,jours,motif,statut,commentaire_rh,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                   (eid, d["type"], d["date_debut"], d["date_fin"], d["jours"], d["motif"], "En attente", "",
                    datetime.now().isoformat()))
        db.commit()
        flash("Demande envoyée : elle sera examinée par les RH.", "success")
    except ValueError as e:
        flash(str(e) if "isoformat" not in str(e) else "Dates invalides.", "danger")
    return redirect(url_for("portail") + "#conges")


@app.route("/portail/conge/<int:cid>/annuler", methods=["POST"])
@login_required
def portail_annuler(cid):
    db = get_db()
    db.execute("DELETE FROM conges WHERE id=? AND employe_id=? AND statut='En attente'", (cid, session.get("employe_id")))
    db.commit()
    flash("Demande annulée.", "success")
    return redirect(url_for("portail") + "#conges")


@app.route("/portail/profil", methods=["POST"])
@login_required
def portail_profil():
    eid = session.get("employe_id") or abort(403)
    db = get_db()
    db.execute("UPDATE employes SET telephone=?, adresse=?, contact_urgence=? WHERE id=?",
               tuple(request.form.get(k, "").strip() for k in ("telephone", "adresse", "contact_urgence")) + (eid,))
    db.commit()
    flash("Vos informations ont été mises à jour.", "success")
    return redirect(url_for("portail"))


@app.route("/portail/feedback", methods=["POST"])
@login_required
def portail_feedback():
    msg = request.form.get("message", "").strip()
    note = fnum(request.form.get("note"))
    if not msg or not 0 <= note <= 5 or request.form.get("categorie") not in MODULES["feedbacks"]["fields"][1]["opts"]:
        flash("Message ou thème invalide.", "danger")
    else:
        auteur = "Anonyme" if request.form.get("anonyme") else session["nom"]
        db = get_db()
        db.execute("INSERT INTO feedbacks (auteur,categorie,note,message,date,traite,created_at) VALUES (?,?,?,?,?,0,?)",
                   (auteur, request.form["categorie"], note, msg, date.today().isoformat(), datetime.now().isoformat()))
        db.commit()
        flash("Merci, votre retour a bien été transmis.", "success")
    return redirect(url_for("portail") + "#feedback")


# ------------------------------------------------------------------ données de démonstration
def seed_demo():
    import random
    random.seed(4)
    db = sqlite3.connect(DB_PATH)
    if db.execute("SELECT COUNT(*) FROM employes").fetchone()[0]:
        print("Des données existent déjà : démo ignorée.")
        return
    now, today = datetime.now().isoformat(), date.today()
    people = [("Awa", "Diallo", "Direction", "Directrice générale", 1800000), ("Moussa", "Traoré", "Finance", "Comptable", 650000),
              ("Fatou", "Sow", "RH", "Chargée RH", 600000), ("Ibrahim", "Koné", "Technique", "Chef de chantier", 800000),
              ("Aïcha", "Bah", "Technique", "Ingénieure travaux", 900000), ("Paul", "Mbarga", "Commercial", "Commercial", 550000),
              ("Léa", "Ndiaye", "Finance", "Assistante comptable", 400000), ("Samuel", "Okoro", "Technique", "Conducteur de travaux", 750000)]
    for i, (p, n, d, poste, sal) in enumerate(people, 1):
        db.execute("INSERT INTO employes (matricule,prenom,nom,email,telephone,date_naissance,poste,departement,date_embauche,type_contrat,salaire_base,statut,created_at) "
                   "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (f"E{i:03d}", p, n, f"{p.lower()}.{n.lower()}@exemple.com", "+221 77 000 00 0%d" % i,
                    (today - timedelta(days=random.randint(9000, 16000))).isoformat(), poste, d,
                    (today - timedelta(days=random.randint(200, 3000))).isoformat(), random.choice(["CDI", "CDI", "CDD"]),
                    sal, "Actif", now))
    db.execute("INSERT INTO employes (matricule,prenom,nom,poste,departement,type_contrat,salaire_base,statut,date_embauche,created_at) VALUES ('E009','Jean','Mballa','Maçon','Technique','CDD',300000,'Parti','2022-01-10',?)", (now,))
    for i in range(1, 9):
        db.execute("INSERT INTO evaluations (employe_id,date,type,note,objectifs,points_forts,axes,evaluateur,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                   (i, (today - timedelta(days=random.randint(10, 300))).isoformat(), "Évaluation annuelle", random.choice([3, 3.5, 4, 4.5, 5]),
                    "Atteindre les objectifs annuels", "Fiable, autonome", "Délégation", "Awa Diallo", now))
        db.execute("INSERT INTO competences (employe_id,competence,categorie,niveau,cible,plan,created_at) VALUES (?,?,?,?,?,?,?)",
                   (i, random.choice(["Lecture de plans", "Excel avancé", "Management d'équipe", "Sécurité chantier"]),
                    random.choice(["Technique", "Management", "Sécurité"]), random.randint(2, 4), 5, "Formation interne", now))
    for e, typ, d1, d2, st in [(4, "Congé annuel", 3, 9, "Approuvé"), (5, "Maladie", -2, 1, "Approuvé"),
                               (6, "Congé annuel", 14, 25, "En attente"), (2, "Congé annuel", 6, 8, "En attente")]:
        a, b = (today + timedelta(days=d1)).isoformat(), (today + timedelta(days=d2)).isoformat()
        db.execute("INSERT INTO conges (employe_id,type,date_debut,date_fin,jours,statut,created_at) VALUES (?,?,?,?,?,?,?)",
                   (e, typ, a, b, jours_ouvres(a, b), st, now))
    for nom, pre, poste, et in [("Camara", "Ousmane", "Électricien", "Entretien"), ("Faye", "Mariam", "Architecte", "Présélectionné"),
                                ("Gomis", "Daniel", "Chef de chantier", "Reçue"), ("Ba", "Salif", "Comptable", "Offre")]:
        db.execute("INSERT INTO candidats (prenom,nom,email,poste_vise,source,etape,note,date_candidature,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                   (pre, nom, f"{pre.lower()}@mail.com", poste, "LinkedIn", et, 4, today.isoformat(), now))
    db.execute("INSERT INTO entretiens (candidat_id,date_heure,type,lieu,intervieweur,statut,created_at) VALUES (1,?,?,?,?,?,?)",
               ((datetime.now() + timedelta(days=2)).replace(hour=10, minute=0, second=0, microsecond=0).isoformat(timespec="minutes"), "Technique", "Siège", "Ibrahim Koné", "Planifié", now))
    for e, t, org, st, c in [(4, "Habilitation électrique", "AFPA", "Planifiée", 250000), (5, "Management de projet", "CESAG", "Terminée", 400000),
                             (7, "Excel avancé", "Interne", "Besoin identifié", 0)]:
        db.execute("INSERT INTO formations (employe_id,intitule,organisme,statut,date_debut,cout,created_at) VALUES (?,?,?,?,?,?,?)",
                   (e, t, org, st, today.isoformat(), c, now))
    db.execute("INSERT INTO talents (poste_cle,titulaire_id,successeur_id,preparation,risque,potentiel,created_at) VALUES ('Directeur technique',4,5,'Prêt dans 1-2 ans','Moyen','Fort',?)", (now,))
    db.execute("INSERT INTO talents (poste_cle,titulaire_id,preparation,risque,created_at) VALUES ('Directrice générale',1,'Aucun successeur','Faible',?)", (now,))
    for t, c, st, ech in [("Registre unique du personnel à jour", "Droit du travail", "À faire", 20), ("Visites médicales annuelles", "Sécurité & santé", "En retard", -10),
                          ("Affichage du règlement intérieur", "Droit du travail", "Conforme", 200), ("Formation sécurité sur chantier", "Sécurité & santé", "À faire", 45)]:
        db.execute("INSERT INTO conformite (intitule,categorie,responsable,echeance,statut,created_at) VALUES (?,?,?,?,?,?)",
                   (t, c, "Fatou Sow", (today + timedelta(days=ech)).isoformat(), st, now))
    db.execute("INSERT INTO annonces (titre,categorie,contenu,date,created_at) VALUES ('Règlement intérieur','Règlement','Horaires : 8h-17h du lundi au vendredi. Port des EPI obligatoire sur chantier.',?,?)", (today.isoformat(), now))
    db.execute("INSERT INTO annonces (titre,categorie,contenu,date,created_at) VALUES ('Fermeture de fin d''année','Annonce','Les bureaux seront fermés du 24 au 31 décembre.',?,?)", (today.isoformat(), now))
    db.execute("INSERT INTO feedbacks (auteur,categorie,note,message,date,traite,created_at) VALUES ('Anonyme','Conditions de travail',3,'Prévoir des casques en plus grand nombre.',?,0,?)", (today.isoformat(), now))
    db.commit()
    db.close()
    # paie des 3 derniers mois via l'application
    with app.test_request_context():
        cfg_db = get_db()
        cfg = settings()
        for k in range(3, 0, -1):
            dd = today.replace(day=1) - timedelta(days=30 * (k - 1))
            per = dd.strftime("%Y-%m")
            for e in cfg_db.execute("SELECT * FROM employes WHERE statut!='Parti'").fetchall():
                x = calcul_paie(dict(salaire_base=e["salaire_base"], primes=random.choice([0, 0, 25000]), heures_sup=0, retenues=0), cfg)
                cfg_db.execute("INSERT INTO paies (employe_id,periode,salaire_base,primes,heures_sup,retenues,brut,cot_sal,impot,net,cot_pat,statut,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                               (e["id"], per, x["salaire_base"], x["primes"], 0, 0, x["brut"], x["cot_sal"], x["impot"], x["net"], x["cot_pat"], "Payée" if k > 1 else "Validée", now))
        cfg_db.commit()
    print("Données de démonstration créées.")


if __name__ == "__main__":
    init_db()
    if "--demo" in sys.argv:
        seed_demo()
    port = int(os.environ.get("PORT", 5001))
    try:
        from waitress import serve
        print(f"RH Pro disponible sur http://localhost:{port}")
        serve(app, host="0.0.0.0", port=port)
    except ImportError:
        app.run(host="0.0.0.0", port=port, debug=False)
else:
    init_db()
