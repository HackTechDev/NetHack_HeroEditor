"""Modèles de héros : un archétype de Night City par rôle du jeu, avec
une combinaison permise de race, de sexe et d'alignement, et une courte
biographie."""

import copy

import nhhero_data as D
from nhhero_i18n import _

# (rôle, race, sexe, alignement, nom, animal, nom de l'animal, fruit,
#  titre du modèle, biographie)
TEMPLATES = [
    ("VALKYRIE", "human", "female", "neutral", "Kestrel", "", "", "",
     _("Solo de rue"),
     _("Garde du corps devenue tueuse à gages, Kestrel loue ses réflexes "
       "câblés au plus offrant. Elle ne fait confiance qu'à sa lame.")),
    ("WIZARD", "elf", "male", "chaotic", "Glitch", "", "Bitmap", "",
     _("Netrunner"),
     _("Réplicant évadé d'un labo d'Arasaka, Glitch plonge dans le Net "
       "pour effacer ses propres plans de fabrication.")),
    ("ARCHEOLOGIST", "dwarf", "male", "lawful", "Rivet", "", "", "",
     _("Techie des tunnels"),
     _("Foreur des chantiers du métro abandonné, Rivet récupère et répare "
       "tout ce qui traîne sous Night City.")),
    ("HEALER", "gnome", "female", "neutral", "Doc Suture", "", "", "",
     _("Medtech de clinique clandestine"),
     _("Squatteuse des Bas-fonds, elle recoud les gangs rivaux sans poser "
       "de questions et sans faire crédit.")),
    ("ROGUE", "human", "male", "chaotic", "Silk", "", "", "",
     _("Fixer"),
     _("Intermédiaire de toutes les combines, Silk connaît un prix pour "
       "chaque secret de la ville.")),
    ("KNIGHT", "human", "female", "lawful", "Sergente Vasquez", "", "",
     "", _("Lawman"),
     _("Dernière flic honnête du district, avec sa moto-poney et son "
       "badge cabossé.")),
    ("BARBARIAN", "orc", "male", "chaotic", "Krank", "", "", "",
     _("Nomade des Badlands"),
     _("Ancien employé corporatiste rejeté par le système, Krank roule "
       "avec les clans du désert.")),
    ("SAMURAI", "human", "male", "lawful", "Kenji", "", "Hachi-9",
     "", _("Ronin urbain"),
     _("Sans maître depuis la chute de sa corpo, Kenji garde son code "
       "d'honneur et son chien-robot.")),
    ("TOURIST", "human", "female", "neutral", "Lumi", "", "", "",
     _("Influenceuse"),
     _("Douze millions d'abonnés, une caméra et aucune idée du danger : "
       "Lumi diffuse tout en direct.")),
    ("RANGER", "elf", "female", "chaotic", "Vesper", "", "", "",
     _("Traqueuse de primes"),
     _("Réplicante chasseuse de réplicants, Vesper ne rate jamais une "
       "cible deux fois.")),
    ("CLERIC", "human", "male", "neutral", "Octet", "", "", "",
     _("Technoprêtre"),
     _("Prêcheur de l'Église de la Machine, il bénit les implants au nom "
       "du Grand Algorithme.")),
    ("MONK", "human", "female", "neutral", "Kai", "", "", "",
     _("Moniale augmentée"),
     _("Ses poings sont ses seuls implants : Kai a refusé tout le reste.")),
    ("CAVE_DWELLER", "dwarf", "male", "lawful", "Gravats", "", "", "",
     _("Zonard des décharges"),
     _("Né dans les décharges de la zone, Gravats se bat avec ce qu'il "
       "ramasse.")),
]


def template_list():
    """[(titre, description)] pour le menu « n »."""
    return [(t[8], t[4]) for t in TEMPLATES] + \
        [(_("Héros vierge"), _("à régler soi-même"))]


def from_template(i):
    """Héros du modèle i (le dernier : héros vierge)."""
    h = D.new_hero()
    if i >= len(TEMPLATES):
        return h
    (role, race, gender, align, name, pet, petname, fruit, _title,
     story) = TEMPLATES[i]
    h.update({"role": role, "race": race, "gender": gender,
              "align": align, "name": name, "pet": pet,
              "petname": petname, "fruit": fruit, "story": story})
    return copy.deepcopy(h)
