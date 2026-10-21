"""The connection options every Proxmox-talking command shares: flag, then
environment variable, and what reaches the client."""

import pytest

from pve_osx.cli import run

NAMES = (
    "PVE_HOST",
    "PVE_NODE",
    "PVE_TOKEN_ID",
    "PVE_TOKEN_SECRET",
    "PVE_SSH_HOST",
    "PVE_VERIFY_SSL",
)


class FakeClient:
    made = []

    def __init__(self, host, node, token_id, token_secret, verify_ssl=True):
        self.args = (host, node, token_id, token_secret, verify_ssl)
        FakeClient.made.append(self.args)

    def list_vms(self):
        return []


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    for name in NAMES:
        monkeypatch.delenv(name, raising=False)
    FakeClient.made = []
    monkeypatch.setattr("pve_osx.pve.PveClient", FakeClient)


def _list(*argv):
    return run(["vm", "list", *argv])


def test_the_environment_supplies_the_connection(monkeypatch):
    monkeypatch.setenv("PVE_HOST", "h.example")
    monkeypatch.setenv("PVE_NODE", "n1")
    monkeypatch.setenv("PVE_TOKEN_ID", "u@pam!t")
    monkeypatch.setenv("PVE_TOKEN_SECRET", "s")

    assert _list() == 0
    assert FakeClient.made == [("h.example", "n1", "u@pam!t", "s", False)]


def test_a_flag_beats_the_environment(monkeypatch):
    monkeypatch.setenv("PVE_HOST", "env.example")
    monkeypatch.setenv("PVE_TOKEN_ID", "env")
    monkeypatch.setenv("PVE_TOKEN_SECRET", "env")

    assert _list("--host", "flag.example", "--token-id", "flag") == 0
    assert FakeClient.made == [("flag.example", None, "flag", "env", False)]


def test_no_host_is_one_line_and_status_1(capsys):
    assert _list("--token-id", "a", "--token-secret", "b") == 1
    assert capsys.readouterr().err.startswith("pve-osx: no Proxmox host given")


def test_no_token_is_one_line_and_status_1(capsys, monkeypatch):
    monkeypatch.setenv("PVE_HOST", "h")
    monkeypatch.setenv("PVE_TOKEN_ID", "a")

    assert _list() == 1
    assert capsys.readouterr().err.startswith("pve-osx: no API token given")


def test_the_ssh_host_is_the_variable_then_the_host(monkeypatch):
    from pve_osx.cli import PveOsx
    from pve_osx.common import PveConnectionArgs

    seen = []

    class FakeSsh:
        def __init__(self, host):
            seen.append(host)

    monkeypatch.setattr("pve_osx.ssh.SshClient", FakeSsh)

    class Probe(PveConnectionArgs):
        def __call__(self):
            self.ssh()
            return 0

    root = type(
        "Root", (PveOsx,), {"_subcommands_": [Probe], "_parsername_": "pve-osx"}
    )
    import duho

    monkeypatch.setenv("PVE_HOST", "api.example")
    assert duho.run(root, ["probe"], exit=False) == 0
    monkeypatch.setenv("PVE_SSH_HOST", "ssh.example")
    assert duho.run(root, ["probe"], exit=False) == 0
    assert duho.run(root, ["probe", "--ssh-host", "flag.example"], exit=False) == 0
    assert seen == ["api.example", "ssh.example", "flag.example"]


def test_help_never_shows_a_secret(monkeypatch, capsys):
    monkeypatch.setenv("PVE_TOKEN_SECRET", "hunter2-secret")
    monkeypatch.setenv("PVE_TOKEN_ID", "hunter2-id")

    with pytest.raises(SystemExit):
        _list("--help")
    out = capsys.readouterr().out
    assert "--token-secret" in out
    assert "hunter2" not in out


def test_only_the_connection_options_read_pve_variables(monkeypatch):
    """`vm create` has options named like variables a user may have set for
    something else (`PVE_NAME`, `PVE_VMID`): they are not read."""
    import os

    read = set()

    class Recording(dict):
        def get(self, key, default=None):
            read.add(key)
            return super().get(key, default)

        def __getitem__(self, key):
            read.add(key)
            return super().__getitem__(key)

        def __contains__(self, key):
            read.add(key)
            return super().__contains__(key)

    monkeypatch.setattr(os, "environ", Recording(os.environ))
    with pytest.raises(SystemExit):
        run(["vm", "create", "--help"])

    assert {name for name in read if name.startswith("PVE_")} == {
        "PVE_HOST",
        "PVE_NODE",
        "PVE_TOKEN_ID",
        "PVE_TOKEN_SECRET",
        "PVE_SSH_HOST",
    }


@pytest.mark.parametrize(
    ("text", "verified"),
    [("true", True), ("1", True), ("yes", True), ("TRUE", True), ("on", True)]
    + [("false", False), ("0", False), ("no", False), ("", False)],
)
def test_pve_verify_ssl_is_a_boolean(monkeypatch, text, verified):
    monkeypatch.setenv("PVE_VERIFY_SSL", text)

    assert _list("--host", "h", "--token-id", "a", "--token-secret", "b") == 0
    assert FakeClient.made[-1][4] is verified


def test_certificates_are_not_verified_unless_asked_for():
    assert _list("--host", "h", "--token-id", "a", "--token-secret", "b") == 0
    assert FakeClient.made[-1][4] is False


def test_insecure_beats_a_variable_that_asks_for_verification(monkeypatch):
    monkeypatch.setenv("PVE_VERIFY_SSL", "true")

    argv = ["--host", "h", "--token-id", "a", "--token-secret", "b"]
    assert _list(*argv, "--insecure") == 0
    assert FakeClient.made[-1][4] is False


def test_text_that_is_not_a_boolean_ends_the_command(monkeypatch, capsys):
    monkeypatch.setenv("PVE_VERIFY_SSL", "sometimes")

    assert _list("--host", "h", "--token-id", "a", "--token-secret", "b") == 1
    assert capsys.readouterr().err == (
        "pve-osx: $PVE_VERIFY_SSL is 'sometimes', not a boolean (true or false)\n"
    )
    assert FakeClient.made == []
