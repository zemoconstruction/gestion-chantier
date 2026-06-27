# GESTION CHANTIERS — Logiciel de gestion des prestataires, avances et achats

Logiciel conçu pour remplacer votre fichier Excel "PROJET PRIVE PCA". Il fonctionne
comme un petit site web installé sur un de vos ordinateurs (le "serveur") et accessible
depuis tous les autres PC et téléphones de votre réseau (Wi-Fi local), avec une base
de données commune et partagée en temps réel.

## 1. Installation — fabriquer votre logiciel .exe (à faire une seule fois)

**Pré-requis : Python 3** doit être installé sur l'ordinateur qui servira de "serveur"
(celui qui restera allumé pour que les autres y accèdent).
- Si vous ne l'avez pas : téléchargez-le sur https://www.python.org/downloads/
- Sous Windows, cochez bien la case **"Add Python to PATH"** pendant l'installation.

**Windows — méthode recommandée (vrai logiciel .exe) :**
1. Double-cliquez sur `FABRIQUER_LE_EXE_WINDOWS.bat`
2. Attendez 1 à 2 minutes (installation puis fabrication automatique)
3. Un fichier **`GestionChantiers.exe`** apparaît dans le dossier — c'est votre logiciel
4. Mettez-le où vous voulez (Bureau, Démarrer...) et double-cliquez pour le lancer :
   il démarre tout seul et ouvre directement votre navigateur, sans terminal ni
   ligne de commande à voir. Double-cliquer une 2e fois ouvre simplement un nouvel
   onglet (il ne redémarre pas deux fois).
5. Pour fermer le logiciel : fermez l'onglet du navigateur, puis dans la barre des
   tâches Windows (icônes cachées, en bas à droite) trouvez l'icône du logiciel et
   "Quitter", ou redémarrez simplement l'ordinateur.

⚠️ Le dossier **`data`** (qui contient toutes vos données) doit toujours rester
juste à côté de `GestionChantiers.exe`. Si vous déplacez l'exe, déplacez le dossier
`data` avec lui.

**Alternative sans fabriquer de .exe (Windows/Mac/Linux), via un script :**
- Windows : double-cliquez sur `installer_et_lancer_windows.bat`
- Mac/Linux : `./installer_et_lancer_mac_linux.sh` (terminal)
Cette méthode garde une fenêtre noire ouverte (terminal) pendant l'utilisation.

## 2. Importer vos anciennes données Excel (recommandé, une seule fois)

Lancez d'abord une fois `GestionChantiers.exe` (ou le script de lancement) pour
créer le dossier `data`, puis fermez-le. Ensuite, ouvrez une invite de commandes
dans ce dossier et lancez :

```
build_env\Scripts\activate
python import_excel.py "PROJET_PRIVE_PCA.xlsx"
```
(remplacez le chemin par l'emplacement réel de votre fichier ; si vous avez utilisé
la méthode "script" plutôt que le .exe, remplacez `build_env` par `venv`)

Cela reprend automatiquement :
- tous les **achats** de vos différents "TABLEAUX DE CHÈQUE" / "TC" avec leur date,
  fournisseur, objet et montant ;
- toutes les **avances** versées aux prestataires (lignes contenant "avance",
  "solde", "avenant", "acompte") ;
- crée automatiquement la **fiche de chaque prestataire** détecté.

⚠️ Le numéro de téléphone, le montant exact du contrat et les dates de début/fin
n'existaient pas de façon exploitable dans votre fichier Excel : pensez à compléter
ces fiches une fois importées (Prestataires → cliquer sur le nom → Modifier).

## 3. Accès depuis les autres ordinateurs / téléphones

Le logiciel (qu'il soit lancé via `GestionChantiers.exe` ou via le script) doit
rester actif sur l'ordinateur "serveur" pendant toute l'utilisation.

Repérez l'adresse réseau de ce PC :
- **Windows** : ouvrez l'invite de commandes, tapez `ipconfig`, notez "Adresse IPv4"
- **Mac** : Préférences Système → Réseau, notez l'adresse IP
- **Téléphone** : doit être connecté au **même Wi-Fi** que l'ordinateur serveur

Depuis n'importe quel autre appareil, ouvrez un navigateur (Chrome, Safari...) et
tapez :
```
http://ADRESSE-IP-DU-SERVEUR:5000
```
Exemple : `http://192.168.1.25:5000`

💡 Astuce : sur téléphone, ouvrez cette adresse puis "Ajouter à l'écran d'accueil"
pour avoir une icône comme une vraie application.

## 4. Les deux types d'accès

| Rôle | Peut faire |
|---|---|
| **Admin** (`admin` / `admin123`) | Tout : ajouter, modifier, supprimer, gérer les utilisateurs et les chantiers |
| **Saisie** (`saisie` / `saisie123`) | Ajouter des prestataires, des avances, des achats — **ne peut rien modifier ni supprimer** |

➡️ **Changez ces mots de passe dès le premier lancement** : connectez-vous en
admin, allez dans "Utilisateurs", cliquez "Mdp" sur chaque compte.
Vous pouvez aussi créer un compte "Saisie" différent pour chacun de vos 2 à 5
agents (recommandé, pour savoir qui a saisi quoi).

## 5. Fonctionnalités

- **Tableau de bord** : total achats, total avances, total des contrats, solde
  global restant à payer, derniers mouvements, prestataires les plus exposés.
- **Prestataires** : fiche complète (nom, téléphone, travaux, montant du contrat,
  dates), historique de toutes ses avances, calcul automatique du **solde restant**.
  Recherche par nom/téléphone/travaux + filtres par statut, période, montant.
- **Achats** : enregistrement par fournisseur/objet/catégorie/montant/référence,
  recherche et filtres par catégorie, période, montant.
- **Export CSV** des deux tableaux (ouvrable directement dans Excel) pour vos
  impressions ou votre comptable.
- **Multi-chantiers** : si vous gérez plusieurs chantiers, créez-les dans
  "Chantiers" et associez prestataires/achats à chacun.
- Tous les montants et soldes sont **calculés automatiquement** — plus aucun
  risque d'erreur de formule comme dans Excel.

## 6. Sauvegarde de vos données

Toutes les données sont dans le fichier `data/gestion_chantiers.db`. Pour sauvegarder,
copiez simplement ce fichier régulièrement (clé USB, cloud, etc.). Pour restaurer,
remettez-le à sa place avant de relancer le logiciel.

## 7. Démarrage automatique avec Windows (optionnel)

Pour que le logiciel démarre tout seul à l'allumage du PC serveur : faites un clic
droit sur `GestionChantiers.exe` → Créer un raccourci, puis déposez ce raccourci
dans le dossier de démarrage Windows (`Win+R`, tapez `shell:startup`, validez).
