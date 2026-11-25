"""Print a password hash for backend/.env.

Usage (from the backend directory, with the virtualenv active):

    python scripts/make_password_hash.py

The password is read with getpass, so it is never echoed and never written to
shell history. Paste the printed line into backend/.env as AXIOM_PASSWORD_HASH.
"""

from __future__ import annotations

import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.auth import PBKDF2_ITERATIONS, hash_password  # noqa: E402


def main() -> int:
    password = getpass.getpass("Password: ")
    if not password:
        print("No password entered; nothing to do.", file=sys.stderr)
        return 1

    repeated = getpass.getpass("Repeat password: ")
    if password != repeated:
        print("The two passwords do not match.", file=sys.stderr)
        return 1

    print("Add this line to backend/.env:")
    print("AXIOM_PASSWORD_HASH={}".format(hash_password(password)))
    print("(pbkdf2_sha256, {} iterations)".format(PBKDF2_ITERATIONS), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
