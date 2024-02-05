# reports/financial_statement.py
# Copyright (C) 2024 - 2028 the PythonAccounting authors and contributors
# <see AUTHORS file>
#
# This module is part of PythonAccounting and is released under
# the MIT License: https://www.opensource.org/licenses/mit-license.php

"""
Represents an abstraction of a financial statement according to IFRS/GAAP.

"""
from datetime import datetime
from strenum import StrEnum
from sqlalchemy.orm.session import Session
from python_accounting.config import config as configuration
from python_accounting.models import Account


class FinancialStatement:
    """
    This class is an abstract representation of a Financial Statement as defined by IFRS and GAAP
    
    Attributes:
        config (str): The configuration section for the report.
        end_date (datetime): The latest transaction date for Transaction amounts to be included
            in the report.
        printout (tuple): The sections to be printed out.
        width (int): The width of the report printout.
        indent (str): The indent between report sections.
        subtotal (str): The underline for report subtotals.
        grandtotal (str): The underline for report grand totals.

    """

    config: dict
    end_date: datetime

    # printing
    printout: tuple
    width: str
    indent: str = " " * configuration.reports["indent_length"]
    subtotal: str = "_" * configuration.reports["result_length"]
    grandtotal: str = "=" * configuration.reports["result_length"]

    def __init__(self, session: Session) -> None:
        self.session = session
        self.title = configuration.reports[self.config]["title"]

        # Financial Statement Sections
        self.sections = StrEnum(
            "Sections",
            {k: v["label"] for k, v in configuration.reports[self.config]["sections"].items()},
        )

        # Financial Statement Results
        self.results = StrEnum(
            "Results",
            {k: v for k, v in configuration.reports[self.config]["results"].items()},
        )

        self.section_names = [section.name for section in self.sections]
        self.accounts = {k: {} for k in self.section_names}
        self.balances = {k: {} for k in self.section_names}
        self.totals = {k: 0 for k in self.section_names}
        self.result_amounts = {}

        self.balances.update({"debit": 0, "credit": 0})

    def __str__(self) -> str:
        template = "{}\n" * len(self.printout)
        return template.format(*self.printout)

    def _get_sections(
        self,
        start_date: datetime = None,
        end_date: datetime = None,
        full_balance: bool = True,
    ) -> None:
        for section, content in configuration.reports[self.config]["sections"].items():
            for account_type in content["account_types"]:
                balances = Account.section_balances(
                    self.session, [account_type], start_date, end_date, full_balance
                )
                account_type = Account.AccountType[account_type].value
                if balances["closing"] != 0:
                    self.accounts[section][account_type] = balances["categories"]
                    self.balances[section][account_type] = balances["closing"]
                    self.totals[section] += balances["closing"]
                    self.balances[
                        "debit" if balances["closing"] >= 0 else "credit"
                    ] += balances["closing"]

    def _print_title(self) -> str:
        period = (
            f"""For the period: {self.start_date.strftime(configuration.dates["long"])}
             to {self.end_date.strftime(configuration.dates["long"])}"""
            if hasattr(self, "start_date")
            else f"As at {self.end_date.strftime(configuration.dates["long"])}"
        )
        self.width = max(len(period), 45)
        return f"""\n{self.session.entity.name.center(self.width)}\n
{self.title.center(self.width)}\n
{period.center(self.width)}"""
    
    def _print_section(self, section, factor = 1) -> str:
        content = f"\n{section.value}"

        for account_type, balance in self.balances[section.name].items():
            label = f"\n{self.indent}{account_type}" 
            content += f"{label}{balance * factor:>{self.width - len(label) + 1}}"
        return content

    def _print_result(self, result, grandtotal = False) -> str:
        return f"""{f"{self.subtotal:>{self.width}}"}\n
{result}{f"{self.result_amounts[result.name]:>{self.width - len(result)}}"}\n
{f"{self.grandtotal:>{self.width}}" if grandtotal else ""}"""
    

    def _print_total(self, section, factor = 1, grandtotal = False) -> str:
        label = f"Total {section.value}"
        return f"""{f"{self.subtotal:>{self.width}}"}\n
{label}{f"{self.totals[section.name] * factor:>{self.width - len(label)}}"}\n
{f"{self.grandtotal:>{self.width}}" if grandtotal else ""}"""
