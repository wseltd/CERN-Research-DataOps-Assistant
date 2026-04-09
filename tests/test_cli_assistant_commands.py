from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "src" / "cern_research_dataops_assistant.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("assistant_cli_under_test", MODULE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_assistant_seed_ask_eval_demo_cli_round_trip(
    tmp_path: Path,
    capsys,
) -> None:
    module = _load_module()
    seed_dir = tmp_path / "seed"
    questions_file = PROJECT_ROOT / "evaluations" / "cms_run2_nanoaod_eval_questions.json"

    seed_exit = module.main(["assistant", "seed", "--seed-dir", str(seed_dir)])
    seed_output = json.loads(capsys.readouterr().out)

    ask_exit = module.main(
        [
            "assistant",
            "ask",
            "--seed-dir",
            str(seed_dir),
            "How do I cite the collision and MC records?",
        ]
    )
    ask_output = json.loads(capsys.readouterr().out)

    eval_exit = module.main(
        [
            "assistant",
            "eval",
            "--seed-dir",
            str(seed_dir),
            "--questions-file",
            str(questions_file),
        ]
    )
    eval_output = json.loads(capsys.readouterr().out)

    demo_exit = module.main(["assistant", "demo", "--seed-dir", str(seed_dir)])
    demo_output = json.loads(capsys.readouterr().out)

    assert seed_exit == 0
    assert seed_output["seed_version"] == "cms-run2-nanoaod-mvp-v1"
    assert ask_exit == 0
    assert "answer" in ask_output
    assert "evidence" in ask_output
    assert eval_exit == 0
    assert eval_output["total_questions"] == 20
    assert demo_exit == 0
    assert demo_output["demo"]["dataset_recid"] == 30522
