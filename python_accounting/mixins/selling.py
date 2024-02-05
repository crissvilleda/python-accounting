# mixins/selling.py
# Copyright (C) 2024 - 2028 the PythonAccounting authors and contributors
# <see AUTHORS file>
#
# This module is part of PythonAccounting and is released under
# the MIT License: https://www.opensource.org/licenses/mit-license.php

"""
Provides functionality to Transactions that can sell goods and services for an Entity.

"""

from typing import Any
from python_accounting.mixins.trading import TradingMixin


class SellingMixin(TradingMixin):
    """
    This class provides validation for Transaction that sell goods and services for an Entity.

    Attributes:
        line_item_types (:obj:`list` of :obj:`Account.AccountType`): A list of Account
            Types that are allowed as Line Item accounts for selling Transactions.
        main_account_types (:obj:`list` of :obj:`Account.AccountType`): A list of Account
            Types that are allowed as main accounts for selling Transactions.
        account_type_map (:obj:`dict` of str : :obj:`Account.AccountType`): A mapping of
            Transactions to the Account Types that apply to their validation.

    """

    line_item_types: list
    main_account_types: list
    account_type_map: dict

    def __init__(self, **kw: Any) -> None:
        from python_accounting.models import (  # pylint: disable=import-outside-toplevel
            Account,
        )

        self.line_item_types: list = [Account.AccountType.OPERATING_REVENUE]

        self.account_type_map: dict = {
            "ClientInvoice": Account.AccountType.RECEIVABLE,
            "CreditNote": Account.AccountType.RECEIVABLE,
            "CashSale": Account.AccountType.BANK,
        }
        super().__init__(**kw)
