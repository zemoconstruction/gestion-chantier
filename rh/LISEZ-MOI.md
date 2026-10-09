# RH Pro — gestion des ressources humaines

Logiciel web simple et fluide (Flask + SQLite, aucune base à installer).
Indépendant de l'application de gestion de chantiers située à la racine du dépôt.

## Lancer
```
cd rh
pip install -r requirements.txt
python app.py --demo      # --demo : charge des données d'exemple (optionnel)
```
Ouvrez http://localhost:5001. Au premier démarrage, le mot de passe du compte `admin`
est généré et affiché dans le terminal (à changer via « Mon mot de passe »).
Variables utiles : `PORT`, `DATA_DIR` (dossier de la base et des fichiers), `SECRET_KEY`.

## Modules
| Besoin | Où |
|---|---|
| Dossiers employés, accès portail | Employés → fiche |
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

## À savoir
- Rôles : **RH (admin)** a accès à tout ; **employé** voit uniquement son espace (ses congés,
  bulletins validés, évaluations, formations, annonces).
- La paie utilise des **taux uniques paramétrables** (Paramètres) : cotisations salariales,
  charges patronales, impôt. C'est une simplification : faites valider les règles
  (barème progressif, plafonds…) par votre comptable avant tout usage réel.
- Les déclarations sont préparées (montants) mais **non transmises** automatiquement à l'administration.
- Sauvegarde : copiez le dossier `data/`.
