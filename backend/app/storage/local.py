"""Single-PC SQLite storage. SQL values are bound; maintenance is offline."""

import hashlib
import logging
import os
import shutil
import sqlite3
import stat
from contextlib import closing, contextmanager, suppress
from pathlib import Path
from uuid import UUID, uuid4

from app import config
from app.config import Settings
from app.errors import StorageError
from app.storage.action_schema import ACTION_SCHEMA
from app.storage.import_schema import IMPORT_SCHEMA
from app.storage.passport_schema import PASSPORT_SCHEMA
from app.storage.run_schema import RUN_SCHEMA
from app.storage.whatsapp_schema import WHATSAPP_SCHEMA
from app.storage.workflow_schema import WORKFLOW_SCHEMA

APPLICATION_ID = int.from_bytes(b"GSTS", "big")
SCHEMA_VERSION = 7
BASE_SCHEMA = (
    "CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL) STRICT",
    """CREATE TABLE users (
        id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE,
        salt BLOB NOT NULL CHECK(length(salt)=16),
        digest BLOB NOT NULL CHECK(length(digest)=32),
        algorithm TEXT NOT NULL CHECK(algorithm='scrypt-v1'),
        active INTEGER NOT NULL CHECK(active IN (0,1)), created_at INTEGER NOT NULL,
        version INTEGER NOT NULL DEFAULT 1 CHECK(version>0)) STRICT""",
    """CREATE TABLE workspaces (id TEXT PRIMARY KEY, name TEXT NOT NULL,
        created_at INTEGER NOT NULL, version INTEGER NOT NULL DEFAULT 1 CHECK(version>0)) STRICT""",
    """CREATE TABLE memberships (
        workspace_id TEXT NOT NULL REFERENCES workspaces(id),
        user_id TEXT NOT NULL REFERENCES users(id),
        role TEXT NOT NULL CHECK(role IN ('OWNER','REVIEWER','VIEWER')),
        active INTEGER NOT NULL CHECK(active IN (0,1)),
        version INTEGER NOT NULL DEFAULT 1 CHECK(version>0),
        PRIMARY KEY(workspace_id,user_id)) STRICT""",
    """CREATE TABLE registrations (
        id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES workspaces(id),
        gstin TEXT NOT NULL, display_name TEXT NOT NULL, created_at INTEGER NOT NULL,
        version INTEGER NOT NULL DEFAULT 1 CHECK(version>0),
        UNIQUE(workspace_id,gstin), UNIQUE(workspace_id,id)) STRICT""",
    """CREATE TABLE sessions (
        token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL UNIQUE REFERENCES users(id),
        created_at INTEGER NOT NULL,
        expires_at INTEGER NOT NULL CHECK(expires_at>created_at)) STRICT""",
    """CREATE TABLE rate_windows (bucket TEXT PRIMARY KEY,
        start INTEGER NOT NULL, count INTEGER NOT NULL CHECK(count>0)) STRICT""",
)
VERSION2_SCHEMA = BASE_SCHEMA + IMPORT_SCHEMA
VERSION3_SCHEMA = VERSION2_SCHEMA + RUN_SCHEMA
VERSION4_SCHEMA = VERSION3_SCHEMA + WORKFLOW_SCHEMA
VERSION5_SCHEMA = VERSION4_SCHEMA + ACTION_SCHEMA
VERSION6_SCHEMA = VERSION5_SCHEMA + WHATSAPP_SCHEMA
SCHEMA = VERSION6_SCHEMA + PASSPORT_SCHEMA


def schema_digest(connection: sqlite3.Connection) -> str:
    rows = connection.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_master "
        "WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"
    ).fetchall()
    return hashlib.sha256(repr([tuple(row) for row in rows]).encode()).hexdigest()


def expected_digest(statements=SCHEMA) -> str:
    with closing(sqlite3.connect(":memory:")) as connection:
        for statement in statements:
            connection.execute(statement)
        return schema_digest(connection)


EXPECTED_DIGEST = expected_digest()
LEGACY_DIGEST = expected_digest(BASE_SCHEMA)
VERSION2_DIGEST = expected_digest(VERSION2_SCHEMA)
VERSION3_DIGEST = expected_digest(VERSION3_SCHEMA)
VERSION4_DIGEST = expected_digest(VERSION4_SCHEMA)
VERSION5_DIGEST = expected_digest(VERSION5_SCHEMA)
VERSION6_DIGEST = expected_digest(VERSION6_SCHEMA)


def check_path(path: Path, root: Path) -> None:
    """Reject links, junctions, devices and traversal, including intermediate paths."""
    if not path.absolute().is_relative_to(root.absolute()):
        raise StorageError("Private storage path is outside its allowed directory.")
    for entry in [root, *reversed(path.relative_to(root).parents), path]:
        candidate = entry if entry.is_absolute() else root / entry
        if candidate.exists() or candidate.is_symlink():
            info = candidate.lstat()
            if (
                stat.S_ISLNK(info.st_mode)
                or getattr(info, "st_file_attributes", 0) & 0x400
                or not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode))
            ):
                raise StorageError("Private storage must use ordinary local files and directories.")
            # lstat/reparse/type checks above already reject linked ordinary-file entries.
            # Windows can misresolve a journal that disappears before GetFinalPathName runs.
            if stat.S_ISDIR(info.st_mode) and candidate.resolve() != candidate.absolute():
                raise StorageError("Private storage cannot contain linked paths.")


class LocalStore:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.root = settings.local_data_dir
        self.path = self.root / "gstshield.sqlite3"
        self._lock = None
        self.opened = False

    def acquire(self) -> None:
        if self.opened:
            raise StorageError("Private storage is already locked by this instance.")
        try:
            check_path(self.root, config.BACKEND_DIR / "data")
            self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
            lock_path = self.root / ".lock"
            check_path(lock_path, config.BACKEND_DIR / "data")
            self._lock = lock_path.open("a+b")
            if lock_path.stat().st_size == 0:
                self._lock.write(b"0")
                self._lock.flush()
            self._lock.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self._lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.opened = True
        except (OSError, StorageError):
            self.close()
            raise StorageError(
                "Cannot lock private storage; stop other backend/maintenance processes."
            ) from None

    def close(self) -> None:
        self.opened = False
        if self._lock is not None:
            self._lock.close()
            self._lock = None

    def connect(self, path: Path | None = None, *, readonly: bool = False) -> sqlite3.Connection:
        target = path or self.path
        check_path(target, config.BACKEND_DIR / "data")
        connection = sqlite3.connect(
            target.as_uri() + ("?mode=ro" if readonly else "?mode=rw"),
            uri=True,
            timeout=2,
            isolation_level=None,
        )
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA trusted_schema=OFF")
            if not readonly:
                connection.execute("PRAGMA synchronous=FULL")
                size = connection.execute("PRAGMA page_size").fetchone()[0]
                connection.execute(
                    f"PRAGMA max_page_count={self.settings.max_database_bytes // size}"
                )
        except BaseException:
            connection.close()
            raise
        return connection

    def validate(
        self, path: Path | None = None, *, legacy: bool = False, version: int | None = None
    ) -> None:
        selected = 1 if legacy else (version if version is not None else SCHEMA_VERSION)
        fingerprints = {
            1: LEGACY_DIGEST,
            2: VERSION2_DIGEST,
            3: VERSION3_DIGEST,
            4: VERSION4_DIGEST,
            5: VERSION5_DIGEST,
            6: VERSION6_DIGEST,
            7: EXPECTED_DIGEST,
        }
        if selected not in fingerprints:
            raise StorageError("Storage schema version is unsupported.")
        try:
            check_path(path or self.path, config.BACKEND_DIR / "data")
            if (path or self.path).stat().st_size > self.settings.max_database_bytes:
                raise StorageError("Storage exceeds the configured database size limit.")
            with closing(self.connect(path, readonly=True)) as connection:
                if (
                    connection.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID
                    or connection.execute("PRAGMA user_version").fetchone()[0] != selected
                    or schema_digest(connection) != fingerprints[selected]
                    or [row[0] for row in connection.execute("PRAGMA quick_check")] != ["ok"]
                    or connection.execute("PRAGMA foreign_key_check").fetchone() is not None
                    or connection.execute("PRAGMA journal_mode").fetchone()[0] != "delete"
                    or (path or self.path).stat().st_size > self.settings.max_database_bytes
                ):
                    raise StorageError(
                        "Storage is corrupt, incompatible or exceeds its configured limit."
                    )
        except (sqlite3.Error, OSError):
            raise StorageError(
                "Storage cannot be validated; preserve it and use offline recovery."
            ) from None

    def capacity(self, growth: int = 131072) -> None:
        def scan_error(error: OSError) -> None:
            raise StorageError("Private storage directory cannot be inspected.") from None

        try:
            total = 0
            count = 0
            for folder, directories, files in os.walk(
                self.root, followlinks=False, onerror=scan_error
            ):
                for name in directories + files:
                    item = Path(folder) / name
                    try:
                        check_path(item, config.BACKEND_DIR / "data")
                        if item.is_file():
                            total += item.stat().st_size
                    except FileNotFoundError:
                        # SQLite journals and worker descriptors can vanish during a quota scan.
                        # The live database is separately opened with mode=rw; never recreate it.
                        continue
                    count += 1
                    if count > 1000:
                        raise StorageError("Private storage file count limit reached.")
            journal = self.path.stat().st_size if self.path.exists() else 131072
            reserve = journal + growth
            if total + reserve > self.settings.max_local_data_bytes:
                raise StorageError("Private storage quota reached; no changes were saved.")
            if shutil.disk_usage(self.root).free < reserve + self.settings.min_free_disk_bytes:
                raise StorageError("Insufficient free disk space; no changes were saved.")
        except OSError:
            raise StorageError("Private storage is unavailable.") from None

    def initialize(self) -> None:
        if not self.opened:
            raise StorageError("Private storage is not locked.")
        created = False
        try:
            check_path(self.path, config.BACKEND_DIR / "data")
            if not self.path.exists():
                self.capacity()
                descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.close(descriptor)
                created = True
                with self.transaction() as connection:
                    connection.execute(f"PRAGMA application_id={APPLICATION_ID}")
                    connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                    for statement in SCHEMA:
                        connection.execute(statement)
                    connection.execute(
                        "INSERT INTO metadata VALUES ('schema',?)", (EXPECTED_DIGEST,)
                    )
            self.validate()
        except (StorageError, OSError, sqlite3.Error):
            if created:
                # Only this call's newly created file may be removed; never an existing DB.
                self.path.unlink(missing_ok=True)
            raise StorageError(
                "Cannot initialize storage; preserve existing files and use offline recovery."
            ) from None

    def upgrade(self) -> str | None:
        """Explicit offline v1 through v6 upgrade: validate and preserve before adding tables."""
        if not self.opened:
            raise StorageError("Private storage is not locked.")
        try:
            with closing(self.connect(readonly=True)) as connection:
                version = connection.execute("PRAGMA user_version").fetchone()[0]
        except (sqlite3.Error, OSError):
            raise StorageError(
                "Cannot inspect old storage; preserve it for offline recovery."
            ) from None
        if version == SCHEMA_VERSION:
            self.validate()
            return None
        self.validate(version=version)
        backup_root = self.root / "backups"
        check_path(backup_root, config.BACKEND_DIR / "data")
        backup_root.mkdir(exist_ok=True, mode=0o700)
        if len(list(backup_root.iterdir())) >= self.settings.max_local_backups:
            raise StorageError("Backup count limit prevents preserving the old schema.")
        self.capacity(self.path.stat().st_size + 131072)
        identifier = str(uuid4())
        self.copy_database(self.path, backup_root / f"{identifier}.sqlite3", version=version)
        with self.transaction() as connection:
            additions = IMPORT_SCHEMA if version == 1 else ()
            additions += RUN_SCHEMA if version < 3 else ()
            additions += WORKFLOW_SCHEMA if version < 4 else ()
            additions += ACTION_SCHEMA if version < 5 else ()
            additions += WHATSAPP_SCHEMA if version < 6 else ()
            for statement in additions + PASSPORT_SCHEMA:
                connection.execute(statement)
            connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
            connection.execute("UPDATE metadata SET value=? WHERE key='schema'", (EXPECTED_DIGEST,))
        self.validate()
        return identifier

    @contextmanager
    def transaction(self, *, write: bool = True):
        if not self.opened:
            raise StorageError("Private storage is not available.")
        connection = None
        try:
            if write:
                self.capacity()
            connection = self.connect(readonly=not write)
            connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield connection
            connection.commit()
        except sqlite3.IntegrityError:
            if connection is not None:
                with suppress(sqlite3.Error):
                    connection.rollback()
            raise
        except (sqlite3.Error, OSError) as exc:
            logging.getLogger("gstshield").warning(
                "Storage transaction failure exception_type=%s code=%s",
                type(exc).__name__,
                getattr(exc, "sqlite_errorcode", getattr(exc, "errno", None)),
            )
            if connection is not None:
                with suppress(sqlite3.Error):
                    connection.rollback()
            raise StorageError(
                "Private storage operation failed; retry after checking local storage."
            ) from None
        except BaseException:
            if connection is not None:
                with suppress(sqlite3.Error):
                    connection.rollback()
            raise
        finally:
            if connection is not None:
                connection.close()

    def ready(self) -> bool:
        try:
            with self.transaction(write=False) as connection:
                return (
                    connection.execute("SELECT value FROM metadata WHERE key='schema'").fetchone()[
                        0
                    ]
                    == EXPECTED_DIGEST
                )
        except (StorageError, TypeError):
            return False

    def backup(self) -> str:
        if not self.opened:
            raise StorageError("Private storage is not locked.")
        self.validate()
        backup_root = self.root / "backups"
        check_path(backup_root, config.BACKEND_DIR / "data")
        backup_root.mkdir(exist_ok=True, mode=0o700)
        if len(list(backup_root.iterdir())) >= self.settings.max_local_backups:
            raise StorageError(
                "Backup count limit reached; archive an old backup outside private storage first."
            )
        self.capacity(self.path.stat().st_size + 131072)
        identifier = str(uuid4())
        destination = backup_root / f"{identifier}.sqlite3"
        self.copy_database(self.path, destination)
        return identifier

    def copy_database(
        self, source: Path, destination: Path, *, legacy: bool = False, version: int | None = None
    ) -> None:
        descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(descriptor)
        try:
            with (
                closing(self.connect(source, readonly=True)) as origin,
                closing(self.connect(destination)) as target,
            ):
                origin.backup(target)
            self.validate(destination, legacy=legacy, version=version)
            with destination.open("r+b") as stream:
                os.fsync(stream.fileno())
        except (StorageError, sqlite3.Error, OSError):
            destination.unlink(missing_ok=True)
            raise StorageError("Backup failed; live storage was not changed.") from None

    def restore(self, identifier: str) -> str:
        if not self.opened:
            raise StorageError("Private storage is not locked.")
        try:
            if str(UUID(identifier)) != identifier:
                raise ValueError
        except ValueError:
            raise StorageError("Use a generated backup UUID.") from None
        source = self.root / "backups" / f"{identifier}.sqlite3"
        self.validate(source)
        for suffix in ("-journal", "-wal", "-shm"):
            if Path(str(self.path) + suffix).exists():
                raise StorageError(
                    "Live storage has recovery sidecars; preserve them before offline recovery."
                )
        self.capacity(
            source.stat().st_size + (self.path.stat().st_size if self.path.exists() else 0)
        )
        if len(list((self.root / "backups").iterdir())) >= self.settings.max_local_backups:
            raise StorageError(
                "Backup limit prevents preserving the current database before restore."
            )
        staging = self.root / f"restore-{uuid4()}.sqlite3"
        preserved = self.root / "backups" / f"recovery-{uuid4()}.sqlite3"
        try:
            self.copy_database(source, staging)
            with closing(self.connect(staging)) as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute("DELETE FROM sessions")
                connection.execute("DELETE FROM rate_windows")
                # A backup must not resurrect revoked accounts or old passwords.
                connection.execute("UPDATE users SET active=0, version=version+1")
                connection.commit()
            self.validate(staging)
            if self.path.exists():
                check_path(self.path, config.BACKEND_DIR / "data")
                descriptor = os.open(preserved, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.close(descriptor)
                shutil.copyfile(self.path, preserved)
                with preserved.open("r+b") as stream:
                    os.fsync(stream.fileno())
            with staging.open("r+b") as stream:
                os.fsync(stream.fileno())
            os.replace(staging, self.path)
            return preserved.name
        except (OSError, sqlite3.Error):
            raise StorageError(
                "Restore failed; check offline recovery files before restarting."
            ) from None
        finally:
            staging.unlink(missing_ok=True)
