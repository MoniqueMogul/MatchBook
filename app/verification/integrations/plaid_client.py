import os
from typing import Any

import plaid
from plaid.api import plaid_api
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.accounts_balance_get_request import AccountsBalanceGetRequest

PLAID_CLIENT_ID = os.environ.get("PLAID_CLIENT_ID", "")
PLAID_SECRET = os.environ.get("PLAID_SECRET", "")
PLAID_ENV = os.environ.get("PLAID_ENV", "sandbox")

_configuration = plaid.Configuration(
    host=getattr(plaid.Environment, PLAID_ENV.capitalize()),
    api_key={"clientId": PLAID_CLIENT_ID, "secret": PLAID_SECRET},
)
_client = plaid_api.PlaidApi(plaid.ApiClient(_configuration))


async def create_link_token(buyer_id: str) -> str:
    request = LinkTokenCreateRequest(
        user=LinkTokenCreateRequestUser(client_user_id=buyer_id), client_name="Matchbook",
        products=["auth", "transactions"], country_codes=["US"], language="en",
    )
    response = _client.link_token_create(request)
    return response["link_token"]


async def exchange_public_token(public_token: str) -> str:
    request = ItemPublicTokenExchangeRequest(public_token=public_token)
    response = _client.item_public_token_exchange(request)
    return response["access_token"]


async def get_account_balances(access_token: str) -> list[dict[str, Any]]:
    request = AccountsBalanceGetRequest(access_token=access_token)
    response = _client.accounts_balance_get(request)
    return [
        {"account_type": account["type"], "balance": account["balances"]["available"] or account["balances"]["current"] or 0.0, "eligible": account["type"] in ("depository",)}
        for account in response["accounts"]
    ]