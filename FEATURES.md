# Fonctionnalités de nhheroedit

Liste de ce que fait l'éditeur ; pour les touches et les fichiers
touchés, voir le [README](README.md) ou `?` dans l'éditeur.

## Généralités

- Éditeur plein écran en mode terminal, Python 3 et `curses`, sans
  dépendance externe ; même interface que nhmonedit (menus filtrables,
  cases à cocher, souris, annulation de 100 modifications, Ctrl-R pour
  rétablir, sauvegarde de secours toutes les minutes).
- Interface en français ou en anglais (`NHHEROEDIT_LANG`, configuration,
  sinon la locale).
- Lit les tables du jeu dans les sources **d'origine** (les modifications
  de l'éditeur sont retirées avant la lecture) : 13 rôles et 5 races de
  `src/role.c`, inventaires de `src/u_init.c`, 405 objets de
  `include/objects.h`, tuiles de `win/share/monsters.txt`, traductions de
  `po/fr.po` et `po/themes/fr@cyber.po`.
- Noms affichés dans le thème de la partie (Night City, français, ou
  noms anglais internes), choisi d'après `~/.nethackrc`, la
  configuration (`theme`) ou `T`.

## Héros

- Nom (vérifié comme le jeu : 31 caractères, sans `-` `,` `:` `=` `/`),
  rôle, race, sexe, alignement, animal (`pettype`) et son nom, fruit,
  conduites (`pauper`, `nudist`, `blind`, `deaf`, `!bones`), biographie
  et notes.
- Combinaisons permises calculées comme le jeu (masques du rôle et de la
  race) ; choix interdits marqués ✖ ; changer de rôle ajuste race, sexe
  et alignement en gardant le plus possible.
- Dieu du héros, titre de rang, plage de chaque attribut selon la race,
  PV et énergie de départ, animal imposé par le rôle.
- 13 archétypes de Night City (un par rôle) avec biographie ; noms
  uniques dans le projet.
- Héros au hasard (rôle, combinaison permise selon les rôles modifiés,
  nom, animal, biographie composée) ; générateur de noms de Night City
  (`N`) : pseudos de rue, surnoms, noms corporatistes.
- Profil d'affichage par héros : interface (`windowtype`, `-w`),
  symboles (`symset` du jeu), ramassage automatique, couleurs Night City
  (`hilite_status`, `MENUCOLOR`) ; écrit dans son `.nethackrc` et passé
  au jeu par `j`.
- Jeu lancé avec le héros : partie normale, découverte ou wizard ;
  partie sauvegardée du héros (ou de « wizard » en mode wizard) à
  reprendre, mettre de côté dans `parties/`, supprimer, ou remettre ;
  avertissements (jeu plus ancien que les sources ; mode refusé par `WIZARDS`
  ou `EXPLORERS` de `sysconf` ; `NETHACKOPTIONS` qui désigne un
  fichier).
- Dans tmux, jeu ouvert dans un panneau à côté de l'éditeur (ou une
  fenêtre tmux si l'écran est étroit) ; `tmux = non` pour le plein écran.
- Historique des parties du héros (`xlogfile`) : résumé dans l'aperçu,
  détail par partie avec la fin traduite par les catalogues du jeu,
  mode découverte ou wizard, conduites tenues.
- Fichier d'options complet (votre configuration puis le héros, options
  redéfinies mises en commentaire, `windowtype` en tête) : utilisé par
  `j` (`NETHACKOPTIONS=@fichier`) et exportable par `x`.
- Export des options en `.nethackrc` ; export et import d'un héros avec
  les changements de son rôle (`.nhhero.json`) ; fusion de projets.

## Rôles modifiés

- Titres des 9 rangs en anglais, français et Night City, au masculin et
  au féminin.
- Dieux loyal, neutre et chaotique (déesse avec `_`).
- Races, sexes et alignements permis.
- Base et poids des six attributs ; PV et énergie de départ (fixe + dé).
- Or de départ (remplace celui du jeu) ; 17 intrinsèques de départ.
- Inventaire de départ : objet précis ou au hasard d'une classe,
  quantité ou intervalle, enchantement ou charges, état (au hasard, non
  maudit, béni) ; ajout, retrait, déplacement, retour à l'inventaire du
  jeu ; deux variantes pour le Barbare.
- Tuiles mâle et femelle du rôle : éditeur de pixels, import de la tuile
  d'un monstre du jeu, retour à la tuile d'origine.
- Vérifications : total des poids (100), base (3 à 18, 75 points au
  plus), rôle sans race, sexe ou alignement, objets inconnus ou de la
  mauvaise classe, quantités, enchantements, caractères interdits ;
  titre anglais déjà employé ailleurs dans le jeu (d'après les
  références de `nethack.pot`) dont la traduction changerait, ou
  traduit différemment par deux rôles du projet.

## Intégration

- Plan des fichiers calculé sans rien écrire, différences affichées,
  traductions contrôlées par `msgfmt --check` (le thème fusionné avec
  `fr.po` comme le Makefile).
- Modifications marquées `nhheroedit`, texte d'origine conservé à côté
  (`#if 0` en C, commentaires dans `monsters.txt` et les `.po`) : retrait
  à l'identique ; une seconde intégration identique ne change rien.
- Correctif du titre au féminin dans `^X` et la liste des rangs atteints
  (`src/insight.c`), posé quand des titres de rang changent.
- Copie des fichiers dans `sauvegardes/<date>/` avant chaque écriture,
  rétablissement d'une sauvegarde, commit git proposé.
- État du rôle dans l'aperçu : d'origine, modifié non intégré, intégré,
  intégré puis modifié, intégré par un autre projet (nommé).
- Plusieurs projets dans les mêmes sources : le projet de chaque rôle
  intégré est noté dans `role.c` ; `I` garde (ou retire, au choix) les
  rôles des autres projets, relus dans leur fichier, et `R` peut ne
  retirer que ceux du projet ouvert.
- Compilation (`make`) et mise à jour du jeu installé (`make update`)
  avec les interfaces du dernier build (lues dans `dat/options`) :
  curses, X11 et Qt restent, les tuiles X11 et Qt sont refaites ;
  avertissement quand des tuiles changent sans X11 ni Qt compilés.
