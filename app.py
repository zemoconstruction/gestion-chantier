"""
GESTION CHANTIERS - Logiciel de gestion des prestataires, avances et achats
Auteur: généré pour PROJET PRIVE PCA
"""
import os
import sys
import sqlite3
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
import csv
import io

# ---- Chemins compatibles "exécutable .exe" (PyInstaller) et exécution normale ----
if getattr(sys, "frozen", False):
    RESOURCE_DIR = sys._MEIPASS           # dossier temporaire contenant templates/static dans l'exe
    APP_DIR = os.path.dirname(sys.executable)  # dossier où se trouve le .exe (pour stocker les données)
else:
    RESOURCE_DIR = os.path.dirname(os.path.abspath(__file__))
    APP_DIR = RESOURCE_DIR

BASE_DIR = APP_DIR
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(APP_DIR, "data"))
DB_PATH = os.path.join(DATA_DIR, "gestion_chantiers.db")
os.makedirs(DATA_DIR, exist_ok=True)

app = Flask(__name__,
            template_folder=os.path.join(RESOURCE_DIR, "templates"),
            static_folder=os.path.join(RESOURCE_DIR, "static"))
app.secret_key = os.environ.get("SECRET_KEY", "changez-cette-cle-secrete-en-production-2026")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            nom_complet TEXT,
            role TEXT NOT NULL CHECK(role IN ('admin','saisie')),
            actif INTEGER DEFAULT 1
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS chantiers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            description TEXT,
            date_creation TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS prestataires (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chantier_id INTEGER,
            nom TEXT NOT NULL,
            telephone TEXT,
            specialite TEXT,
            travaux TEXT,
            montant_contrat REAL DEFAULT 0,
            date_debut TEXT,
            date_fin_prevue TEXT,
            date_fin_reelle TEXT,
            statut TEXT DEFAULT 'En cours',
            notes TEXT,
            date_creation TEXT,
            FOREIGN KEY (chantier_id) REFERENCES chantiers(id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS avances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prestataire_id INTEGER NOT NULL,
            date TEXT,
            montant REAL DEFAULT 0,
            libelle TEXT,
            mode_paiement TEXT,
            saisi_par TEXT,
            date_saisie TEXT,
            FOREIGN KEY (prestataire_id) REFERENCES prestataires(id) ON DELETE CASCADE
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS achats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chantier_id INTEGER,
            date TEXT,
            fournisseur TEXT,
            objet TEXT,
            categorie TEXT,
            montant REAL DEFAULT 0,
            tableau_ref TEXT,
            mode_paiement TEXT,
            saisi_par TEXT,
            date_saisie TEXT,
            FOREIGN KEY (chantier_id) REFERENCES chantiers(id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS categories_achat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT UNIQUE NOT NULL
        )
    """)
    conn.commit()

    # ---- Migrations légères (ajout de colonnes sur bases existantes) ----
    def _col_exists(table, col):
        return col in [r[1] for r in c.execute(f"PRAGMA table_info({table})").fetchall()]

    if not _col_exists("achats", "pu"):
        c.execute("ALTER TABLE achats ADD COLUMN pu REAL DEFAULT 0")
    if not _col_exists("achats", "quantite"):
        c.execute("ALTER TABLE achats ADD COLUMN quantite REAL DEFAULT 0")
    conn.commit()

    # Catégories par défaut
    for cat in ["Ciment", "Fer / Barres", "Briques", "Sable / Gravier", "Bois / Planches",
                "Plomberie", "Électricité", "Quincaillerie", "Transport"]:
        c.execute("INSERT OR IGNORE INTO categories_achat (nom) VALUES (?)", (cat,))
    conn.commit()

    # Comptes par défaut si aucun utilisateur
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        from werkzeug.security import generate_password_hash
        c.execute("INSERT INTO users (username, password, nom_complet, role) VALUES (?,?,?,?)",
                  ("admin", generate_password_hash("admin123"), "Administrateur", "admin"))
        c.execute("INSERT INTO users (username, password, nom_complet, role) VALUES (?,?,?,?)",
                  ("saisie", generate_password_hash("saisie123"), "Agent de saisie", "saisie"))
        conn.commit()

    # Chantier par défaut
    c.execute("SELECT COUNT(*) FROM chantiers")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO chantiers (nom, description, date_creation) VALUES (?,?,?)",
                  ("Chantier principal", "Chantier importé / par défaut", datetime.now().isoformat()))
        conn.commit()
    conn.close()


# ---------- AUTH ----------
def login_required(f):
    @wraps(f)
    def deco(*a, **kw):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*a, **kw)
    return deco


def admin_required(f):
    @wraps(f)
    def deco(*a, **kw):
        if "user_id" not in session:
            return redirect(url_for("login"))
        if session.get("role") != "admin":
            flash("Accès refusé : cette action est réservée à l'administrateur.", "danger")
            return redirect(url_for("dashboard"))
        return f(*a, **kw)
    return deco


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        from werkzeug.security import check_password_hash
        username = request.form["username"].strip()
        password = request.form["password"]
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username=? AND actif=1", (username,)).fetchone()
        conn.close()
        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            session["nom_complet"] = user["nom_complet"]
            return redirect(url_for("dashboard"))
        flash("Identifiant ou mot de passe incorrect.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------- DASHBOARD ----------
@app.route("/")
@login_required
def dashboard():
    conn = get_db()
    total_achats = conn.execute("SELECT COALESCE(SUM(montant),0) s FROM achats").fetchone()["s"]
    total_avances = conn.execute("SELECT COALESCE(SUM(montant),0) s FROM avances").fetchone()["s"]
    total_contrats = conn.execute("SELECT COALESCE(SUM(montant_contrat),0) s FROM prestataires").fetchone()["s"]
    nb_prestataires = conn.execute("SELECT COUNT(*) c FROM prestataires").fetchone()["c"]
    nb_en_cours = conn.execute("SELECT COUNT(*) c FROM prestataires WHERE statut='En cours'").fetchone()["c"]
    nb_termines = conn.execute("SELECT COUNT(*) c FROM prestataires WHERE statut='Terminé'").fetchone()["c"]
    solde_global = total_contrats - total_avances

    derniers_achats = conn.execute("SELECT * FROM achats ORDER BY date_saisie DESC LIMIT 6").fetchall()
    dernieres_avances = conn.execute("""
        SELECT a.*, p.nom as prestataire_nom FROM avances a
        JOIN prestataires p ON p.id = a.prestataire_id
        ORDER BY a.date_saisie DESC LIMIT 6
    """).fetchall()

    top_prestataires = conn.execute("""
        SELECT p.*, COALESCE(SUM(av.montant),0) as total_avance
        FROM prestataires p LEFT JOIN avances av ON av.prestataire_id = p.id
        GROUP BY p.id
        ORDER BY (p.montant_contrat - COALESCE(SUM(av.montant),0)) DESC
        LIMIT 5
    """).fetchall()

    par_categorie = conn.execute("""
        SELECT COALESCE(categorie,'Non classé') cat, COALESCE(SUM(montant),0) total
        FROM achats GROUP BY cat ORDER BY total DESC LIMIT 8
    """).fetchall()

    conn.close()
    return render_template("dashboard.html",
                           total_achats=total_achats, total_avances=total_avances,
                           total_contrats=total_contrats, solde_global=solde_global,
                           nb_prestataires=nb_prestataires, nb_en_cours=nb_en_cours,
                           nb_termines=nb_termines, derniers_achats=derniers_achats,
                           dernieres_avances=dernieres_avances, top_prestataires=top_prestataires,
                           par_categorie=par_categorie)


# ---------- PRESTATAIRES ----------
def _prestataires_query(args, conn):
    q = args.get("q", "").strip()
    statut = args.get("statut", "")
    chantier_id = args.get("chantier_id", "")
    date_min = args.get("date_min", "")
    date_max = args.get("date_max", "")
    montant_min = args.get("montant_min", "")
    montant_max = args.get("montant_max", "")

    sql = """
        SELECT p.*, c.nom as chantier_nom, COALESCE(SUM(av.montant),0) as total_avance,
               (p.montant_contrat - COALESCE(SUM(av.montant),0)) as solde
        FROM prestataires p
        LEFT JOIN avances av ON av.prestataire_id = p.id
        LEFT JOIN chantiers c ON c.id = p.chantier_id
        WHERE 1=1
    """
    params = []
    if q:
        sql += " AND (p.nom LIKE ? OR p.telephone LIKE ? OR p.travaux LIKE ? OR p.specialite LIKE ?)"
        params += [f"%{q}%"] * 4
    if chantier_id:
        sql += " AND p.chantier_id = ?"
        params.append(chantier_id)
    if statut:
        sql += " AND p.statut = ?"
        params.append(statut)
    if date_min:
        sql += " AND p.date_debut >= ?"
        params.append(date_min)
    if date_max:
        sql += " AND p.date_debut <= ?"
        params.append(date_max)
    sql += " GROUP BY p.id"
    if montant_min:
        sql += " HAVING p.montant_contrat >= ?"
        params.append(float(montant_min))
    if montant_max:
        sql += (" AND" if montant_min else " HAVING") + " p.montant_contrat <= ?"
        params.append(float(montant_max))
    # Filtre/tri par chantier en 1er
    sql += " ORDER BY c.nom IS NULL, c.nom, p.id DESC"

    rows = conn.execute(sql, params).fetchall()
    filtres = dict(q=q, statut=statut, chantier_id=chantier_id, date_min=date_min,
                    date_max=date_max, montant_min=montant_min, montant_max=montant_max)
    return rows, filtres


@app.route("/prestataires")
@login_required
def prestataires_list():
    conn = get_db()
    rows, filtres = _prestataires_query(request.args, conn)
    chantiers = conn.execute("SELECT * FROM chantiers ORDER BY nom").fetchall()
    conn.close()
    return render_template("prestataires_list.html", rows=rows, chantiers=chantiers, **filtres)


@app.route("/prestataires/imprimer")
@login_required
def prestataires_imprimer():
    conn = get_db()
    rows, filtres = _prestataires_query(request.args, conn)
    chantier_nom = None
    if filtres.get("chantier_id"):
        ch = conn.execute("SELECT nom FROM chantiers WHERE id=?", (filtres["chantier_id"],)).fetchone()
        chantier_nom = ch["nom"] if ch else None
    conn.close()
    total_contrat = sum(r["montant_contrat"] for r in rows)
    total_avance = sum(r["total_avance"] for r in rows)
    total_solde = sum(r["solde"] for r in rows)
    return render_template("prestataires_print.html", rows=rows, chantier_nom=chantier_nom,
                            filtres=filtres, total_contrat=total_contrat, total_avance=total_avance,
                            total_solde=total_solde, date_impression=datetime.now().strftime("%d/%m/%Y %H:%M"))


@app.route("/prestataires/nouveau", methods=["GET", "POST"])
@login_required
def prestataire_nouveau():
    conn = get_db()
    if request.method == "POST":
        f = request.form
        conn.execute("""
            INSERT INTO prestataires (chantier_id, nom, telephone, specialite, travaux,
                montant_contrat, date_debut, date_fin_prevue, statut, notes, date_creation)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (f.get("chantier_id") or None, f["nom"], f.get("telephone"), f.get("specialite"),
              f.get("travaux"), float(f.get("montant_contrat") or 0), f.get("date_debut"),
              f.get("date_fin_prevue"), f.get("statut", "En cours"), f.get("notes"),
              datetime.now().isoformat()))
        conn.commit()
        conn.close()
        flash("Prestataire ajouté avec succès.", "success")
        return redirect(url_for("prestataires_list"))
    chantiers = conn.execute("SELECT * FROM chantiers").fetchall()
    conn.close()
    return render_template("prestataire_form.html", p=None, chantiers=chantiers)


@app.route("/prestataires/<int:pid>")
@login_required
def prestataire_detail(pid):
    conn = get_db()
    p = conn.execute("SELECT * FROM prestataires WHERE id=?", (pid,)).fetchone()
    if not p:
        flash("Prestataire introuvable.", "danger")
        return redirect(url_for("prestataires_list"))
    avances = conn.execute("SELECT * FROM avances WHERE prestataire_id=? ORDER BY date DESC", (pid,)).fetchall()
    total_avance = sum(a["montant"] for a in avances)
    solde = p["montant_contrat"] - total_avance
    conn.close()
    return render_template("prestataire_detail.html", p=p, avances=avances,
                            total_avance=total_avance, solde=solde)


@app.route("/prestataires/<int:pid>/modifier", methods=["GET", "POST"])
@admin_required
def prestataire_modifier(pid):
    conn = get_db()
    if request.method == "POST":
        f = request.form
        conn.execute("""
            UPDATE prestataires SET chantier_id=?, nom=?, telephone=?, specialite=?, travaux=?,
                montant_contrat=?, date_debut=?, date_fin_prevue=?, date_fin_reelle=?, statut=?, notes=?
            WHERE id=?
        """, (f.get("chantier_id") or None, f["nom"], f.get("telephone"), f.get("specialite"),
              f.get("travaux"), float(f.get("montant_contrat") or 0), f.get("date_debut"),
              f.get("date_fin_prevue"), f.get("date_fin_reelle"), f.get("statut"), f.get("notes"), pid))
        conn.commit()
        conn.close()
        flash("Prestataire mis à jour.", "success")
        return redirect(url_for("prestataire_detail", pid=pid))
    p = conn.execute("SELECT * FROM prestataires WHERE id=?", (pid,)).fetchone()
    chantiers = conn.execute("SELECT * FROM chantiers").fetchall()
    conn.close()
    return render_template("prestataire_form.html", p=p, chantiers=chantiers)


@app.route("/prestataires/<int:pid>/supprimer", methods=["POST"])
@admin_required
def prestataire_supprimer(pid):
    conn = get_db()
    conn.execute("DELETE FROM prestataires WHERE id=?", (pid,))
    conn.commit()
    conn.close()
    flash("Prestataire supprimé.", "success")
    return redirect(url_for("prestataires_list"))


# ---------- AVANCES ----------
@app.route("/prestataires/<int:pid>/avances/nouvelle", methods=["POST"])
@login_required
def avance_nouvelle(pid):
    f = request.form
    conn = get_db()
    conn.execute("""
        INSERT INTO avances (prestataire_id, date, montant, libelle, mode_paiement, saisi_par, date_saisie)
        VALUES (?,?,?,?,?,?,?)
    """, (pid, f.get("date"), float(f.get("montant") or 0), f.get("libelle"),
          f.get("mode_paiement"), session.get("username"), datetime.now().isoformat()))
    conn.commit()
    conn.close()
    flash("Avance enregistrée.", "success")
    return redirect(url_for("prestataire_detail", pid=pid))


@app.route("/avances/<int:aid>/supprimer", methods=["POST"])
@admin_required
def avance_supprimer(aid):
    conn = get_db()
    row = conn.execute("SELECT prestataire_id FROM avances WHERE id=?", (aid,)).fetchone()
    conn.execute("DELETE FROM avances WHERE id=?", (aid,))
    conn.commit()
    conn.close()
    flash("Avance supprimée.", "success")
    return redirect(url_for("prestataire_detail", pid=row["prestataire_id"]))


# ---------- ACHATS ----------
def _achats_query(args, conn):
    """Construit et exécute la requête achats à partir des filtres GET.
    Tri par défaut : chantier en 1er, puis référence (TC N), puis date."""
    q = args.get("q", "").strip()
    chantier_id = args.get("chantier_id", "")
    tableau_ref = args.get("tableau_ref", "").strip()
    categorie = args.get("categorie", "")
    date_min = args.get("date_min", "")
    date_max = args.get("date_max", "")
    montant_min = args.get("montant_min", "")
    montant_max = args.get("montant_max", "")

    sql = """
        SELECT a.*, c.nom as chantier_nom
        FROM achats a LEFT JOIN chantiers c ON c.id = a.chantier_id
        WHERE 1=1
    """
    params = []
    if q:
        sql += " AND (a.fournisseur LIKE ? OR a.objet LIKE ? OR a.tableau_ref LIKE ?)"
        params += [f"%{q}%"] * 3
    if chantier_id:
        sql += " AND a.chantier_id = ?"
        params.append(chantier_id)
    if tableau_ref:
        sql += " AND a.tableau_ref LIKE ?"
        params.append(f"%{tableau_ref}%")
    if categorie:
        sql += " AND a.categorie = ?"
        params.append(categorie)
    if date_min:
        sql += " AND a.date >= ?"
        params.append(date_min)
    if date_max:
        sql += " AND a.date <= ?"
        params.append(date_max)
    if montant_min:
        sql += " AND a.montant >= ?"
        params.append(float(montant_min))
    if montant_max:
        sql += " AND a.montant <= ?"
        params.append(float(montant_max))
    # Filtre par chantier en 1er, puis par référence TC N, puis par date
    sql += " ORDER BY c.nom IS NULL, c.nom, a.tableau_ref, a.date DESC, a.id DESC"
    rows = conn.execute(sql, params).fetchall()
    total = sum(r["montant"] for r in rows)
    filtres = dict(q=q, chantier_id=chantier_id, tableau_ref=tableau_ref, categorie=categorie,
                   date_min=date_min, date_max=date_max, montant_min=montant_min, montant_max=montant_max)
    return rows, total, filtres


@app.route("/achats")
@login_required
def achats_list():
    conn = get_db()
    rows, total, filtres = _achats_query(request.args, conn)
    categories = [r["nom"] for r in conn.execute("SELECT nom FROM categories_achat ORDER BY nom").fetchall()]
    chantiers = conn.execute("SELECT * FROM chantiers ORDER BY nom").fetchall()
    conn.close()
    return render_template("achats_list.html", rows=rows, total=total, categories=categories,
                            chantiers=chantiers, **filtres)


@app.route("/achats/imprimer")
@login_required
def achats_imprimer():
    conn = get_db()
    rows, total, filtres = _achats_query(request.args, conn)
    chantier_nom = None
    if filtres.get("chantier_id"):
        ch = conn.execute("SELECT nom FROM chantiers WHERE id=?", (filtres["chantier_id"],)).fetchone()
        chantier_nom = ch["nom"] if ch else None
    conn.close()
    return render_template("achats_print.html", rows=rows, total=total, chantier_nom=chantier_nom,
                            filtres=filtres, date_impression=datetime.now().strftime("%d/%m/%Y %H:%M"))


@app.route("/achats/nouveau", methods=["GET", "POST"])
@login_required
def achat_nouveau():
    conn = get_db()
    if request.method == "POST":
        f = request.form
        categorie, pu, quantite, montant = _resoudre_categorie_et_montant(f, conn)
        conn.execute("""
            INSERT INTO achats (chantier_id, date, fournisseur, objet, categorie, montant,
                pu, quantite, tableau_ref, mode_paiement, saisi_par, date_saisie)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (f.get("chantier_id") or None, f.get("date"), f.get("fournisseur"), f.get("objet"),
              categorie, montant, pu, quantite, f.get("tableau_ref"),
              f.get("mode_paiement"), session.get("username"), datetime.now().isoformat()))
        conn.commit()
        conn.close()
        flash("Achat enregistré.", "success")
        return redirect(url_for("achats_list"))
    chantiers = conn.execute("SELECT * FROM chantiers").fetchall()
    categories = [r["nom"] for r in conn.execute("SELECT nom FROM categories_achat ORDER BY nom").fetchall()]
    conn.close()
    return render_template("achat_form.html", a=None, chantiers=chantiers, categories=categories)


def _resoudre_categorie_et_montant(f, conn):
    """Gère le choix 'Autre' (enregistre la nouvelle catégorie en base) et
    calcule le montant = PU x quantité quand ces deux champs sont fournis."""
    categorie = (f.get("categorie") or "").strip()
    if categorie == "__new__":
        nouvelle = (f.get("nouvelle_categorie") or "").strip()
        if nouvelle:
            conn.execute("INSERT OR IGNORE INTO categories_achat (nom) VALUES (?)", (nouvelle,))
            categorie = nouvelle
        else:
            categorie = ""
    pu_raw = f.get("pu", "").strip()
    qte_raw = f.get("quantite", "").strip()
    pu = float(pu_raw) if pu_raw else 0
    quantite = float(qte_raw) if qte_raw else 0
    if pu and quantite:
        montant = pu * quantite
    else:
        montant = float(f.get("montant") or 0)
    return categorie, pu, quantite, montant


@app.route("/achats/<int:aid>/modifier", methods=["GET", "POST"])
@admin_required
def achat_modifier(aid):
    conn = get_db()
    if request.method == "POST":
        f = request.form
        categorie, pu, quantite, montant = _resoudre_categorie_et_montant(f, conn)
        conn.execute("""
            UPDATE achats SET chantier_id=?, date=?, fournisseur=?, objet=?, categorie=?,
                montant=?, pu=?, quantite=?, tableau_ref=?, mode_paiement=? WHERE id=?
        """, (f.get("chantier_id") or None, f.get("date"), f.get("fournisseur"), f.get("objet"),
              categorie, montant, pu, quantite, f.get("tableau_ref"),
              f.get("mode_paiement"), aid))
        conn.commit()
        conn.close()
        flash("Achat mis à jour.", "success")
        return redirect(url_for("achats_list"))
    a = conn.execute("SELECT * FROM achats WHERE id=?", (aid,)).fetchone()
    chantiers = conn.execute("SELECT * FROM chantiers").fetchall()
    categories = [r["nom"] for r in conn.execute("SELECT nom FROM categories_achat ORDER BY nom").fetchall()]
    conn.close()
    return render_template("achat_form.html", a=a, chantiers=chantiers, categories=categories)


@app.route("/achats/<int:aid>/supprimer", methods=["POST"])
@admin_required
def achat_supprimer(aid):
    conn = get_db()
    conn.execute("DELETE FROM achats WHERE id=?", (aid,))
    conn.commit()
    conn.close()
    flash("Achat supprimé.", "success")
    return redirect(url_for("achats_list"))


# ---------- EXPORT CSV ----------
@app.route("/export/prestataires.csv")
@login_required
def export_prestataires():
    conn = get_db()
    rows = conn.execute("""
        SELECT p.nom, p.telephone, p.specialite, p.travaux, p.montant_contrat,
               COALESCE(SUM(av.montant),0) as total_avance,
               (p.montant_contrat - COALESCE(SUM(av.montant),0)) as solde,
               p.date_debut, p.date_fin_prevue, p.date_fin_reelle, p.statut
        FROM prestataires p LEFT JOIN avances av ON av.prestataire_id=p.id
        GROUP BY p.id ORDER BY p.id
    """).fetchall()
    conn.close()
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(["Nom", "Téléphone", "Spécialité", "Travaux", "Montant contrat",
                      "Total avances", "Solde", "Date début", "Fin prévue", "Fin réelle", "Statut"])
    for r in rows:
        writer.writerow(list(r))
    mem = io.BytesIO(output.getvalue().encode("utf-8-sig"))
    return send_file(mem, mimetype="text/csv", as_attachment=True, download_name="prestataires.csv")


@app.route("/export/achats.csv")
@login_required
def export_achats():
    conn = get_db()
    rows = conn.execute("SELECT date, fournisseur, objet, categorie, montant, tableau_ref, mode_paiement FROM achats ORDER BY date").fetchall()
    conn.close()
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(["Date", "Fournisseur", "Objet", "Catégorie", "Montant", "Référence", "Mode paiement"])
    for r in rows:
        writer.writerow(list(r))
    mem = io.BytesIO(output.getvalue().encode("utf-8-sig"))
    return send_file(mem, mimetype="text/csv", as_attachment=True, download_name="achats.csv")


# ---------- ADMIN UTILISATEURS ----------
@app.route("/utilisateurs")
@admin_required
def utilisateurs_list():
    conn = get_db()
    rows = conn.execute("SELECT * FROM users ORDER BY id").fetchall()
    conn.close()
    return render_template("utilisateurs.html", rows=rows)


@app.route("/utilisateurs/nouveau", methods=["POST"])
@admin_required
def utilisateur_nouveau():
    from werkzeug.security import generate_password_hash
    f = request.form
    conn = get_db()
    try:
        conn.execute("INSERT INTO users (username, password, nom_complet, role) VALUES (?,?,?,?)",
                     (f["username"].strip(), generate_password_hash(f["password"]), f.get("nom_complet"), f.get("role", "saisie")))
        conn.commit()
        flash("Utilisateur créé.", "success")
    except sqlite3.IntegrityError:
        flash("Ce nom d'utilisateur existe déjà.", "danger")
    conn.close()
    return redirect(url_for("utilisateurs_list"))


@app.route("/utilisateurs/<int:uid>/toggle", methods=["POST"])
@admin_required
def utilisateur_toggle(uid):
    conn = get_db()
    u = conn.execute("SELECT actif FROM users WHERE id=?", (uid,)).fetchone()
    conn.execute("UPDATE users SET actif=? WHERE id=?", (0 if u["actif"] else 1, uid))
    conn.commit()
    conn.close()
    return redirect(url_for("utilisateurs_list"))


@app.route("/utilisateurs/<int:uid>/reinit", methods=["POST"])
@admin_required
def utilisateur_reinit(uid):
    from werkzeug.security import generate_password_hash
    f = request.form
    conn = get_db()
    conn.execute("UPDATE users SET password=? WHERE id=?", (generate_password_hash(f["password"]), uid))
    conn.commit()
    conn.close()
    flash("Mot de passe réinitialisé.", "success")
    return redirect(url_for("utilisateurs_list"))


# ---------- CHANTIERS ----------
@app.route("/chantiers", methods=["GET", "POST"])
@admin_required
def chantiers_list():
    conn = get_db()
    if request.method == "POST":
        conn.execute("INSERT INTO chantiers (nom, description, date_creation) VALUES (?,?,?)",
                     (request.form["nom"], request.form.get("description"), datetime.now().isoformat()))
        conn.commit()
        flash("Chantier ajouté.", "success")
    rows = conn.execute("SELECT * FROM chantiers ORDER BY id").fetchall()
    conn.close()
    return render_template("chantiers.html", rows=rows)


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    print("="*60)
    print(" GESTION CHANTIERS - démarrage du serveur")
    print(f" Accès local : http://localhost:{port}")
    print(" Accès réseau (autres PC/téléphones) : http://<IP-DE-CE-PC>:{port}")
    print("="*60)
    app.run(host="0.0.0.0", port=port, debug=False)
else:
    # Cas du déploiement en production via Gunicorn (Render, etc.)
    # __main__ n'est pas exécuté : on initialise donc la base ici.
    init_db()
