# nhheroedit — éditeur de héros NetHack, version Night City

Éditeur plein écran en mode terminal (Python 3 + curses, sans dépendance
externe) pour créer les **héros** de NetHack 5.0 (branche `cybernethack`,
thème `fr@cyber`) : profession, race, sexe, alignement, animal… puis
lancer le jeu avec eux. Il permet aussi de **changer les règles de départ
d'un rôle** (inventaire, or, intrinsèques, attributs, PV, titres de rang,
dieux, races permises, tuile) et de les intégrer aux sources du jeu.

Il complète l'éditeur de cartes `../NetHack_MapEditor` et l'éditeur de
monstres `../NetHack_MonsterEditor`, dont il reprend l'interface.
La liste complète des fonctions est dans [FEATURES.md](FEATURES.md).

## Lancement

```sh
./nhheroedit.sh                     # projet heros.json, sources ../NetHack-5.0.0
./nhheroedit.sh mes-heros.json      # autre projet
./nhheroedit.sh --src ~/NetHack-5.0.0
./nhheroedit.sh --install           # lien ~/.local/bin/nhheroedit
```

Variables : `NHHEROEDIT_SRC` (sources du jeu), `NHHEROEDIT_HACKDIR`
(dossier du jeu installé, par défaut `~/nh/install/games/lib/nethackdir`),
`NHHEROEDIT_MOUSE=0` (sans souris), `NHHEROEDIT_LANG=en` ou `fr` (langue
de l'interface). Les mêmes réglages, et le **thème des noms** affichés,
peuvent aller dans `~/.config/nhheroedit/config` : voir
[`config.exemple`](config.exemple).

Terminal de 80×24 au minimum ; à partir de 120 colonnes, le panneau
« Aperçu » montre le héros en direct : titre, attributs, PV, dieu,
inventaire, problèmes et tuile.

## Le thème Night City

Les noms du jeu sont lus dans les traductions des sources
(`po/fr.po` et `po/themes/fr@cyber.po`) et affichés dans le thème de votre
partie (option `language` de `~/.nethackrc`) : la Valkyrie est une
**Solo**, le Magicien un **Netrunner**, l'elfe un **réplicant**, le
chaton un **chaton-robot**, la ration de nourriture une **ration
synthétique**… `T` passe de Night City au français puis aux noms
anglais internes.

`n` propose un archétype de Night City pour chacun des 13 rôles (Solo de
rue, Netrunner, Techie des tunnels, Medtech de clinique clandestine,
Fixer, Lawman, Nomade des Badlands, Ronin urbain, Influenceuse,
Traqueuse de primes, Technoprêtre, Moniale augmentée, Zonard des
décharges), avec une combinaison permise et une biographie.

Les titres de rang se règlent séparément en anglais (nom interne),
en français et en Night City, au masculin et au féminin. Le titre
anglais sert de clé aux traductions : s'il est déjà employé ailleurs
dans le jeu (« Rambler » est un rang du Touriste), changer sa
traduction la change aussi là-bas ; l'éditeur le signale et un autre
titre anglais l'évite.

## La fiche

**▸ Héros** — rien à intégrer, ce sont des options du jeu :

| Champ | Option NetHack |
|---|---|
| Nom | `name` (et `-u`) |
| Rôle, race, sexe, alignement | `role`, `race`, `gender`, `alignment` |
| Animal et son nom | `pettype`, `catname` / `dogname` / `horsename` |
| Fruit préféré | `fruit` |
| Conduites | `pauper`, `nudist`, `blind`, `deaf`, `!bones` |
| Biographie, notes | (pour vous) |

Seules les combinaisons permises par le rôle **et** la race sont
acceptées (✖ sinon) ; changer de rôle ramène race, sexe et alignement à
une combinaison valide.

**▸ Rôle** — les règles de départ, communes à **tous** les héros de ce
rôle (un champ modifié est marqué ●, `Suppr` rend la valeur du jeu) :

- titres des 9 rangs (anglais, français, Night City ; masculin et féminin) ;
- les trois dieux (`_` devant le nom : une déesse) ;
- races, sexes et alignements permis ;
- attributs : base et poids de chacun (avec la plage obtenue selon la race) ;
- PV et énergie de départ (fixe + dé), or de départ, intrinsèques
  (rapidité, télépathie, résistances…) ;
- inventaire de départ (`k`) : objets du jeu ou objet au hasard d'une
  classe, quantité (ou intervalle), enchantement ou charges, béni ;
  le Barbare a deux variantes, tirées au hasard par le jeu ;
- tuiles mâle et femelle (`t`), visibles dans les versions graphiques.

### La tuile

Dans le terminal, le héros est un `@` : la tuile 16×16 ne se voit que
dans les versions graphiques (Qt, X11). Elle est celle du **rôle et du
sexe** (`win/share/monsters.txt`), donc commune à tous les héros de ce
rôle. L'éditeur de pixels est celui de nhmonedit : flèches et Espace
pour peindre, une lettre de la palette (`A`–`Z`, `.`, `0`, `1`) pour la
couleur, `f` remplir, `p` pipette, `r` remplacer, `m` symétrie, `h`
retourner, `i` importer la tuile d'un des 394 monstres du jeu, `o`
revenir à la tuile d'origine, `u` annuler ; souris : clic ou glissé pour
peindre, clic droit pipette, molette pour la couleur.

## Touches

| Touche | Action |
|---|---|
| Tab | passer de la liste à la fiche |
| ↑ ↓ | héros / champ précédent ou suivant |
| ← → | changer la valeur (choix, nombre) |
| Entrée | modifier le champ |
| Suppr | vider le champ, rendre la valeur du jeu ; dans la liste : supprimer |
| `n` `d` | nouveau héros (archétype), dupliquer |
| `<` `>` `/` | déplacer, aller à un héros |
| `k` `t` | inventaire de départ, tuile du rôle |
| `T` | noms affichés : Night City, français, anglais |
| `v` `c` `x` | vérifier, voir les options et le code, écrire le `.nethackrc` |
| `I` `R` | intégrer aux sources, retirer ou rétablir une sauvegarde |
| `m` `U` `j` | compiler, mettre à jour le jeu installé, jouer |
| `p` | projet : fusionner, exporter ou importer un héros, rendre un rôle d'origine |
| `s` `u` Ctrl-R `?` `q` | enregistrer, annuler, rétablir, aide, quitter |

## Jouer

`j` lance NetHack avec le héros (options passées par `NETHACKOPTIONS`,
en plus de votre `.nethackrc`) : partie normale, mode découverte (`-X`)
ou mode wizard (`-D`). L'éditeur prévient si une partie sauvegardée du
héros existe (le jeu la reprend), si le jeu installé est plus ancien
que les sources modifiées, ou si `sysconf` (`WIZARDS`, `EXPLORERS`) ne
vous permet pas le mode choisi. En mode wizard, le jeu nomme toujours
le héros « wizard » (sa partie sauvegardée reste ainsi à part de la
vraie) ; rôle, race, sexe, alignement et règles du rôle sont bien ceux
du héros. `x` écrit les options dans `<nom>.nethackrc`, à recopier dans
`~/.nethackrc`.

## Du projet au jeu (rôles modifiés)

1. **`I` — intégrer.** L'éditeur vérifie les rôles, contrôle les
   traductions avec `msgfmt --check`, montre les différences, puis écrit
   dans les sources (après une copie des fichiers dans
   `sauvegardes/<date>/`) :

   | Fichier | Changement |
   |---|---|
   | `src/role.c` | l'entrée du rôle dans `roles[]` ; l'originale reste dans un `#if 0` ; avant `roles[]`, un commentaire donne le projet de chaque rôle intégré |
   | `src/u_init.c` | les tableaux d'inventaire (originaux en `#if 0`), et un bloc pour l'or et les intrinsèques après `u_init_race()` |
   | `src/insight.c` | quand des titres de rang changent : le titre au féminin dans `^X` et dans la liste des rangs atteints (appels d'origine en `#if 0`) |
   | `win/share/monsters.txt` | les tuiles du rôle (l'originale en commentaire dessous) |
   | `po/fr.po`, `po/themes/fr@cyber.po`, `po/nethack.pot` | les titres de rang (ancienne traduction gardée en commentaire `# nhheroedit:orig`) |

   Chaque changement est marqué `nhheroedit` et garde le texte
   d'origine : une nouvelle intégration repart des fichiers d'origine,
   et `R` les rend **à l'identique**. Si les sources sont un dépôt git,
   un commit des fichiers touchés est proposé.

   **Plusieurs projets.** Chaque intégration repart des fichiers
   d'origine : les rôles intégrés par un autre projet sont relus dans
   leur projet (noté dans `role.c`) et gardés, ou retirés si vous le
   choisissez. `R` propose de même de ne retirer que les rôles du projet
   ouvert. L'aperçu indique « intégré par le projet … ».

2. **`m` — compiler**, 3. **`U` — mettre à jour le jeu installé**
   (`make update` garde `sysconf`, scores et sauvegardes), 4. **`j` —
   jouer**. `m` et `U` recompilent avec les interfaces du dernier build
   (`WANT_WIN_TTY=1 WANT_WIN_CURSES=1…`, lues dans `dat/options`) : un
   simple `make` ne ferait qu'un jeu tty, sans curses ni les tuiles des
   versions X11 et Qt. Les options `make` de la configuration qui
   contiennent `WANT_…` sont prises telles quelles.

Les rôles ne changent pas la liste des monstres : les parties
sauvegardées restent lisibles (`EDITLEVEL` n'est pas touché).

**Titre au féminin.** Un rang sans titre féminin propre se traduit au
féminin par le contexte `feminine` des `.po`. La ligne d'état et les
textes de quête en tiennent compte, mais le jeu d'origine traduit le
titre masculin dans `^X` (« Vous êtes Gamin ») et dans la liste des
rangs atteints : l'intégration corrige ces deux appels dans
`src/insight.c` dès qu'un projet change des titres de rang.

## Fichiers

| Fichier | Rôle |
|---|---|
| `nhheroedit.py` | l'application (liste, fiche, inventaire, titres, actions) |
| `nhhero_ui.py` | fenêtres curses, menus, éditeur de texte et de tuile (repris de nhmonedit) |
| `nhhero_data.py` | lecture du C (`role.c`, `u_init.c`, `objects.h`) et des `.po`, combinaisons, calculs, vérifications |
| `nhhero_install.py` | lecture des sources d'origine, intégration et retrait |
| `nhhero_project.py` | projets, héros exportés (`.nhhero.json`), sauvegarde de secours |
| `nhhero_game.py` | lancement du jeu avec le héros |
| `nhhero_templates.py` | archétypes de Night City |
| `nhhero_config.py`, `nhhero_i18n.py`, `nhhero_i18n_en.py` | configuration, langue, traduction anglaise |
| `tests/` | tests (`python3 -m unittest discover -s tests`) |
| `heros.json` | le projet par défaut (créé au premier enregistrement) |

## Environnement de test

Développé sous Lubuntu 26.04 avec Python 3.14 et NetHack 5.0.0, branche
`cybernethack`. Testé : intégration puis retrait qui rend les six
fichiers à l'identique ; compilation complète du jeu avec une Valkyrie
modifiée (aucun avertissement) ; en partie : 300 eddies, épée large +2
bénie dans l'inventaire, « Vous êtes rapide », « Vous êtes télépathe »,
déesse Freyja, PV et énergie modifiés.
