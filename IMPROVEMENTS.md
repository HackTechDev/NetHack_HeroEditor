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
| 1. Limites connues | 4 / 6 | 1.5 et 1.6 |
| 2. Vérification | 0 / 6 | tout |
| 3. Héros et parties | 0 / 7 | tout |
| 4. Rôles : nouvelles règles | 0 / 9 | tout |
| 5. Tuiles | 0 / 4 | tout |
| 6. Projets et fichiers | 0 / 3 | tout |
| 7. Liens avec les autres outils | 0 / 3 | tout |
| 8. Qualité du projet | 0 / 5 | tout |

Prochaines étapes conseillées : le **titre féminin** de la ligne d'état
(1.1), puis l'**historique des parties** du héros (3.1) et les
**compétences** du rôle (4.1). Ensemble, elles rendent le héros
« vivant » et complètent l'inventaire de départ.

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
5. **Traductions sur plusieurs lignes** **[facile]**. Le remplacement
   d'une traduction dans les `.po` ne gère que les `msgstr` d'une seule
   ligne ; les titres de rang le sont tous aujourd'hui, mais un titre
   long (ou un futur champ) ferait une entrée en double, refusée par
   `msgfmt`. Gérer les lignes de suite `"…"`.
6. **Mode wizard sous le nom « wizard »** **[facile]**. En `-D`, le jeu
   remplace le nom du héros par « wizard » : la partie d'essai n'est
   pas tout à fait celle du héros. Expliquer comment ajouter le nom à
   `WIZARDS` dans `sysconf`, ou passer `-u` quand c'est permis.

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

1. **Historique des parties du héros** **[moyen]**. Lire le `xlogfile`
   du jeu (comme le lanceur) et montrer dans l'aperçu les parties
   jouées sous ce nom : nombre, meilleur score, niveau atteint, cause
   des morts, conduites tenues.
2. **Jeu à côté de l'éditeur** **[facile]**. Comme `j` dans nhmonedit,
   ouvrir NetHack dans un panneau tmux plutôt qu'en plein écran, pour
   garder la fiche sous les yeux.
3. **Partie sauvegardée** **[facile]**. Quand une sauvegarde du héros
   existe, proposer de la reprendre, de la mettre de côté ou de la
   supprimer, au lieu d'un simple avertissement.
4. **Héros au hasard** **[facile]**. Tirer une combinaison permise, un
   nom et un animal ; avec un générateur de noms de Night City
   (pseudos de rue, noms corporatistes) aussi utile pour `n`.
5. **Profil d'affichage par héros** **[moyen]**. Options d'interface
   propres au héros : `menucolors`, `statushilites`, `autopickup`,
   symboles, interface (tty, curses). Écrites dans son `.nethackrc` et
   passées par `j`.
6. **Fichier d'options complet** **[facile]**. `x` n'écrit que les
   options du héros ; proposer aussi un fichier complet (le
   `~/.nethackrc` actuel suivi des options du héros), utilisable tel
   quel avec `NETHACKOPTIONS=@fichier`.
7. **Biographie dans le jeu** **[gros]**. Montrer la biographie au début
   de la partie, à la place ou à la suite du texte d'introduction
   (`legacy`), ce qui demande une modification du jeu.

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

1. **Les deux sexes côte à côte** **[facile]**. Voir et copier la tuile
   mâle vers la femelle (ou l'inverse) dans l'éditeur de pixels.
2. **Calques Night City** **[moyen]**. Éléments à poser sur une tuile :
   visière, implants, bras mécanique, manteau long, arme.
3. **Export en image** **[facile]**. Écrire la tuile en PNG ou en SVG
   (agrandie), pour la partager ou l'utiliser hors du jeu.
4. **Aperçu en couleurs réelles** **[facile]**. Dans un terminal à
   256 couleurs, l'aperçu en demi-blocs est approché : proposer les
   couleurs vraies (24 bits) quand le terminal les accepte.

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

1. **Héros dans le lanceur** **[moyen]**. Lister les héros du projet
   dans le lanceur et jouer l'un d'eux directement (« Jack-in :
   Kestrel »), avec son historique.
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
