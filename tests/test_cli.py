import pytest

from pve_osx.cli import PveOsx, run


def test_help_exits_zero(capsys):
    with pytest.raises(SystemExit) as exc:
        run(["--help"])
    assert exc.value.code == 0
    assert "pve-osx" in capsys.readouterr().out


def test_version_matches_package():
    """`__version__` must agree with the version the build backend recorded --
    pinning a literal here just meant the test had to be edited on every bump,
    which is exactly when a drifted `__version__` would go unnoticed."""
    from importlib.metadata import version

    from pve_osx import __version__

    assert PveOsx._version_ is not None
    assert __version__ == version("pve-osx")
