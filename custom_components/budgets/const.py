"""Constants for the Budgets integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "budgets"

CONF_HOUSEHOLD_ID: Final = "household_id"

# Budgets answers from its own database and never calls the bank on our behalf, so polling is cheap. The bank data
# itself only changes when Budgets syncs (four times a day), so there is no point in polling much more often.
UPDATE_INTERVAL: Final = timedelta(minutes=5)

# How many transactions one request asks for while catching up.
TRANSACTIONS_PAGE: Final = 100

EVENT_TRANSACTION: Final = "budgets_transaction"
EVENT_SALARY: Final = "budgets_salary_received"

STORAGE_VERSION: Final = 1
