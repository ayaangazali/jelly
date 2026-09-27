import io
import subprocess
import sys
import tarfile

from conftest import ROOT


def test_committed_demo_repo_is_green(tmp_path):
    archive = subprocess.run(
        ["git", "archive", "HEAD", "demo-repo"], cwd=ROOT, capture_output=True, check=True
    ).stdout
    tarfile.open(fileobj=io.BytesIO(archive)).extractall(tmp_path, filter="data")
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        cwd=tmp_path / "demo-repo",
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0 and "10 passed" in r.stdout, r.stdout + r.stderr
