"""Tests for crypto watchlist repository and API endpoints."""
import os
import sys
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.storage import CryptoLaunch, DatabaseManager


class CryptoWatchlistRepositoryTestCase(unittest.TestCase):
    def setUp(self) -> None:
        DatabaseManager.reset_instance()
        self.db = DatabaseManager("sqlite:///:memory:")

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()

    def _create_launch(self, pair_address: str, symbol: str) -> int:
        with self.db.get_session() as session:
            launch = CryptoLaunch(
                chain_id="bsc",
                pair_address=pair_address,
                base_token_symbol=symbol,
                base_token_name=f"{symbol} Token",
            )
            session.add(launch)
            session.commit()
            return launch.id

    def test_add_watch_creates_entry(self) -> None:
        from src.repositories.crypto_watchlist_repo import CryptoWatchlistRepository

        launch_id = self._create_launch("0xwatch1", "W1")
        repo = CryptoWatchlistRepository(self.db)

        entry = repo.add_watch(launch_id, note="Keep an eye on it")

        self.assertIsNotNone(entry)
        self.assertEqual(entry["launch_id"], launch_id)
        self.assertEqual(entry["note"], "Keep an eye on it")
        self.assertIsNotNone(entry["watched_at"])

    def test_add_watch_idempotent(self) -> None:
        from src.repositories.crypto_watchlist_repo import CryptoWatchlistRepository

        launch_id = self._create_launch("0xwatch2", "W2")
        repo = CryptoWatchlistRepository(self.db)

        first = repo.add_watch(launch_id, note="first")
        second = repo.add_watch(launch_id, note="second")

        self.assertEqual(first["id"], second["id"])
        self.assertEqual(first["launch_id"], second["launch_id"])
        self.assertEqual(second["note"], "first")

    def test_add_watch_nonexistent_launch_returns_none(self) -> None:
        from src.repositories.crypto_watchlist_repo import CryptoWatchlistRepository

        repo = CryptoWatchlistRepository(self.db)

        self.assertIsNone(repo.add_watch(9999, note="missing"))

    def test_remove_watch_success(self) -> None:
        from src.repositories.crypto_watchlist_repo import CryptoWatchlistRepository

        launch_id = self._create_launch("0xwatch3", "W3")
        repo = CryptoWatchlistRepository(self.db)
        repo.add_watch(launch_id)

        removed = repo.remove_watch(launch_id)

        self.assertTrue(removed)
        self.assertFalse(repo.is_watched(launch_id))

    def test_remove_watch_not_found(self) -> None:
        from src.repositories.crypto_watchlist_repo import CryptoWatchlistRepository

        repo = CryptoWatchlistRepository(self.db)

        self.assertFalse(repo.remove_watch(1234))

    def test_list_watched_ordered_by_watched_at(self) -> None:
        from src.repositories.crypto_watchlist_repo import CryptoWatchlistRepository
        from src.storage import CryptoWatchlist

        older_launch_id = self._create_launch("0xwatch4", "W4")
        newer_launch_id = self._create_launch("0xwatch5", "W5")
        older = datetime.now() - timedelta(hours=2)
        newer = datetime.now() - timedelta(minutes=10)

        with self.db.get_session() as session:
            session.add(
                CryptoWatchlist(launch_id=older_launch_id, watched_at=older, note="older")
            )
            session.add(
                CryptoWatchlist(launch_id=newer_launch_id, watched_at=newer, note="newer")
            )
            session.commit()

        repo = CryptoWatchlistRepository(self.db)
        items = repo.list_watched()

        self.assertEqual([item["launch_id"] for item in items], [newer_launch_id, older_launch_id])

    def test_is_watched_true_and_false(self) -> None:
        from src.repositories.crypto_watchlist_repo import CryptoWatchlistRepository

        watched_launch_id = self._create_launch("0xwatch6", "W6")
        unwatched_launch_id = self._create_launch("0xwatch7", "W7")
        repo = CryptoWatchlistRepository(self.db)
        repo.add_watch(watched_launch_id)

        self.assertTrue(repo.is_watched(watched_launch_id))
        self.assertFalse(repo.is_watched(unwatched_launch_id))

    def test_get_watched_launch_ids(self) -> None:
        from src.repositories.crypto_watchlist_repo import CryptoWatchlistRepository

        launch_id_one = self._create_launch("0xwatch8", "W8")
        launch_id_two = self._create_launch("0xwatch9", "W9")
        repo = CryptoWatchlistRepository(self.db)
        repo.add_watch(launch_id_one)
        repo.add_watch(launch_id_two)

        launch_ids = repo.get_watched_launch_ids()

        self.assertCountEqual(launch_ids, [launch_id_one, launch_id_two])
        self.assertTrue(all(isinstance(item, int) for item in launch_ids))


class CryptoWatchlistEndpointTestCase(unittest.TestCase):
    def setUp(self) -> None:
        from api.v1.endpoints.crypto_watchlist import router

        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)

    def test_list_watchlist_endpoint(self) -> None:
        with patch("api.v1.endpoints.crypto_watchlist._get_repo") as mock_get_repo:
            mock_repo = mock_get_repo.return_value
            mock_repo.list_watched.return_value = [
                {
                    "id": 1,
                    "launch_id": 10,
                    "watched_at": "2026-03-21T10:00:00",
                    "note": "tracked",
                }
            ]

            response = self.client.get("/watchlist")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 1)
        self.assertEqual(response.json()["items"][0]["launch_id"], 10)

    def test_add_watchlist_endpoint(self) -> None:
        with patch("api.v1.endpoints.crypto_watchlist._get_repo") as mock_get_repo:
            mock_repo = mock_get_repo.return_value
            mock_repo.add_watch.return_value = {
                "id": 2,
                "launch_id": 22,
                "watched_at": "2026-03-21T10:05:00",
                "note": "buy later",
            }

            response = self.client.post("/watchlist/22", json={"note": "buy later"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["entry"]["launch_id"], 22)
        self.assertEqual(payload["message"], "Added to watchlist")

    def test_remove_watchlist_endpoint(self) -> None:
        with patch("api.v1.endpoints.crypto_watchlist._get_repo") as mock_get_repo:
            mock_repo = mock_get_repo.return_value
            mock_repo.remove_watch.return_value = True

            response = self.client.delete("/watchlist/33")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertEqual(response.json()["message"], "Removed from watchlist")

    def test_get_watched_ids_endpoint(self) -> None:
        with patch("api.v1.endpoints.crypto_watchlist._get_repo") as mock_get_repo:
            mock_repo = mock_get_repo.return_value
            mock_repo.get_watched_launch_ids.return_value = [1, 2, 5]

            response = self.client.get("/watchlist/ids")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["launch_ids"], [1, 2, 5])


if __name__ == "__main__":
    unittest.main()
