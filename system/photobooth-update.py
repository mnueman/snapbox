#!/usr/bin/env python3
"""Updates the photobooth from GitHub, rolling back automatically if the new version won't run.

Runs as root from photobooth-update.service, which the app's UPDATES screen starts.
Usage: photobooth-update.py [--branch NAME]   update (default branch: stable)
       photobooth-update.py --recover         at boot: undo an update a power cut interrupted
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path("/home/admin/photobooth")
USER = "admin"
BRANCH = "stable"
REMOTE = "updates"  # the public repo over HTTPS; see system/setup-updates.sh
SERVICE = "photobooth.service"
RESULT_FILE = REPO / "update-result.json"  # read (and removed) by the app to show the outcome
PENDING_FILE = REPO / "update-pending.json"  # exists only while switching versions
SETTLE_SECONDS = 20  # after the app reports ready, it must stay up this long


def log(msg):
    print(msg, flush=True)


def git(*args, check=True):
    # As admin, so files keep their owner and git uses admin's credentials.
    result = subprocess.run(
        ["runuser", "-u", USER, "--", "env", f"HOME=/home/{USER}", "GIT_TERMINAL_PROMPT=0",
         "git", "-C", str(REPO), *args],
        capture_output=True, text=True, timeout=180)
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def write_json(path, data):
    tmp = path.with_name(f".{path.name}.tmp")
    with open(tmp, "w") as f:
        json.dump(data, f)
        f.flush()
        os.fsync(f.fileno())
    os.chown(tmp, *_admin_ids())
    os.replace(tmp, path)
    os.sync()


def _admin_ids():
    st = REPO.stat()
    return st.st_uid, st.st_gid


def version(sha):
    return git("log", "-1", "--format=%h %cs", sha)


def result(ok, message, **extra):
    log(message)
    write_json(RESULT_FILE, {"ok": ok, "message": message, "time": time.time(), **extra})


def switch_to(sha):
    # Sparse checkout (system/gifts.py): only this booth's person's gifts are checked out.
    git("checkout", "--quiet", "--force", "--detach", sha)
    os.sync()
    # The service, sudoers and polkit files of that version.
    run = subprocess.run(["sh", str(REPO / "system" / "install.sh")],
                         capture_output=True, text=True, timeout=180)
    if run.returncode != 0:
        raise RuntimeError(f"install.sh failed: {run.stderr.strip() or run.stdout.strip()}")


def _service_prop(prop):
    return subprocess.run(["systemctl", "show", SERVICE, "-p", prop, "--value"],
                          capture_output=True, text=True).stdout.strip()


def app_healthy():
    # photobooth.service is Type=notify: restart returns once the app says it's ready,
    # or fails if it crashes or never gets there.
    log("Restarting the app...")
    run = subprocess.run(["systemctl", "restart", SERVICE], capture_output=True, text=True,
                         timeout=300)
    if run.returncode != 0:
        log(f"App did not start: {run.stderr.strip()}")
        return False
    restarts = _service_prop("NRestarts")
    time.sleep(SETTLE_SECONDS)
    ok = _service_prop("ActiveState") == "active" and _service_prop("NRestarts") == restarts
    log("App is running." if ok else "App stopped or restarted after starting.")
    return ok


def update(branch):
    previous = git("rev-parse", "HEAD")
    if git("status", "--porcelain", "--untracked-files=no"):
        result(False, "LOCAL CHANGES ON THE BOOTH; UPDATE SKIPPED")
        return 1

    log(f"Fetching {branch}...")
    try:
        git("fetch", "--quiet", REMOTE, branch)
    except RuntimeError as e:
        log(str(e))
        result(False, "COULDN'T REACH GITHUB; CHECK WIFI")
        return 1
    target = git("rev-parse", f"{REMOTE}/{branch}")
    if target == previous:
        result(True, "ALREADY UP TO DATE", version=version(target))
        return 0

    # Cheap check before touching anything: the new app must at least compile.
    try:
        compile(git("show", f"{target}:photobooth.py"), "photobooth.py", "exec")
    except SyntaxError as e:
        log(f"New version doesn't compile: {e}")
        result(False, "UPDATE IS BROKEN; NOT INSTALLED", version=version(previous))
        return 1

    log(f"Updating {version(previous)} -> {version(target)}")
    write_json(PENDING_FILE, {"previous": previous, "target": target})
    try:
        switch_to(target)
        ok = app_healthy()
    except Exception as e:
        log(f"Update failed: {e}")
        ok = False

    if ok:
        PENDING_FILE.unlink()
        os.sync()
        result(True, "UPDATED", version=version(target))
        return 0

    log(f"Rolling back to {version(previous)}")
    try:
        switch_to(previous)
        PENDING_FILE.unlink()
        os.sync()
        app_healthy()
    except Exception as e:
        log(f"Rollback problem: {e}")
    result(False, "UPDATE FAILED; KEPT THE OLD VERSION", version=version(previous))
    return 1


def recover():
    # Runs before the app at boot. A leftover marker means a power cut hit mid-update.
    if not PENDING_FILE.exists():
        return 0
    previous = json.loads(PENDING_FILE.read_text())["previous"]
    log(f"Update was interrupted; restoring {previous[:7]}")
    switch_to(previous)
    PENDING_FILE.unlink()
    os.sync()
    result(False, "UPDATE WAS INTERRUPTED; KEPT THE OLD VERSION", version=version(previous))
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    if args == ["--recover"]:
        sys.exit(recover())
    branch = args[1] if len(args) == 2 and args[0] == "--branch" else BRANCH
    sys.exit(update(branch))
