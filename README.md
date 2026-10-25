# Budgets for Home Assistant

A Home Assistant integration for [Budgets](https://budgets.hrmis.dk), a personal finance app for households. It shows your accounts, your month, payday and the bank connection as sensors, and fires events for new transactions and salaries so automations can react to them.

Home Assistant never talks to your bank. Banks allow only about four fetches a day without you present (PSD2), and Budgets is the one place that fetches, four times a day. This integration polls Budgets' read-only API, which answers from Budgets' own database, so polling costs your bank nothing.

## Install

1. In HACS, open the menu → **Custom repositories**, add `https://github.com/Tobiasmidskards/budgets-homeassistant` as an **Integration**, and download **Budgets**.
2. Restart Home Assistant.
3. In Budgets, open **Settings → Integrations** and create a token. It can only read.
4. In Home Assistant, go to **Settings → Devices & services → Add integration → Budgets**, and enter the address of your Budgets app and the token. If you are in more than one household, pick one. Add the integration again for another household.

When the token expires or is deleted, Home Assistant asks for a new one.

## Entities

The household gets a device with these sensors. "My month" is the month of the person who created the token, on their own everyday account.

| Sensor | What it is |
| --- | --- |
| Total balance | All accounts that count in the total |
| Left this month | Room minus spent so far (attributes: room, spent, income, transfers, bills still due) |
| Spent this month, Room this month | From Budgets' month, which starts on payday |
| Per day | What is left per day for the rest of the month |
| Month-end forecast | Where the own account is expected to end the month (attributes: low, high, projected spending) |
| Days until payday, Payday | From the household's budget months |
| Last salary | When the last salary came (attributes: amount, account) |
| Last bank sync, Next bank sync | When Budgets fetched and fetches next |
| Bank consent days left | Until the bank consent has to be renewed in Budgets |
| Left over per month, Buffer in months, Fixed expenses share | Budgets' key figures |

Each bank connection has a problem binary sensor. It turns on when the data is stale, the last fetch failed, the connection isn't active or the consent runs out within 14 days. A bank that has reached its daily limit doesn't turn it on: Budgets waits for its next window, and the sensor turns on only if the data goes stale meanwhile.

Each account gets a device with its balance as the main sensor. The balance's attributes include `stale`, `last_error`, `consent_days_remaining`, `change_today`, `change_yesterday` and when it was updated. The device also has Spent this month, Money in this month and Change today.

## Events

`budgets_transaction` fires once for every new transaction Budgets gets from the bank. Rows that Budgets keeps itself on accounts without a bank connection don't fire. The event data:

```yaml
transaction_id: 901
booked_on: "2026-11-10"
status: booked            # or pending
description: ELGIGANTEN
counterparty: null
amount: -2499.0           # in the account's currency, negative is money out
currency: DKK
household_amount: -2499.0 # in the household's currency
account_id: 3
account_name: Min konto
account_role: spending    # budget, shared, savings, investment, credit_card, loan or null
account_balance: 1830.5
category: Electronics     # "Main › Sub" for a subcategory, null while uncategorized
category_type: expense    # income, savings, transfer, wealth or null
is_salary: false
counts_in_budget: true
household_id: 7
```

`budgets_salary_received` fires when a new salary lands on your own account, with `transaction_id`, `date`, `amount`, `currency`, `account_id`, `account_name`, `balance` and `household_id`.

When the integration is set up, it notes the latest transaction and salary. History is never replayed as events, and a restart neither repeats nor misses events.

### Example: big expenses

```yaml
triggers:
  - trigger: event
    event_type: budgets_transaction
conditions:
  - condition: template
    value_template: "{{ trigger.event.data.household_amount <= -2000 }}"
actions:
  - action: notify.notify
    data:
      title: "Big expense: {{ trigger.event.data.amount | round(0) }} kr"
      message: "{{ trigger.event.data.description }} on {{ trigger.event.data.account_name }}"
```

## Development

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements_test.txt
.venv/bin/python -m pytest
```

Budgets shows the API's address and creates its tokens under Settings → Integrations. This repository holds only the integration, never data or tokens.
