# RH Pro — gestion des ressources humaines

Logiciel web simple et fluide (Flask + SQLite, aucune base à installer).
Indépendant de l'application de gestion de chantiers située à la racine du dépôt.

## Lancer
- **Installateur Windows (recommandé)** : `RHPro-Setup.exe` installe le logiciel et crée les raccourcis (Bureau + menu Démarrer).
  Pour l'obtenir : sur GitHub, onglet *Actions* → « Installateur Windows » → *Run workflow* → téléchargez `RHPro-Setup` dans les artefacts
  (ou poussez un tag `v1.0` : l'installateur est publié dans *Releases*). Hors GitHub : `CREER_INSTALLATEUR_WINDOWS.bat` sur un PC Windows avec Python et Inno Setup.
  Version installée : données dans `%LOCALAPPDATA%\RHPro\data`, mot de passe `admin` initial dans `MOT_DE_PASSE_ADMIN.txt` (dans ce dossier), bouton « Quitter » en haut à droite.
- **Sans installer** : double-cliquez `LANCER_WINDOWS.bat`.
- **Mac/Linux** : `./lancer_linux_mac.sh`
- **Manuel** : `pip install -r requirements.txt && python main.py` (ajoutez `--demo` à `python app.py` pour des données d'exemple).
- **Docker** : `docker build -t rhpro . && docker run -p 5001:5001 -v rhdata:/data rhpro`

Ouvrez http://localhost:5001. Au premier démarrage, le mot de passe du compte `admin` est généré et affiché
dans le terminal ; il vous sera demandé de le changer à la première connexion.
Variables : `PORT`, `DATA_DIR` (base + fichiers), `SECRET_KEY`, `LOCAL_ONLY=1` (écoute locale uniquement).
Tests : `pip install -r requirements-dev.txt && pytest tests`.

## Modules
| Besoin | Où |
|---|---|
| Dossiers employés, hiérarchie, accès portail | Employés → fiche |
| Contrats, pièces, diplômes (avec alerte d'expiration) | Documents |
| Checklists d'arrivée et de départ | Intégration & départs |
| Offres d'emploi ouvertes | Offres d'emploi |
| Évaluations, feedbacks 1-to-1/360° | Performance |
| Candidatures, tri/étapes, CV, messages, embauche en un clic | Candidatures |
| Planification des entretiens | Entretiens |
| Demandes de congés (employé) / validation (RH), soldes | Mon espace / Congés |
| Calendrier d'équipe (mois, filtre département) | Calendrier absences |
| Paie : génération mensuelle, primes, bulletins imprimables | Paie |
| Déclarations fiscales/sociales préparées depuis la paie | Déclarations |
| Besoins et suivi des formations | Formations |
| Évaluation des compétences (niveau / cible) | Compétences |
| Talents clés, successeurs, risque de départ | Plan de succession |
| Indicateurs RH (effectif, turnover, masse salariale…) | Tableau de bord |
| Rapports personnalisés + export CSV/Excel | Rapports |
| Obligations légales et échéances | Conformité |
| Portail employé : documents, politiques, annonces | Portail & documents |
| Recueil des avis (anonyme possible) | Mon espace → Donner mon avis / Feedbacks |

## Professionnel
- Journal d'activité (qui a fait quoi), gestion des comptes, sauvegarde en un clic, jours fériés pris en compte dans les congés.
- Sécurité : mots de passe hachés, changement imposé au premier accès, protection CSRF, limitation des tentatives de connexion, session de 8 h, droits par rôle.
- Alertes du tableau de bord : fins de CDD, documents qui expirent, échéances de conformité et de déclarations, anniversaires.

## À savoir
- Rôles : **RH (admin)** a accès à tout ; **employé** voit uniquement son espace (ses congés,
  bulletins validés, évaluations, formations, annonces).
- La paie utilise des **taux uniques paramétrables** (Paramètres) : cotisations salariales,
  charges patronales, impôt. C'est une simplification : faites valider les règles
  (barème progressif, plafonds…) par votre comptable avant tout usage réel.
- Les déclarations sont préparées (montants) mais **non transmises** automatiquement à l'administration.
- Sauvegarde : copiez le dossier `data/`.
