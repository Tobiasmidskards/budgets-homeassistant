"""The config flow: URL and token, choosing a household, and a new token when the old one stops working."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.budgets.const import CONF_HOUSEHOLD_ID, DOMAIN

from .conftest import API, TOKEN, URL

HOME = {"id": 7, "slug": "home", "name": "Home", "currency": "DKK", "is_current": True}
CABIN = {"id": 8, "slug": "cabin", "name": "Cabin", "currency": "DKK", "is_current": False}


async def start(hass: HomeAssistant, url: str = URL + "/settings/integrations") -> dict:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    return await hass.config_entries.flow.async_configure(result["flow_id"], {"url": url, "token": f" {TOKEN} "})


async def test_creates_the_entry_for_the_only_household(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(f"{API}/households", json={"households": [HOME]})

    result = await start(hass)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Home"
    assert result["data"] == {"url": URL, "token": TOKEN, CONF_HOUSEHOLD_ID: 7}
    assert result["result"].unique_id == f"{URL}#7"
    assert aioclient_mock.mock_calls[0][3]["Authorization"] == f"Bearer {TOKEN}"


async def test_asks_which_household_when_there_are_several(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(f"{API}/households", json={"households": [HOME, CABIN]})

    result = await start(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "household"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOUSEHOLD_ID: "8"})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Cabin"
    assert result["data"][CONF_HOUSEHOLD_ID] == 8


async def test_shows_an_error_for_a_rejected_token(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    aioclient_mock.get(f"{API}/households", status=403)

    result = await start(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_shows_an_error_when_budgets_cannot_be_reached(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(f"{API}/households", status=502)

    result = await start(hass)

    assert result["errors"] == {"base": "cannot_connect"}


async def test_aborts_for_a_household_already_set_up(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, config_entry
) -> None:
    config_entry.add_to_hass(hass)
    aioclient_mock.get(f"{API}/households", json={"households": [HOME]})

    result = await start(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_takes_a_new_token_when_the_old_one_stops_working(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, config_entry, summary
) -> None:
    config_entry.add_to_hass(hass)
    aioclient_mock.get(f"{API}/households", json={"households": [HOME]})
    aioclient_mock.get(f"{API}/households/7", json=summary)

    result = await config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"token": "new-token"})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data["token"] == "new-token"


async def test_refuses_a_new_token_for_another_user(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, config_entry
) -> None:
    config_entry.add_to_hass(hass)
    aioclient_mock.get(f"{API}/households", json={"households": [CABIN]})

    result = await config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"token": "someone-elses"})

    assert result["errors"] == {"base": "household_missing"}
    assert config_entry.data["token"] == TOKEN
