import sqlite3
from contextlib import closing

from app.config import Settings
from app.storage.local import (
    APPLICATION_ID,
    SCHEMA_VERSION,
    VERSION7_DIGEST,
    VERSION7_SCHEMA,
    LocalStore,
)


def test_v7_upgrade_preserves_all_existing_rows_and_a_verified_backup():
    store = LocalStore(Settings())
    store.acquire()
    try:
        with closing(sqlite3.connect(store.path)) as con, con:
            for statement in VERSION7_SCHEMA:
                con.execute(statement)
            con.execute(f"PRAGMA application_id={APPLICATION_ID}")
            con.execute("PRAGMA user_version=7")
            con.execute("INSERT INTO metadata VALUES ('schema',?)", (VERSION7_DIGEST,))
            con.execute(
                "INSERT INTO metadata VALUES ('retained-note','preserve every existing invoice')"
            )
        with closing(sqlite3.connect(store.path)) as original:
            before = list(original.iterdump())
        backup = store.upgrade()
        assert backup
        with closing(sqlite3.connect(store.root / "backups" / f"{backup}.sqlite3")) as preserved:
            assert list(preserved.iterdump()) == before
        store.validate()
        store.validate(store.root / "backups" / f"{backup}.sqlite3", version=7)
        with store.transaction(write=False) as con:
            assert con.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
            assert (
                con.execute("SELECT value FROM metadata WHERE key='retained-note'").fetchone()[0]
                == "preserve every existing invoice"
            )
            assert con.execute("PRAGMA foreign_key_check").fetchall() == []
        assert store.upgrade() is None
    finally:
        store.close()
