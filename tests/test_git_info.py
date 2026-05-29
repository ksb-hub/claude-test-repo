import pytest
from unittest.mock import patch
from git_info import get_local_branches, get_remote_branches


LOCAL_VV = """\
* main          abc1234 [origin/main] latest
  feature/auth  def5678 [origin/feature/auth: ahead 2] wip
  bugfix/login  abc9012 no remote yet"""

REMOTE_R = """\
  origin/HEAD -> origin/main
  origin/main
  origin/feature/auth"""


def mock_run(args, cwd):
    if args == ["branch", "-vv"]:
        return LOCAL_VV
    if args == ["branch", "-r"]:
        return REMOTE_R
    return ""


@patch("git_info._run", side_effect=mock_run)
def test_get_local_branches(mock):
    branches = get_local_branches()
    assert len(branches) == 3

    main = branches[0]
    assert main["name"] == "main"
    assert main["current"] is True
    assert main["remote"] == "origin/main"
    assert main["ahead"] == 0
    assert main["behind"] == 0

    feature = branches[1]
    assert feature["name"] == "feature/auth"
    assert feature["current"] is False
    assert feature["remote"] == "origin/feature/auth"
    assert feature["ahead"] == 2

    no_remote = branches[2]
    assert no_remote["remote"] is None


@patch("git_info._run", side_effect=mock_run)
def test_get_remote_branches(mock):
    branches = get_remote_branches()
    assert "origin/main" in branches
    assert "origin/feature/auth" in branches
    assert not any("HEAD" in b for b in branches)
