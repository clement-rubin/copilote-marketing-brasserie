"""Configuration : chemins du projet et variables d'environnement (.env)."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Racine du dépôt (le dossier qui contient src/)
ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = ROOT / "data"
BRAND_DIR = DATA_DIR / "brand"
FEEDS_FILE = DATA_DIR / "feeds.yaml"
PROMPTS_DIR = ROOT / "prompts"
OUT_DIR = ROOT / "out"
CHROMA_DIR = ROOT / "chroma_db"

# Charge le fichier .env s'il existe. Les variables déjà définies dans le shell restent prioritaires.
load_dotenv(ROOT / ".env")

# Windows sans mode développeur : Hugging Face ne peut pas créer de liens symboliques.
# Le cache fonctionne quand même, on masque juste l'avertissement.
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
# Moins de bruit dans la console : pas de barres de progression ni d'avertissements HF.
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("HF_HUB_VERBOSITY", "error")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")


def env(name: str, default: str = "") -> str:
    """Lit une variable d'environnement et enlève les espaces autour."""
    return os.getenv(name, default).strip()


# Les chemins de sortie sont des fonctions (et non des constantes) pour être lus au moment de
# l'appel : les tests peuvent ainsi rediriger OUT_DIR vers un dossier temporaire.
def watch_file() -> Path:
    """Fichier JSON des articles de veille."""
    return OUT_DIR / "watch" / "articles.json"


def posts_dir() -> Path:
    """Dossier des posts générés (un fichier JSON par post)."""
    return OUT_DIR / "posts"


def scheduled_dir() -> Path:
    """Dossier où le MockPublisher écrit les posts programmés."""
    return OUT_DIR / "scheduled"
