"""
Shared thumbnail template/style choices.

Lives in its own module so that both the thumbnail generator
(``plugins/thumbnails.py``) and the settings system
(``plugins/user_settings.py``) can use it without a circular import.
"""

# Magic templates (keys match thumbnail_generator._MAGIC_TEMPLATES)
MAGIC_CHOICES = [
    ("1", "1 · Classic"), ("2", "2 · Netflix"), ("3", "3 · Disney"),
    ("4", "4 · HBO"), ("5", "5 · Prime"), ("6", "6 · Apple"),
    ("7", "7 · Cyberpunk"), ("8", "8 · Bollywood"), ("9", "9 · Anime"),
    ("10", "10 · Mono"), ("11", "11 · Hotstar"), ("12", "12 · Crunchyroll"),
    ("13", "13 · Peacock"), ("14", "14 · Paramount"), ("15", "15 · Horror"),
    ("16", "16 · K-Drama"), ("17", "17 · Vintage"), ("18", "18 · Adult"),
    ("19", "19 · Adult Purple"), ("20", "20 · Adult Gold"),
]

# Premiere styles (keys match thumbnail_generator._PREMIERE_STYLES)
PREMIERE_CHOICES = [
    ("1", "1 · Classic"), ("2", "2 · Netflix"), ("3", "3 · Gold"),
    ("4", "4 · Neon"), ("5", "5 · Minimal"), ("6", "6 · Anime"),
    ("7", "7 · Horror"), ("8", "8 · K-Drama"), ("9", "9 · Adult"),
    ("10", "10 · Adult Purple"), ("11", "11 · Adult Gold"), ("12", "12 · Vintage"),
]
