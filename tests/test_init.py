"""Setting up an entry: sensors from the summary, events for new transactions and salaries, and an expired token."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_capture_events, async_fire_time_changed
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.budgets.const import EVENT_SALARY, EVENT_TRANSACTION, UPDATE_INTERVAL

from .conftest import API, money, transaction


async def set_up(hass: HomeAssistant, config_entry) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def poll(hass: HomeAssistant) -> None:
    async_fire_time_changed(hass, dt_util.utcnow() + UPDATE_INTERVAL + timedelta(seconds=1))
    await hass.async_block_till_done()


def entity_id(hass: HomeAssistant, key: str) -> str:
    registry = er.async_get(hass)
    return next(entry.entity_id for entry in registry.entities.values() if entry.unique_id.endswith(key))


def mock_summary(aioclient_mock: AiohttpClientMocker, summary: dict[str, Any]) -> None:
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{API}/households/7", json=summary)


async def test_adds_sensors_for_the_household_and_each_account(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, config_entry, summary
) -> None:
    mock_summary(aioclient_mock, summary)

    await set_up(hass, config_entry)

    balance = hass.states.get(entity_id(hass, "account-3-balance"))
    assert balance.state == "1830.5"
    assert balance.attributes["unit_of_measurement"] == "DKK"
    assert balance.attributes["device_class"] == "monetary"
    assert balance.attributes["stale"] is False
    assert balance.attributes["consent_days_remaining"] == 162
    assert balance.attributes["change_today"] == -120.5
    assert balance.attributes["change_yesterday"] == -310
    assert balance.name == "Min konto"

    assert hass.states.get(entity_id(hass, "account-3-spent_this_month")).state == "2309.34"
    assert hass.states.get(entity_id(hass, "#7-left_this_month")).state == "4190.66"
    assert hass.states.get(entity_id(hass, "#7-per_day")).state == "246.51"
    assert hass.states.get(entity_id(hass, "#7-month_end_forecast")).state == "1463"
    assert hass.states.get(entity_id(hass, "#7-days_until_payday")).state == "17"
    assert hass.states.get(entity_id(hass, "#7-payday")).state == "2026-11-27"
    assert hass.states.get(entity_id(hass, "#7-next_sync")).state == "2026-11-10T16:00:00+00:00"
    assert hass.states.get(entity_id(hass, "#7-fixed_expenses_share")).state == "48.0"
    assert hass.states.get(entity_id(hass, "connection-3")).state == "off"

    devices = {
        identifier: device
        for device in dr.async_entries_for_config_entry(dr.async_get(hass), config_entry.entry_id)
        for _, identifier in device.identifiers
    }
    account = devices["https://budgets.example.com#7-account-3"]
    assert account.name == "Min konto"
    assert account.model == "Everyday account"
    assert account.via_device_id == devices["https://budgets.example.com#7"].id


async def test_keeps_an_account_sensor_when_it_is_renamed(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, config_entry, summary
) -> None:
    mock_summary(aioclient_mock, summary)
    await set_up(hass, config_entry)

    er.async_get(hass).async_update_entity(
        entity_id(hass, "#7-account-3-balance"), new_entity_id="sensor.budgets_min_konto"
    )
    await hass.async_block_till_done()

    assert hass.states.get("sensor.budgets_min_konto").state == "1830.5"


async def test_fires_an_event_for_each_new_transaction_but_not_for_history(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, config_entry, summary
) -> None:
    mock_summary(aioclient_mock, summary)
    events = async_capture_events(hass, EVENT_TRANSACTION)
    await set_up(hass, config_entry)

    assert events == []

    summary["latest_transaction_id"] = 903
    mock_summary(aioclient_mock, summary)
    aioclient_mock.get(
        f"{API}/households/7/transactions",
        json={
            "transactions": [
                transaction(901, -2499.0, description="ELGIGANTEN"),
                transaction(902, 500.0, account={"id": 9, "name": "Savings"}, mirrors_transaction_id=880),
                transaction(903, -35.0),
            ],
            "latest_id": 903,
            "has_more": False,
        },
    )
    await poll(hass)

    assert [event.data["transaction_id"] for event in events] == [901, 903]
    assert events[0].data["amount"] == -2499.0
    assert events[0].data["description"] == "ELGIGANTEN"
    assert events[0].data["account_name"] == "Min konto"
    assert events[0].data["account_role"] == "spending"
    assert events[0].data["category_type"] == "expense"
    assert aioclient_mock.mock_calls[-1][1].query["after"] == "900"

    # Nothing new: no request for transactions, no events.
    mock_summary(aioclient_mock, summary)
    await poll(hass)

    assert len(events) == 2
    assert all("transactions" not in str(call[1]) for call in aioclient_mock.mock_calls)


async def test_fires_salary_received_once_for_a_new_salary(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, config_entry, summary
) -> None:
    mock_summary(aioclient_mock, summary)
    events = async_capture_events(hass, EVENT_SALARY)
    await set_up(hass, config_entry)

    summary["payday"]["last_salary"] = {
        "transaction_id": 950,
        "date": "2026-11-27",
        "amount": money(25500),
        "account_id": 3,
    }
    mock_summary(aioclient_mock, summary)
    await poll(hass)
    await poll(hass)

    assert len(events) == 1
    assert events[0].data == {
        "household_id": 7,
        "transaction_id": 950,
        "date": "2026-11-27",
        "amount": 25500,
        "currency": "DKK",
        "account_id": 3,
        "account_name": "Min konto",
        "balance": 1830.5,
    }


async def test_remembers_where_the_events_got_to_across_a_restart(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, config_entry, summary
) -> None:
    mock_summary(aioclient_mock, summary)
    events = async_capture_events(hass, EVENT_TRANSACTION)
    await set_up(hass, config_entry)
    assert await hass.config_entries.async_unload(config_entry.entry_id)

    summary["latest_transaction_id"] = 901
    mock_summary(aioclient_mock, summary)
    aioclient_mock.get(
        f"{API}/households/7/transactions",
        json={"transactions": [transaction(901, -10.0)], "latest_id": 901, "has_more": False},
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert [event.data["transaction_id"] for event in events] == [901]


async def test_reports_a_problem_when_the_bank_data_is_stale(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, config_entry, summary
) -> None:
    summary["sync"]["connections"][0] |= {"stale": True, "last_error": "Consent expired"}
    mock_summary(aioclient_mock, summary)

    await set_up(hass, config_entry)

    problem = hass.states.get(entity_id(hass, "connection-3"))
    assert problem.state == "on"
    assert problem.attributes["last_error"] == "Consent expired"
    assert problem.name == "Home Jyske Bank connection"


async def test_waits_quietly_while_the_bank_has_reached_its_daily_limit(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, config_entry, summary
) -> None:
    summary["sync"]["connections"][0] |= {
        "last_error": "The bank's limit is reached",
        "rate_limited_until": "2026-11-10T16:00:00+00:00",
    }
    mock_summary(aioclient_mock, summary)

    await set_up(hass, config_entry)

    problem = hass.states.get(entity_id(hass, "connection-3"))
    assert problem.state == "off"
    assert problem.attributes["rate_limited_until"] == "2026-11-10T16:00:00+00:00"


async def test_asks_for_a_new_token_when_budgets_refuses_the_old_one(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, config_entry, summary
) -> None:
    mock_summary(aioclient_mock, summary)
    await set_up(hass, config_entry)

    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{API}/households/7", status=401)
    await poll(hass)

    flows = hass.config_entries.flow.async_progress()
    assert [flow["context"]["source"] for flow in flows] == ["reauth"]
    assert config_entry.state is ConfigEntryState.LOADED


async def test_retries_setup_when_budgets_is_down(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, config_entry
) -> None:
    aioclient_mock.get(f"{API}/households/7", status=503)
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.SETUP_RETRY
