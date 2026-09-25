from __future__ import annotations

from decimal import Decimal
from typing import Any, Protocol

import httpx

from app.verification.config import VerificationSettings
from app.verification.exceptions import ProviderConfigurationError, ProviderError


class PlaidProvider(Protocol):
    async def create_link_token(self, client_user_id: str) -> dict[str, Any]: ...

    async def exchange_public_token(self, public_token: str) -> dict[str, str]: ...

    async def get_balances(self, access_token: str) -> list[dict[str, Any]]: ...


class PlaidClient:
    def __init__(self, settings: VerificationSettings) -> None:
        self.settings = settings
        hosts = {
            "sandbox": "https://sandbox.plaid.com",
            "development": "https://development.plaid.com",
            "production": "https://production.plaid.com",
        }
        try:
            self.base_url = hosts[settings.plaid_environment.lower()]
        except KeyError as exc:
            raise ProviderConfigurationError("Invalid Plaid environment") from exc

    def _credentials(self) -> dict[str, str]:
        if not self.settings.plaid_client_id or not self.settings.plaid_secret:
            raise ProviderConfigurationError("Plaid is not configured")
        return {
            "client_id": self.settings.plaid_client_id,
            "secret": self.settings.plaid_secret,
        }

    async def create_link_token(self, client_user_id: str) -> dict[str, Any]:
        return await self._post(
            "/link/token/create",
            {
                **self._credentials(),
                "client_name": "MatchBook",
                "language": "en",
                "country_codes": ["US"],
                "products": ["auth"],
                "user": {"client_user_id": client_user_id},
            },
        )

    async def exchange_public_token(self, public_token: str) -> dict[str, str]:
        data = await self._post(
            "/item/public_token/exchange",
            {**self._credentials(), "public_token": public_token},
        )
        if not data.get("access_token") or not data.get("item_id"):
            raise ProviderError("Plaid token exchange returned invalid output")
        return {
            "access_token": str(data["access_token"]),
            "item_id": str(data["item_id"]),
        }

    async def get_balances(self, access_token: str) -> list[dict[str, Any]]:
        data = await self._post(
            "/accounts/balance/get",
            {**self._credentials(), "access_token": access_token},
        )
        accounts = data.get("accounts")
        if not isinstance(accounts, list):
            raise ProviderError("Plaid balances returned invalid output")
        return accounts

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=20.0,
            ) as client:
                response = await client.post(path, json=payload)
                response.raise_for_status()
                data = response.json()
        except ProviderConfigurationError:
            raise
        except Exception as exc:
            raise ProviderError("Plaid request failed") from exc
        if not isinstance(data, dict):
            raise ProviderError("Plaid returned invalid output")
        return data


def eligible_depository_balance(
    accounts: list[dict[str, Any]],
) -> tuple[Decimal, int]:
    total = Decimal("0")
    count = 0
    for account in accounts:
        if account.get("type") != "depository":
            continue
        balances = account.get("balances") or {}
        amount = balances.get("available")
        if amount is None:
            amount = balances.get("current")
        if amount is None:
            continue
        value = Decimal(str(amount))
        total += value
        count += 1
    return max(total, Decimal("0")), count
