# Flux RSS auto du catalogue PDO de SHAPE — mode d'emploi

Ce petit dispositif publie une URL RSS **fixe** et **mise à jour toute seule**,
que tu colles dans Feedly. Tout tourne gratuitement sur les serveurs de GitHub :
tu ne codes rien, tu n'installes rien, tu n'as aucun serveur à gérer.

**Ton URL finale ressemblera à :**
```
https://TON-PSEUDO.github.io/pdo-feed/feed.xml
```
(remplace `TON-PSEUDO` par ton identifiant GitHub, choisi à l'étape 1)

---

## Les 4 fichiers fournis

| Fichier              | Où il doit aller dans le dépôt        |
|----------------------|----------------------------------------|
| `scrape.py`          | à la racine                            |
| `requirements.txt`   | à la racine                            |
| `pdo-feed.yml`       | dans le dossier `.github/workflows/`   |
| `index.html`         | (généré tout seul — rien à faire)      |

---

## Étape 1 — Créer un compte GitHub (2 min, gratuit)

1. Va sur https://github.com → **Sign up**.
2. Choisis un identifiant (= `TON-PSEUDO`), un e-mail, un mot de passe.
3. Valide l'e-mail de confirmation.

## Étape 2 — Créer le dépôt

1. En haut à droite : **+** → **New repository**.
2. **Repository name** : `pdo-feed` (garde exactement ce nom, ton URL en dépend).
3. Coche **Public**.
4. Coche **Add a README file**.
5. Clique **Create repository**.

## Étape 3 — Déposer les fichiers

Pour chaque fichier (`scrape.py`, `requirements.txt`) :

1. Dans ton dépôt : bouton **Add file** → **Upload files**.
2. Glisse le fichier, puis **Commit changes**.

Pour le workflow, il doit être rangé dans un sous-dossier :

1. **Add file** → **Create new file**.
2. Dans le champ du nom, tape exactement : `.github/workflows/pdo-feed.yml`
   (le `/` crée automatiquement les dossiers).
3. Ouvre `pdo-feed.yml` fourni, copie tout son contenu, colle-le dans la zone.
4. **Commit changes**.

> Dès ce commit, le robot se lance une première fois. Va dans l'onglet
> **Actions** : tu verras « PDO Feed » tourner (rond orange), puis un ✅ vert
> au bout d'une minute. `feed.xml` apparaît alors à la racine du dépôt.

## Étape 4 — Activer la page publique (GitHub Pages)

1. Onglet **Settings** du dépôt → menu de gauche **Pages**.
2. Sous **Build and deployment** → **Source** : choisis **Deploy from a branch**.
3. **Branch** : `main`, dossier `/ (root)` → **Save**.
4. Attends ~1 min. La page affichera : *Your site is live at* `https://TON-PSEUDO.github.io/pdo-feed/`.

## Étape 5 — Récupérer l'URL du flux et la brancher dans Feedly

Ton URL RSS est simplement la page ci-dessus suivie de `feed.xml` :
```
https://TON-PSEUDO.github.io/pdo-feed/feed.xml
```
1. Ouvre-la une fois dans ton navigateur pour vérifier que du XML s'affiche.
2. Dans **Feedly** : **+ (Add Content)** → **Follow a feed / RSS** → colle cette URL → **Follow**.

C'est fini. ✅

---

## Ce qui se passe ensuite (tout seul)

- Toutes les 6 h, le robot relit le catalogue et réécrit `feed.xml`.
- Chaque objet a un identifiant unique (son lien). **Un nouvel objet = une
  nouvelle entrée** qui remonte en non-lu dans Feedly. Les objets déjà vus ne
  reviennent pas.
- Une page lisible est aussi dispo sur `https://TON-PSEUDO.github.io/pdo-feed/`.

## Réglages faciles

- **Fréquence** : dans `pdo-feed.yml`, la ligne `cron: "0 */6 * * *"` = toutes
  les 6 h. Pour toutes les 3 h : `"0 */3 * * *"`. Pour une fois par jour à 7 h :
  `"0 7 * * *"`.
- **Relancer à la main** : onglet **Actions** → « PDO Feed » → **Run workflow**.

## Si ça coince

- **Le flux est vide / l'Action est en ❌ rouge** : ouvre l'Action, lis le
  message. Le plus probable : le site a changé de structure — dis-le-moi, on
  ajuste `scrape.py`.
- **Le push échoue (permissions)** : Settings → Actions → General → tout en bas
  **Workflow permissions** → coche **Read and write permissions** → Save, puis
  relance l'Action.
- **Plus de mise à jour après 2 mois** : GitHub met en veille les tâches
  planifiées si le dépôt est inactif. Il suffit de relancer une fois à la main
  (Actions → Run workflow) pour repartir.

---

*Rien de tout ce code ne tourne sur ta machine. Tu peux fermer l'ordinateur :
le flux continue de vivre sur GitHub.*
