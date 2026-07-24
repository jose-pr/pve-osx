import pytest

from pve_osx.cli import PveOsx, run


def test_help_exits_zero(capsys):
    with pytest.raises(SystemExit) as exc:
        run(["--help"])
    assert exc.value.code == 0
    assert "pve-osx" in capsys.readouterr().out


def test_version_matches_package():
    from pve_osx import __version__

    assert PveOsx._version_ is not None
    assert __version__ == "0.1.0"
