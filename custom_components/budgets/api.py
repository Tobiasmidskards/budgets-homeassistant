"""A small client for the Budgets read-only API (v1)."""

from __future__ import annotations

from typing import Any

import aiohttp


class BudgetsError(Exception):
    """Budgets could not be reached or answered with an error."""


class BudgetsAuthError(BudgetsError):
    """The token is missing, expired, revoked or lacks the read scope."""


class BudgetsApi:
    """Read a household's finances from Budgets with a read-only API token."""

    def __init__(self, session: aiohttp.ClientSession, url: str, token: str) -> None:
        self._session = session
        self._base = url.rstrip("/") + "/api/v1"
        self._token = token

    async def households(self) -> list[dict[str, Any]]:
        """The households the token's user belongs to."""
        return (await self._get("/households"))["households"]

    async def summary(self, household_id: int) -> dict[str, Any]:
        """Accounts, the user's month, payday, key figures and the bank sync status in one call."""
        return await self._get(f"/households/{household_id}")

    async def transactions(self, household_id: int, after: int | None, limit: int) -> dict[str, Any]:
        """Transactions with an id above `after`, oldest first (the latest ones without `after`)."""
        params: dict[str, Any] = {"limit": limit}
        if after is not None:
            params["after"] = after
        return await self._get(f"/households/{household_id}/transactions", params)

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            async with self._session.get(
                self._base + path,
                params=params,
                headers={"Authorization": f"Bearer {self._token}", "Accept": "application/json"},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status in (401, 403):
                    raise BudgetsAuthError(f"Budgets refused the token ({response.status})")
                if response.status >= 400:
                    raise BudgetsError(f"Budgets answered {response.status}")
                return await response.json()
        except (aiohttp.ClientError, TimeoutError) as error:
            raise BudgetsError(f"Could not reach Budgets: {error}") from error
