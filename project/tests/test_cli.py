from vellric.cli import main


def test_help(capsys):
    assert main([]) == 0
    assert "fidelity conversion" in capsys.readouterr().out
