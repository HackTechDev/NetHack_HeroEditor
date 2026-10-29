# Tutoriel : votre première héroïne avec nhheroedit

Ce tutoriel crée pas à pas une héroïne pour le NetHack de Night City :
**Nyx, netrunneuse réplicante**, une ancienne analyste d'Arasaka qui
plonge dans le Net pour son propre compte. On règle ses options, on
change quelques règles de départ de son rôle (titre, or, intrinsèques,
inventaire, tuile), on les ajoute aux sources du jeu, puis on joue avec
elle. Comptez vingt-cinq minutes, compilation comprise.

Les touches à taper sont indiquées entre crochets : `[n]`, `[Entrée]`…
L'aide complète s'affiche à tout moment avec `[?]`, et la ligne cyan en
bas de l'écran explique le champ sélectionné.

À la fin, la partie commencera ainsi :

```
Nyx

Ancienne analyste d'Arasaka, Nyx a vu ce que la corpo cachait dans le Net.
Elle a vendu son badge, gardé ses implants, et plonge désormais pour son
propre compte.

Son chat Bitmap est le seul à connaître son vrai nom.
--Plus--

Nyx la Pirate du câble        Fo:11 Dx:16 Co:16 In:17 Sa:8 Ch:7 Chaotique
Niv:1 $:800 PV:11(11) Pm:8(8) CA:9 Xp:1 T:1
```

## 1. Lancer l'éditeur

Dans un terminal d'au moins 80 colonnes sur 24 lignes (120 colonnes
pour voir le panneau « Aperçu » à droite), depuis le dossier de
l'éditeur :

```sh
./nhheroedit.sh tutoriel.json
```

`tutoriel.json` est le fichier du projet : il garde vos héros et les
changements de leurs rôles. Il n'existe pas encore et sera créé au
premier enregistrement. Sans nom de fichier, l'éditeur ouvre
`heros.json`.

L'éditeur cherche les sources du jeu dans `../NetHack-5.0.0` (sinon :
option `--src`) et le jeu installé dans `~/nh/install/games/lib/nethackdir`
(sinon : variable `NHHEROEDIT_HACKDIR`).

L'écran se compose de :

- la **liste des héros** du projet, à gauche (vide pour l'instant) ;
- la **fiche** du héros choisi, au centre : le héros lui-même, son
  profil d'affichage, puis les règles de son rôle ;
- le panneau **Aperçu**, à droite si le terminal est assez large : titre,
  attributs possibles, PV, dieu, état du rôle dans les sources,
  inventaire de départ, problèmes détectés et tuile ;
- en bas, l'aide du champ et la ligne des touches (ou le dernier
  message).

`[Tab]` passe de la liste à la fiche et inversement.

## 2. Partir d'un archétype

Plutôt que de remplir une fiche vide, on part d'un des treize
archétypes de Night City (un par rôle du jeu) :

1. `[n]` ouvre la liste des archétypes. Tapez `net` pour la filtrer, puis
   `[Entrée]` sur **Netrunner** (le rôle Wizard du jeu).
2. L'éditeur demande le **nom du héros**, proposé par l'archétype
   (« Glitch »). `[Ctrl-U]` efface la ligne ; tapez `Nyx` puis `[Entrée]`.

La fiche se remplit et l'Aperçu montre déjà le titre de départ
(« Script-kiddie »), la combinaison « Netrunner réplicant, chaotique »,
les attributs, l'inventaire du rôle et **✔ aucun problème**.

« Héros au hasard », en bas de la liste, tire un rôle, une combinaison
permise, un nom et une biographie ; `[N]` donne plus tard un nom de
Night City au hasard au héros choisi.

## 3. Régler l'héroïne

`[Tab]` passe dans la fiche. Les flèches `[↑]` `[↓]` choisissent un
champ, `[←]` `[→]` changent une valeur à choix, `[Entrée]` ouvre la
liste ou la saisie. `[u]` annule la dernière modification.

1. **Sexe** : `[→]` donne **féminin**. Le rôle et la race s'accordent
   (« Netrunneuse réplicante »).
2. **Animal** : il est « imposé par le rôle : chaton-robot » (le rôle
   en a un d'office) ; son **nom**, « Bitmap », vient de l'archétype.
3. **Fruit préféré** : `[Entrée]`, tapez `ramen synthétique`,
   `[Entrée]`.
4. **Biographie** : `[Entrée]` ouvre un petit éditeur de texte. Effacez
   le texte de l'archétype (`[Suppr]`) et écrivez :

   > Ancienne analyste d'Arasaka, Nyx a vu ce que la corpo cachait dans
   > le Net. Elle a vendu son badge, gardé ses implants, et plonge
   > désormais pour son propre compte.
   >
   > Son chat Bitmap est le seul à connaître son vrai nom.

   `[Entrée]` coupe un paragraphe ; `[Échap]` termine. Cette biographie
   sera montrée au début de chaque nouvelle partie de Nyx.

Une valeur que le rôle ou la race refuse est marquée **✖ interdit**
(essayez `[←]` sur la race, puis `[u]`) : l'Aperçu signale alors le
problème en rouge.

## 4. Le profil d'affichage

La section « Affichage » règle l'interface du jeu pour ce héros
seulement (vide = votre `.nethackrc`) :

1. **Symboles** : `[Entrée]`, tapez `DEC`, `[Entrée]` : la carte sera
   dessinée avec les traits de **DECgraphics**.
2. **Couleurs** : `[→]` choisit le profil **Night City** : ligne d'état
   colorée selon les PV et l'énergie, objets bénis en cyan, maudits en
   rouge dans les menus.

## 5. Les règles du rôle

Tout ce qui suit la ligne « ▸ Rôle « Netrunneuse » » change les règles
de départ **du rôle** : elles vaudront pour tous ses héros, et il faudra
les intégrer aux sources du jeu. Un champ modifié est marqué **●** ;
`[Suppr]` lui rend la valeur du jeu.

1. **Rang 1** : `[Entrée]` montre le titre dans ses six versions
   (anglais, français et Night City, au masculin et au féminin).
   Choisissez **Night City, féminin**, `[Ctrl-U]`, tapez
   `Pirate du câble`, `[Entrée]`, puis `[Échap]`. L'Aperçu affiche le
   nouveau titre.
2. **Or de départ** (plus bas, après les attributs et les PV) :
   `[Entrée]`, `800`, `[Entrée]`. Le Netrunner n'en avait pas.
3. **Intrinsèques** : `[Entrée]`, puis `[Espace]` sur **télépathie** et
   sur **résistance au poison**, `[Entrée]` pour valider.
4. **Inventaire** : `[k]` ouvre l'inventaire de départ. `[a]` ajoute un
   objet : tapez `puce de` pour filtrer et choisissez **outil : puce de
   crédit** (de quoi crocheter les portes). Acceptez la quantité (`1`)
   et l'enchantement, puis choisissez **non maudit**. La puce apparaît
   dans la liste ; `[Échap]` referme l'inventaire.

Le champ **Animal imposé** permet aussi de donner au rôle un autre
animal de départ, y compris un robot créé avec nhmonedit (voir la
section 11).

## 6. La tuile

Dans le terminal, le héros est un `@` ; les versions graphiques du jeu
(Qt, X11) le dessinent avec une **tuile** 16×16, celle du rôle et du
sexe.

1. `[t]` ouvre l'éditeur de pixels sur la tuile de la Netrunneuse.
   L'aperçu en taille réelle est à droite de la grille, et la tuile de
   l'autre sexe juste dessous (`[c]` la recopierait).
2. `[l]` pose un **calque Night City** : choisissez **Visière**. Les
   flèches déplacent le calque, `[Entrée]` le pose.
3. `[e]` exporte la tuile en image : **PNG** (128×128), `[Entrée]` sur
   le nom proposé (`nyx-female.png`, à côté du projet).
4. `[Échap]` garde le dessin et revient à la fiche.

Les flèches et `[Espace]` peignent pixel par pixel ; `[A]`–`[Z]`,
`[.]`, `[0]`, `[1]` choisissent la couleur ; `[u]` annule.

## 7. Vérifier et enregistrer

- `[v]` vérifie tous les héros du projet : **Nyx ✔**.
- `[c]` montre les options du héros (ce que `[x]` écrirait dans un
  `.nethackrc`) et le code C du rôle modifié.
- `[s]` enregistre le projet dans `tutoriel.json`.

## 8. Intégrer, compiler, installer

Les options du héros suffisent pour jouer, mais les règles du rôle
doivent entrer dans les sources du jeu :

1. `[I]` montre les changements prévus fichier par fichier ; `[q]` pour
   continuer, puis `[o]` pour confirmer. Les fichiers sont d'abord
   copiés dans `sauvegardes/`. Si les sources sont un dépôt git,
   l'éditeur propose un commit (`[Échap]` : non). L'Aperçu indique
   maintenant **Rôle : intégré**.
2. `[m]` compile le jeu (`make`) ; `[Entrée]` revient à l'éditeur :
   « Compilation réussie — U pour mettre à jour le jeu ».
3. `[U]` installe le jeu compilé (`make update`).

## 9. Jouer

`[j]` → **Partie normale** : l'éditeur résume les options passées au
jeu (nom, rôle, race, sexe, alignement, nom du chat, fruit, affichage)
et le fichier d'options complet qu'il écrit (votre configuration puis
celles du héros). `[o]` lance NetHack ; dans tmux, le jeu s'ouvre à
côté de l'éditeur.

Après le texte d'introduction vient la biographie de Nyx. La ligne
d'état dit « Nyx la Pirate du câble » et « $:800 » ; `[i]` montre la
puce de crédit dans l'inventaire.

Quittez quand vous voulez (`#quit` abandonne la partie, `S` la
sauvegarde : `[j]` proposera ensuite de la reprendre).

## 10. L'historique, et le lanceur

De retour dans l'éditeur, `[h]` montre l'**historique** des parties de
Nyx : date, score, fin de la partie (« a abandonné »), tours,
profondeur, conduites tenues. L'Aperçu en donne le résumé.

Le [lanceur](../Nethack_Launcher) peut lister les héros : avec
`heros = oui` dans sa section de l'éditeur de héros, une ligne
« ↳ Jack-in : Nyx » lance directement une partie avec elle.

## 11. Pour aller plus loin

- **Un robot compagnon** : créez un robot avec nhmonedit et
  intégrez-le ; il apparaît alors dans le champ **Animal imposé** du
  rôle (« robot de sécurité (robot de nhmonedit) »).
- **La quête du rôle** : `[Q]` ouvre l'un des cinq niveaux de quête du
  rôle (`dat/Wiz-strt.lua`…) dans l'éditeur de cartes nhmapedit.
- **Partager** : `[p]` exporte Nyx avec les règles de son rôle
  (`.nhhero.json`) ou en importe un autre ; `[x]` écrit ses options en
  `.nethackrc`.
- **Les noms** : `[T]` change le thème des noms affichés (Night City,
  français, anglais).

## 12. Revenir au jeu d'origine

`[R]` → **Retirer les modifications de l'éditeur**, `[o]` : les sources
reprennent leur texte d'origine (gardé dans les blocs marqués
`nhheroedit`). `[m]` puis `[U]` réinstallent le jeu d'origine. Le
projet, lui, garde Nyx et les règles de son rôle, prêtes à être
réintégrées.
