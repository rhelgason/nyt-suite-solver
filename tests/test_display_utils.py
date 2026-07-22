import pytest

from display_utils import use_progress_bar


def test_progress_bar_rejects_out_of_range():
    with pytest.raises(Exception):
        use_progress_bar(-1, 0.0, 1.0)
    with pytest.raises(Exception):
        use_progress_bar(101, 0.0, 1.0)


def test_progress_bar_renders_percentage(capsys):
    use_progress_bar(50, 0.0, 1.0)
    assert "50%" in capsys.readouterr().out
