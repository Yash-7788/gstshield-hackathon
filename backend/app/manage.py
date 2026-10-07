"""Offline local administration. Passwords are prompted, never CLI arguments."""

import argparse
import getpass
import sys
import warnings

from app.config import ConfigurationError, load_settings
from app.errors import APIError, StorageError
from app.services.access import AccessService
from app.storage.local import LocalStore


def new_password() -> str:
    if not sys.stdin.isatty():
        raise ValueError("Use an interactive terminal for private password prompts.")
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        first = getpass.getpass("Password (12-128 characters): ")
        second = getpass.getpass("Confirm password: ")
    if first != second:
        raise ValueError("Password confirmation does not match.")
    return first


def main() -> int:
    parser = argparse.ArgumentParser(
        description="GSTShield offline local administration; stop the backend first."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("user-create")
    create.add_argument("--username", required=True)
    create.add_argument("--workspace", required=True)
    reset = commands.add_parser("password-reset")
    reset.add_argument("--username", required=True)
    grant = commands.add_parser("membership-set")
    grant.add_argument("--username", required=True)
    grant.add_argument("--workspace-id", required=True)
    grant.add_argument("--role", choices=["OWNER", "REVIEWER", "VIEWER"], required=True)
    grant.add_argument("--revoke", action="store_true")
    registration = commands.add_parser("registration-create")
    registration.add_argument("--workspace-id", required=True)
    registration.add_argument("--gstin", required=True)
    registration.add_argument("--name", required=True)
    commands.add_parser("backup")
    commands.add_parser("storage-upgrade")
    restore = commands.add_parser("restore")
    restore.add_argument("--backup-id", required=True)
    arguments = parser.parse_args()
    store = None
    try:
        store = LocalStore(load_settings())
        store.acquire()
        if arguments.command == "restore":
            preserved = store.restore(arguments.backup_id)
            print(
                f"Restored. Prior database preserved as {preserved}. "
                "All restored accounts are disabled; reset intended users' passwords "
                "and review memberships before launch."
            )
            return 0
        if arguments.command == "storage-upgrade":
            identifier = store.upgrade()
            print(
                "Storage upgraded; prior schema backup ID: " + identifier
                if identifier
                else "Storage schema is current."
            )
            return 0
        store.initialize()
        access = AccessService(store)
        if arguments.command == "user-create":
            user, workspace = access.provision(
                arguments.username, new_password(), arguments.workspace
            )
            print(f"User ID: {user}\nWorkspace ID: {workspace}")
        elif arguments.command == "password-reset":
            access.reset_password(arguments.username, new_password())
            print("Password reset, account enabled, and previous sessions revoked.")
        elif arguments.command == "membership-set":
            access.grant(
                arguments.username,
                arguments.workspace_id,
                arguments.role,
                active=not arguments.revoke,
            )
            print("Membership updated.")
        elif arguments.command == "registration-create":
            print(
                "Registration ID: "
                + access.add_registration(arguments.workspace_id, arguments.gstin, arguments.name)
            )
        elif arguments.command == "backup":
            print("Backup ID: " + store.backup())
        return 0
    except (ConfigurationError, StorageError, APIError, ValueError) as exc:
        print(
            str(exc)
            if not isinstance(exc, ValueError)
            else "Invalid administration input; check command values and password requirements.",
            file=sys.stderr,
        )
        return 2
    except (OSError, EOFError, getpass.GetPassWarning):
        print(
            "Local administration could not complete; check terminal and local storage access.",
            file=sys.stderr,
        )
        return 2
    finally:
        if store is not None:
            store.close()


if __name__ == "__main__":
    raise SystemExit(main())
