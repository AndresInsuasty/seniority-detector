# ejemplo senior — para el video
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import requests

log = logging.getLogger(__name__)


@dataclass
class User:
    name: str
    email: str
    score: int


def fetch_active_users(api_url: str, min_score: int = 50) -> list[User]:
    """Fetch users from the API and return those that are active and above the score threshold.

    Args:
        api_url: Base URL of the users API endpoint.
        min_score: Minimum score to include a user. Defaults to 50.

    Returns:
        List of User objects matching the criteria.
    """
    response = requests.get(api_url, timeout=10)
    response.raise_for_status()

    return [
        User(name=u["name"], email=u["email"], score=u["score"])
        for u in response.json()
        if u.get("active") and u.get("score", 0) > min_score
    ]


def save_users(users: list[User], output_path: Path) -> None:
    """Serialize users to JSON and write to disk atomically."""
    payload = [{"name": u.name, "email": u.email, "score": u.score} for u in users]
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    log.info("Saved %d users to %s", len(users), output_path)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    api_url = "http://localhost:8080/api/users"

    try:
        users = fetch_active_users(api_url, min_score=50)
    except requests.HTTPError as exc:
        log.error("API request failed: %s", exc)
        raise SystemExit(1) from exc

    output = Path("output.json")
    save_users(users, output)


if __name__ == "__main__":
    main()
