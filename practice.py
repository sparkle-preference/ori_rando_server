"""The default practice segments: every .bfrp in practice_defaults/, fetched by clients that lack them."""
import os

DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "practice_defaults")
EXT = ".bfrp"


def defaults():
    """Their names, without the extension."""
    if not os.path.isdir(DIR):
        return []
    return sorted(f[:-len(EXT)] for f in os.listdir(DIR) if f.endswith(EXT))


def default_path(file):
    """The path of practice_defaults/<file>, or None for a name the listing doesn't hold."""
    if file.endswith(EXT) and file[:-len(EXT)] in defaults():
        return os.path.join(DIR, file)
    return None
