import pytest

from burstwise import cli


def test_help_lists_the_commands(capsys):
    with pytest.raises(SystemExit):
        cli.main(["--help"])
    out = capsys.readouterr().out
    for word in ("cull", "serve", "undo", "models"):
        assert word in out


def test_version(capsys):
    with pytest.raises(SystemExit):
        cli.main(["--version"])
    assert capsys.readouterr().out.startswith("burstwise 0.")


def test_cull_options_become_settings():
    args = cli.build_parser().parse_args(["cull", "photos", "--similarity", "0.9", "--cpu"])
    assert cli._settings(args).similarity == 0.9 and args.cpu


def test_undo_with_nothing_to_undo(tmp_path, capsys):
    assert cli.main(["undo", str(tmp_path)]) == 0
    assert "nothing to undo" in capsys.readouterr().out


def test_empty_folder_exits_with_a_message(tmp_path):
    with pytest.raises(SystemExit, match="no supported photos"):
        cli.main(["cull", str(tmp_path), "--cpu"])


def test_missing_folder_exits_with_a_message(tmp_path):
    with pytest.raises(SystemExit, match="is not a folder"):
        cli.main(["cull", str(tmp_path / "nope")])
