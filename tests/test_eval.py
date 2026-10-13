"""La mini-évaluation doit passer à 10/10 en mode démo, et les détecteurs doivent réagir."""

from tests.eval import N_CASES, detector_controls, run_eval


def test_eval_demo_mode_all_cases_pass(isolated):
    results = run_eval()
    assert len(results) == N_CASES
    failed = [r for r in results if not r.passed]
    assert not failed, failed


def test_detectors_flag_faulty_posts():
    for name, warnings in detector_controls():
        assert warnings, name
