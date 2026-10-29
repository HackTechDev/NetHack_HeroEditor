# Améliorations possibles

Idées d'évolution pour nhheroedit, classées par thème. Chaque thème
commence par les améliorations les plus utiles, et chaque idée est
marquée selon l'effort qu'elle demande :
**[facile]** quelques heures, **[moyen]** une journée environ,
**[gros]** plusieurs jours.

Les idées réalisées seront marquées « ✅ **Fait** » ; la liste complète
de ce que fait l'éditeur aujourd'hui est dans [FEATURES.md](FEATURES.md).

## État d'avancement (2026-10-29)

| Thème | Fait | Reste |
|---|---|---|
| 1. Limites connues | 6 / 6 | — |
| 2. Vérification | 0 / 6 | tout |
| 3. Héros et parties | 7 / 7 | — |
| 4. Rôles : nouvelles règles | 0 / 9 | tout |
| 5. Tuiles | 4 / 4 | — |
| 6. Projets et fichiers | 0 / 3 | tout |
| 7. Liens avec les autres outils | 1 / 3 | 7.2, 7.3 |
| 8. Qualité du projet | 0 / 5 | tout |

Prochaine étape conseillée : les **compétences** du rôle (4.1), qui
complètent l'inventaire de départ.

## 1. Limites connues

Ce que l'éditeur fait mal ou ne vérifie pas aujourd'hui.

1. **Titre féminin absent de `^X`** **[facile]** — ✅ **Fait**. Quand
   un rang n'a pas de titre féminin propre, `^X` (« Vous êtes Gamin »)
   et la liste des rangs atteints traduisaient la forme masculine ; la
   ligne d'état et les textes de quête passent déjà par
   `gendered_word()`. L'intégration corrige ces deux appels de
   `src/insight.c` (marqués `nhheroedit`, retirés par `R`) dès que des
   titres de rang changent. Vérifié en jeu : « Vous êtes Gamine ».
2. **Titres anglais déjà employés ailleurs** **[facile]** — ✅ **Fait**.
   Un titre anglais tapé à la main (« Novice », « Rambler ») peut être
   un `msgid` que le jeu utilise déjà : changer sa traduction dans
   `fr.po` change aussi l'autre texte. L'éditeur cherche les emplois du
   titre dans les références de `nethack.pot` (hors de l'entrée du rôle)
   et avertit dans l'aperçu, la vérification `v` et à la saisie ; il
   signale aussi un même titre traduit différemment par deux rôles du
   projet.
3. **Tuiles des versions graphiques non régénérées** **[facile]** —
   ✅ **Fait**. `m` lançait un simple `make`, qui ne refait qu'un jeu
   tty : sans curses, X11 ni Qt, et sans `x11tiles` ni `nhtiles.bmp`
   (`U` l'aurait installé). `m` et `U` reprennent maintenant les
   interfaces du dernier build, lues dans `dat/options` (ou d'après les
   fichiers objets), et l'intégration prévient quand des tuiles changent
   alors que ni X11 ni Qt ne sont compilés.
4. **Un seul projet par jeu** **[moyen]** — ✅ **Fait**. Une
   intégration remplaçait toutes les modifications faites avant, même
   par un autre projet. Le projet de chaque rôle intégré est maintenant
   noté dans `role.c` (commentaire marqué, retiré avec le reste) : `I`
   garde les rôles des autres projets (relus dans leur fichier, dans
   leur état actuel) ou les retire au choix, `R` peut ne retirer que
   ceux du projet ouvert, et l'aperçu dit « intégré par le projet … ».
   Un rôle intégré par une version précédente de l'éditeur n'a pas de
   projet connu : il est signalé et retiré.
5. **Traductions sur plusieurs lignes** **[facile]** — ✅ **Fait**. Le
   remplacement d'une traduction dans les `.po` ne gérait que les
   `msgstr` d'une seule ligne : une traduction coupée en lignes de suite
   `"…"` aurait donné une entrée en double, refusée par `msgfmt`. Elle
   est maintenant remplacée, et son texte d'origine gardé ligne à ligne
   (`# nhheroedit:orig` puis `# nhheroedit:orig+`) pour le retrait. Le
   `msgid` reste attendu sur une ligne (`xgettext` ne coupe que les
   textes longs, pas les titres de rang).
6. **Mode wizard sous le nom « wizard »** **[facile]** — ✅ **Fait**. En
   `-D`, le jeu remplace toujours le nom du héros par « wizard »
   (`set_playmode()`, `src/options.c`) : ni `sysconf` ni `-u` n'y
   changent rien, et c'est voulu, puisque la partie wizard est ainsi
   sauvegardée à part de la vraie. L'éditeur l'explique avant de lancer
   le jeu, prévient quand une partie « wizard » sauvegardée sera reprise
   à la place du héros, et quand `WIZARDS` ou `EXPLORERS` de `sysconf`
   ne permettent pas le mode choisi (le jeu passerait en découverte ou
   en partie normale).

## 2. Vérification

1. **Armes que le rôle ne sait pas manier** **[moyen]**. Lire les
   tables `Skill_X` de `u_init.c` et avertir quand l'inventaire donne
   une arme d'une compétence interdite au rôle (une Netrunneuse avec une
   épée à deux mains).
2. **Objets que le jeu remplace au départ** **[facile]**.
   `ini_inv_mkobj_filter()` refuse certains objets tirés au hasard
   (baguette de souhait, anneau de polymorphie, livres trop difficiles…)
   et `inv_subs[]` change certains objets selon la race (dague →
   dague elfique). Le montrer dans l'aperçu : « pour un réplicant :
   dague de réplicant ».
3. **Livres de sorts trop difficiles** **[facile]**. Signaler un livre
   de niveau élevé ou d'une école restreinte pour le rôle
   (`restricted_spell_discipline()`), que le héros ne pourra pas lire.
4. **Poids de l'inventaire** **[moyen]**. Additionner les poids lus
   dans `objects.h` et comparer à la capacité de départ (force et
   constitution) : avertir quand le héros commence chargé.
5. **Équilibrage** **[moyen]**. Une note de « puissance de départ »
   (attributs, PV, armure, dégâts de l'arme, intrinsèques) comparée aux
   13 rôles du jeu, comme la touche `b` de nhmonedit pour les monstres.
6. **Vérification en jeu automatique** **[moyen]**. Lancer le jeu dans
   tmux en mode découverte, lire l'inventaire (`i`) et les attributs
   (`^X`), et comparer à ce que l'éditeur attend : c'est ce qui a été
   fait à la main pour tester la première version.

## 3. Héros et parties

1. **Historique des parties du héros** **[moyen]** — ✅ **Fait**. `h`
   lit le `xlogfile` du jeu (comme le lanceur) : parties terminées sous
   le nom du héros, avec date, score, niveau, fin traduite par les
   catalogues du jeu, tours, profondeur et conduites tenues. L'aperçu
   montre le nombre de parties et le record.
2. **Jeu à côté de l'éditeur** **[facile]** — ✅ **Fait**. Dans tmux,
   `j` ouvre NetHack dans un panneau à droite (fenêtre d'au moins 170
   colonnes) ou dans une fenêtre tmux à part ; la fiche reste sous les
   yeux. `tmux = non` dans la configuration garde le plein écran.
3. **Partie sauvegardée** **[facile]** — ✅ **Fait**. Quand une
   sauvegarde du héros existe, `j` propose de la reprendre, de la mettre
   de côté (dans `parties/` de l'éditeur) ou de la supprimer ; sans
   sauvegarde, il propose de remettre une partie mise de côté. La
   sauvegarde est cherchée sous son nom exact (`Kestrel` ne prend plus
   celle de `Kestrel2`).
4. **Héros au hasard** **[facile]** — ✅ **Fait**. « Héros au hasard »
   dans le menu de `n` tire un rôle, une combinaison permise (rôles
   modifiés compris), un nom, un animal et une biographie composée ; `N`
   donne un nom de Night City au hasard (pseudo de rue, surnom, nom
   corporatiste) au héros choisi.
5. **Profil d'affichage par héros** **[moyen]** — ✅ **Fait**. Section
   « ▸ Affichage » de la fiche : interface (interfaces du jeu compilé,
   `-w` pour `j`), symboles (lus dans le fichier `symbols` du jeu),
   ramassage automatique, couleurs Night City (`hilite_status`,
   `menucolors`, `MENUCOLOR`). Écrit dans le `.nethackrc` du héros et
   passé par `j`. Vérifié en jeu.
6. **Fichier d'options complet** **[facile]** — ✅ **Fait**. `x` écrit au
   choix les options du héros ou un fichier complet : votre
   configuration (`~/.nethackrc` ou le fichier de `NETHACKOPTIONS`),
   puis le héros, `windowtype` en tête, les options redéfinies mises en
   commentaire (le jeu refuse une option donnée deux fois). `j` s'en
   sert aussi : les règles `MENUCOLOR` passent, et un `NETHACKOPTIONS`
   qui désigne un fichier n'empêche plus de transmettre les options.
7. **Biographie dans le jeu** **[gros]** — ✅ **Fait**. L'intégration
   ajoute à `newgame()` (`src/allmain.c`, bloc marqué `nhheroedit`)
   l'affichage du texte de `NHHEROEDIT_STORY` juste après le texte
   d'introduction ; `j` y met le nom et la biographie du héros, coupée
   à 76 colonnes. Rien ne change pour une partie lancée sans l'éditeur.
   Vérifié en jeu.

## 4. Rôles : nouvelles règles

1. **Compétences** **[moyen]**. Éditer les tables `Skill_X` de
   `u_init.c` : niveau maximal de chaque compétence d'arme et de magie,
   avec le même mécanisme réversible que les inventaires.
2. **Intrinsèques par niveau** **[moyen]**. Les tables `role_abil` et
   `race_abil` de `attrib.c` donnent des capacités en montant de niveau
   (rapidité au niveau 7 pour un Moine…) : les rendre éditables.
3. **Magie du rôle** **[facile]**. Les derniers champs de `roles[]` :
   sort de prédilection, attribut de lancement, pénalités de base, de
   soin, de bouclier et d'armure métallique.
4. **Animal imposé** **[facile]**. Le champ `petnum` (chaton du
   Netrunner, chien du Ronin, poney du Lawman), à choisir parmi les
   animaux possibles.
5. **Objets connus au départ** **[moyen]**. Les appels `knows_object()`
   et `knows_class()` de `u_init_role()` : objets identifiés dès le
   début.
6. **Objets de départ tirés au hasard** **[moyen]**. Les ajouts
   aléatoires de `u_init_role()` (lampe, marqueur magique, bandeau…)
   avec leur probabilité.
7. **Noms du rôle** **[facile]**. Changer le nom français et Night City
   du rôle lui-même (« Solo »), comme les titres de rang.
8. **Races modifiées** **[moyen]**. Même principe pour `races[]` :
   attributs minimum et maximum, PV et énergie, alignements permis,
   noms dans le thème.
9. **Nouveau rôle** **[gros]**. Créer une profession entière (entrée de
   `roles[]`, monstre `PM_`, inventaire, compétences, quête, artefact,
   textes) : la suite logique, mais un très gros chantier.

## 5. Tuiles

1. **Les deux sexes côte à côte** **[facile]** — ✅ **Fait**. L'éditeur
   de pixels montre sous l'aperçu la tuile de l'autre sexe, et `c` la
   recopie dans la tuile en cours (mâle vers femelle ou l'inverse).
2. **Calques Night City** **[moyen]** — ✅ **Fait**. `l` dans l'éditeur
   de pixels : visière, implants, bras mécanique, manteau long, arme
   (`LAYERS` dans `nhhero_data.py`, espace = transparent), à déplacer
   avec les flèches avant de les poser.
3. **Export en image** **[facile]** — ✅ **Fait**. `e` dans l'éditeur de
   pixels écrit la tuile agrandie huit fois en PNG (écrit sans
   bibliothèque, `tile_png`) ou en SVG (`tile_svg`).
4. **Aperçu en couleurs réelles** **[facile]** — ✅ **Fait**. Avec
   `COLORTERM=truecolor` (ou `couleurs = 24bits` dans la
   configuration), curses démarre avec le terminfo `-direct` du terminal
   et les tuiles ont leurs couleurs exactes ; le jeu garde son `TERM`.
   Vérifié dans tmux (`48;2;71;108;108`).

## 6. Projets et fichiers

1. **Modèles personnels** **[facile]**. Comme dans nhmonedit :
   enregistrer un héros (avec les changements de son rôle) comme modèle,
   proposé ensuite par `n`.
2. **Conflits à la fusion** **[moyen]**. Quand deux projets modifient
   le même rôle, montrer les différences et laisser choisir champ par
   champ, au lieu de garder celui du projet ouvert.
3. **Comparaison avec le jeu** **[facile]**. Fiche du rôle modifié à
   côté du rôle d'origine, différences en couleur (comme `B` dans
   nhmonedit).

## 7. Liens avec les autres outils

1. **Héros dans le lanceur** **[moyen]** — ✅ **Fait**. Avec
   `heros = oui` dans sa section, le lanceur ajoute sous l'éditeur une
   ligne « ↳ Jack-in : Kestrel » par héros (`nhheroedit --heros` :
   rôle, race, parties, record, dernière fin, partie en pause), qui
   lance le jeu par `nhheroedit --jouer Kestrel`.
2. **Robots compagnons** **[moyen]**. Choisir comme animal de départ un
   robot créé avec nhmonedit (champ `petnum`, voir 4.4).
3. **Quête du rôle** **[gros]**. Ouvrir dans l'éditeur de cartes les
   niveaux de quête du rôle (`dat/Val-*.lua`…) pour les adapter au rôle
   modifié.

## 8. Qualité du projet

1. **Code commun avec nhmonedit** **[moyen]**. `nhhero_ui.py`,
   `nhhero_config.py` et `nhhero_i18n.py` sont des copies adaptées de
   nhmonedit : une bibliothèque partagée éviterait de corriger deux
   fois le même défaut.
2. **Tutoriel et capture d'écran** **[facile]**. Un `TUTORIAL.md` qui
   crée un héros de A à Z, et une capture dans le README, comme pour
   nhmonedit.
3. **Tests de l'interface** **[moyen]**. Piloter l'éditeur dans un
   terminal simulé (tmux) : création d'un héros, inventaire, tuile,
   intégration.
4. **Test de compilation complet** **[moyen]**. Un test facultatif qui
   copie les sources, intègre un rôle modifié et lance `make` en entier
   (aujourd'hui seuls `role.c` et `u_init.c` sont compilés par les
   tests).
5. **Licence et style** **[facile]**. Ajouter un fichier `LICENSE` ; une
   dizaine de lignes dépassent 79 colonnes.
