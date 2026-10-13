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


def env(name: str, default: str = "") -> str:
    """Lit une variable d'environnement et enlève les espaces autour."""
    return os.getenv(name, default).strip()
