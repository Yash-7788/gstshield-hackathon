"""Storage boundaries use actual disk files and SQLite transactions."""

import shutil
import sqlite3
from uuid import uuid4

import pytest

from app.config import Settings
from app.errors import APIError, StorageError
from app.services.access import AccessService
from app.storage.local import LocalStore


@pytest.fixture
def store():
    result = LocalStore(Settings())
    result.acquire()
    result.initialize()
    try:
        yield result
    finally:
        result.close()


def test_process_lock_blocks_second_runtime_and_offline_maintenance(store):
    other = LocalStore(store.settings)
    with pytest.raises(StorageError, match="Cannot lock"):
        other.acquire()
    assert store.ready()
    store.close()
    other.acquire()
    other.initialize()
    other.close()


@pytest.mark.parametrize("kind", ["corrupt", "empty", "foreign", "future", "modified"])
def test_existing_unsafe_database_is_preserved(kind):
    settings = Settings()
    store = LocalStore(settings)
    store.acquire()
    try:
        if kind == "corrupt":
            store.path.write_bytes(b"synthetic-corrupt-private-data")
        elif kind == "empty":
            store.path.touch()
        elif kind == "foreign":
            connection = sqlite3.connect(store.path)
            connection.execute("CREATE TABLE foreign_app (id INTEGER)")
            connection.close()
        else:
            store.initialize()
            connection = sqlite3.connect(store.path)
            if kind == "future":
                connection.execute("PRAGMA user_version=999")
            else:
                connection.execute("CREATE TABLE unexpected (id INTEGER)")
            connection.close()
        before = store.path.read_bytes()
        with pytest.raises(StorageError):
            store.initialize()
        assert store.path.read_bytes() == before
    finally:
        store.close()


def test_backup_restore_preserves_previous_db_and_requires_access_recovery(store):
    access = AccessService(store)
    _, workspace = access.provision("alice", "synthetic-passphrase-only", "Original")
    token, _ = access.login("alice", "synthetic-passphrase-only")
    backup = store.backup()
    access.add_registration(workspace, "27ABCDE1234F1Z5", "Added after backup")
    before = store.path.read_bytes()
    preserved = store.restore(backup)
    assert (store.root / "backups" / preserved).read_bytes() == before
    assert store.ready()
    with store.transaction(write=False) as connection:
        assert connection.execute("SELECT COUNT(*) FROM registrations").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0
        assert connection.execute("SELECT active FROM users").fetchone()[0] == 0
    with pytest.raises(APIError):
        access.identity(token)
    with pytest.raises(APIError):
        access.login("alice", "synthetic-passphrase-only")
    access.reset_password("alice", "recovered-synthetic-password")
    assert access.login("alice", "recovered-synthetic-password")[1].username == "alice"


def test_corrupt_live_db_can_be_recovered_without_destroying_evidence(store):
    backup = store.backup()
    store.path.write_bytes(b"corrupted-live-file")
    preserved = store.restore(backup)
    assert (store.root / "backups" / preserved).read_bytes() == b"corrupted-live-file"
    assert store.ready()


def test_invalid_corrupt_and_missing_backup_never_change_live_db(store):
    before = store.path.read_bytes()
    backup_root = store.root / "backups"
    backup_root.mkdir()
    corrupt = str(uuid4())
    (backup_root / f"{corrupt}.sqlite3").write_bytes(b"bad backup")
    for identifier in ("../../outside", str(uuid4()), corrupt):
        with pytest.raises(StorageError):
            store.restore(identifier)
        assert store.path.read_bytes() == before


def test_backup_count_and_restore_preservation_limits(store):
    for _ in range(store.settings.max_local_backups):
        store.backup()
    before = store.path.read_bytes()
    with pytest.raises(StorageError, match="count limit"):
        store.backup()
    with pytest.raises(StorageError, match="Backup limit"):
        store.restore(next((store.root / "backups").glob("*.sqlite3")).stem)
    assert store.path.read_bytes() == before


def test_restore_refuses_sidecar_and_preserves_it(store):
    backup = store.backup()
    sidecar = store.path.with_name(store.path.name + "-wal")
    sidecar.write_bytes(b"preserve-recovery-data")
    with pytest.raises(StorageError, match="sidecars"):
        store.restore(backup)
    assert sidecar.read_bytes() == b"preserve-recovery-data"


def test_disk_capacity_and_database_page_limit_roll_back(store, monkeypatch):
    real_disk_usage = shutil.disk_usage
    real_usage = real_disk_usage(store.root)
    monkeypatch.setattr(shutil, "disk_usage", lambda path: real_usage._replace(free=0))
    before = store.path.read_bytes()
    with pytest.raises(StorageError, match="free disk"), store.transaction() as connection:
        connection.execute("INSERT INTO metadata VALUES ('never','saved')")
    assert store.path.read_bytes() == before
    monkeypatch.setattr(shutil, "disk_usage", real_disk_usage)
    # Store settings are validated again, not bypassed with an invalid model_copy.
    store.settings = Settings(max_database_bytes=1048576)
    with pytest.raises(StorageError), store.transaction() as connection:
        connection.execute("INSERT INTO metadata VALUES ('too-big',?)", ("x" * 2000000,))
    with store.transaction(write=False) as connection:
        assert (
            connection.execute("SELECT value FROM metadata WHERE key='too-big'").fetchone() is None
        )


def test_retained_quota_is_rejected(store):
    store.settings = Settings(max_database_bytes=1048576, max_local_data_bytes=4000000)
    oversized = store.root / "oversized.synthetic"
    oversized.write_bytes(b"x" * 4000000)
    with pytest.raises(StorageError, match="quota"):
        store.capacity()
    oversized.unlink()


def test_private_symlink_is_rejected(store):
    link = store.root / "linked.synthetic"
    try:
        link.symlink_to(store.path)
    except OSError:
        pytest.skip("Creating symlinks requires Windows Developer Mode or privilege")
    with pytest.raises(StorageError, match="ordinary local"):
        store.capacity()


def test_operator_cli_has_no_password_argument_and_requires_offline_access(store):
    # The in-process parser's help is public; no service is provisioned here.
    import os
    import subprocess
    import sys

    from app.config import BACKEND_DIR

    real_backend = __import__("app.manage", fromlist=["main"]).__file__
    env = os.environ.copy()
    result = subprocess.run(
        [sys.executable, "-m", "app.manage", "user-create", "--help"],
        cwd=str(__import__("pathlib").Path(real_backend).parents[1]),
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0 and "--password" not in result.stdout
    assert store.root.parent == BACKEND_DIR


def test_private_windows_junction_is_rejected(store, tmp_path):
    import os
    import subprocess

    if os.name != "nt":
        pytest.skip("Windows junctions apply only on Windows")
    destination = tmp_path / "outside-private-storage"
    destination.mkdir()
    link = store.root / "unsafe-junction"
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(destination)],
        capture_output=True,
        timeout=10,
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    assert result.returncode == 0
    with pytest.raises(StorageError, match="ordinary local"):
        store.capacity()


def test_oversized_existing_database_is_refused_before_sqlite_open(store, monkeypatch):
    store.settings = Settings(max_database_bytes=1048576)
    store.path.write_bytes(b"x" * 2000000)

    def must_not_open(*args, **kwargs):
        raise AssertionError("Oversized existing storage must not be opened")

    monkeypatch.setattr(store, "connect", must_not_open)
    with pytest.raises(StorageError, match="size limit"):
        store.validate()
    assert store.path.stat().st_size == 2000000


def test_password_admin_requires_a_private_interactive_terminal(monkeypatch):
    import sys

    from app.manage import new_password

    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    with pytest.raises(ValueError, match="interactive terminal"):
        new_password()


def test_password_admin_refuses_getpass_echo_fallback(monkeypatch):
    import getpass
    import sys
    import warnings

    from app.manage import new_password

    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)

    def cannot_hide(prompt):
        warnings.warn("Cannot hide password", getpass.GetPassWarning, stacklevel=2)
        raise AssertionError("Echo fallback must be stopped")

    monkeypatch.setattr(getpass, "getpass", cannot_hide)
    with pytest.raises(getpass.GetPassWarning):
        new_password()


@pytest.mark.parametrize("point", ["path_check", "size_read"])
def test_vanishing_transient_file_does_not_fail_live_storage_transaction(store, monkeypatch, point):
    from pathlib import Path

    transient = store.root / (store.path.name + "-journal")
    transient.write_bytes(b"synthetic transient; not an actual active SQLite journal")
    original_check = __import__("app.storage.local", fromlist=["check_path"]).check_path
    original_stat = Path.stat
    checked = False
    vanished = False

    def check(path, root):
        nonlocal checked, vanished
        original_check(path, root)
        if path == transient:
            checked = True
            if point == "path_check":
                transient.unlink()
                vanished = True
                raise FileNotFoundError("synthetic concurrent journal removal")

    def stat(path, *args, **kwargs):
        nonlocal vanished
        if path == transient and checked and not vanished and point == "size_read":
            # is_file succeeds, followed by a disappeared file at the size-read boundary.
            info = original_stat(path, *args, **kwargs)
            transient.unlink()
            vanished = True
            return info
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr("app.storage.local.check_path", check)
    monkeypatch.setattr(Path, "stat", stat)
    with store.transaction() as connection:
        connection.execute("INSERT INTO metadata VALUES ('race-proof','saved')")
    assert vanished
    with store.transaction(write=False) as connection:
        assert (
            connection.execute("SELECT value FROM metadata WHERE key='race-proof'").fetchone()[0]
            == "saved"
        )
    assert store.ready()


def test_missing_live_database_still_fails_closed_without_recreation(store):
    store.path.unlink()
    with pytest.raises(StorageError), store.transaction() as connection:
        connection.execute("SELECT 1")
    assert not store.path.exists()


def test_ordinary_transient_file_does_not_require_racy_final_path_resolution(store, monkeypatch):
    from pathlib import Path

    transient = store.root / "ordinary-transient.synthetic"
    transient.write_bytes(b"bounded private bytes")
    original = Path.resolve

    def resolve(path, *args, **kwargs):
        if path == transient:
            pytest.fail("An ordinary lstat-checked file must not need final-path resolution")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve)
    store.capacity()
    assert store.ready()


def test_existing_directory_traversal_is_still_rejected(store):
    from app.storage.local import check_path

    outside = store.root / ".." / "outside-private.synthetic"
    outside.write_bytes(b"outside")
    with pytest.raises(StorageError):
        check_path(outside, store.root)


def test_readonly_transactions_do_not_configure_writes_or_allow_them(store):
    with store.transaction() as writer:
        writer.execute("INSERT INTO metadata VALUES ('synthetic-write-probe','pending')")
        # A reserved writer can coexist with readers in DELETE journal mode.
        assert store.ready()
        with store.transaction(write=False) as reader:
            assert (
                reader.execute(
                    "SELECT value FROM metadata WHERE key='synthetic-write-probe'"
                ).fetchone()
                is None
            )
    with pytest.raises(StorageError), store.transaction(write=False) as reader:
        reader.execute("UPDATE metadata SET value='forbidden' WHERE key='schema'")
    assert store.ready()
    with store.transaction(write=False) as reader:
        assert (
            reader.execute(
                "SELECT value FROM metadata WHERE key='synthetic-write-probe'"
            ).fetchone()[0]
            == "pending"
        )
