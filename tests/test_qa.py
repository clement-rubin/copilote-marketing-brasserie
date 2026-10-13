"""Tests de la base de connaissances interrogeable (commande `ask`)."""

import json

from src.llm import FakeLLMClient, get_llm_client
from src.qa import ask


def test_demo_answer_is_sourced(isolated):
    answer = ask(get_llm_client("fake"), "Quel est le degré d'alcool de la Saison Démo ?")
    assert "5,8" in answer.reponse
    assert "05_fiche_saison_demo.md" in answer.sources_utilisees
    assert not any("non sourcé" in w for w in answer.avertissements)


def test_invented_number_in_answer_is_flagged(isolated):
    fake = FakeLLMClient([json.dumps({"reponse": "La Saison titre 9,1 %.", "sources_utilisees": ["05_fiche_saison_demo.md"]})])
    answer = ask(fake, "Quel est le degré de la Saison ?")
    assert any("9,1" in w for w in answer.avertissements)


def test_prompt_forbids_answering_outside_documents(isolated):
    fake = FakeLLMClient([json.dumps({"reponse": "Je ne trouve pas cette information dans la documentation."})])
    ask(fake, "Quel est le prix d'un fût ?")
    _, user = fake.calls[0]
    assert "uniquement à partir des passages" in user
