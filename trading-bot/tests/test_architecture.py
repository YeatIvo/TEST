"""Phase A: prüft, dass die Architektur steht und die Sicherheitsregeln greifen."""
from pathlib import Path

from src import fingerprint, settings

ROOT = settings.ROOT


def test_folders_exist():
    for name, path in settings.DIRS.items():
        assert path.is_dir(), f"Ordner fehlt: {name}"


def test_settings_consistent():
    s = settings.load()
    u = s["universe"]
    assert len(u["study_tickers"]) == 24
    assert len(settings.tradable_tickers()) == 22
    for t in u["engine_candidates"] + u["safe_candidates"]:
        assert t in u["study_tickers"]
    assert s["broker"]["paper_only"] is True
    tr_s, tr_e = settings.window("train")
    lk_s, _ = settings.window("lock")
    assert tr_s < tr_e < lk_s, "Lock-Fenster muss nach dem Training liegen"


def test_env_never_tracked():
    gi = (ROOT / ".gitignore").read_text()
    assert ".env" in gi.splitlines()
    example = (ROOT / ".env.example").read_text()
    # Vorlage darf keine Werte enthalten
    for ln in example.splitlines():
        if ln.startswith(("ALPACA_API_KEY", "ALPACA_SECRET_KEY", "TELEGRAM_BOT_TOKEN")):
            assert ln.rstrip().endswith("="), f"Wert in .env.example: {ln.split('=')[0]}"


def test_agents_matches_claude():
    assert (ROOT / "AGENTS.md").read_text() == (ROOT / "CLAUDE.md").read_text()


def test_fingerprint_stable():
    assert fingerprint.line() == fingerprint.line()
    assert fingerprint.line().startswith("FINGERPRINT A")
