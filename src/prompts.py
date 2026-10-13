"""Chargement des prompts depuis prompts/*.md.

Conventions des fichiers de prompt :
- les commentaires <!-- ... --> servent à documenter le prompt et ne sont PAS envoyés au LLM ;
- les variables s'écrivent {{nom}} et sont remplacées par `render()`.
On n'utilise pas str.format() car les prompts contiennent des accolades JSON.
"""

import re

from src.config import PROMPTS_DIR

COMMENT = re.compile(r"<!--.*?-->\s*", flags=re.DOTALL)
VARIABLE = re.compile(r"\{\{(\w+)\}\}")


def load(name: str) -> str:
    """Lit prompts/<name>.md sans les commentaires."""
    text = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    return COMMENT.sub("", text).strip()


def render(name: str, **variables: str) -> str:
    """Charge un prompt et remplace les {{variables}}. Une variable manquante est une erreur."""
    text = load(name)
    missing = set(VARIABLE.findall(text)) - variables.keys()
    if missing:
        raise KeyError(f"Variables manquantes pour le prompt {name!r} : {sorted(missing)}")
    return VARIABLE.sub(lambda m: str(variables[m.group(1)]), text)
