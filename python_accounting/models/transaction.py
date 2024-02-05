# models/transaction.py
# Copyright (C) 2024 - 2028 the PythonAccounting authors and contributors
# <see AUTHORS file>
#
# This module is part of PythonAccounting and is released under
# the MIT License: https://www.opensource.org/licenses/mit-license.php

"""
Represents a financial Transaction.

"""
from typing import List, Set
from datetime import datetime
from decimal import Decimal
from strenum import StrEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from sqlalchemy import (
    String,
    ForeignKey,
    Enum,
    Boolean,
    Text,
    func,
    UniqueConstraint,
    inspect,
)
from sqlalchemy.types import DECIMAL
from python_accounting.mixins import IsolatingMixin
from python_accounting.config import config
from python_accounting.exceptions import (
    InvalidTransactionDateError,
    ClosedReportingPeriodError,
    AdjustingReportingPeriodError,
    RedundantTransactionError,
    MissingLineItemError,
    PostedTransactionError,
    InvalidTransactionTypeError,
)
from python_accounting.models import Recyclable, Account, ReportingPeriod, LineItem


class Transaction(IsolatingMixin, Recyclable):
    """
    Represents a Transaction in the sense of an original source document.

    Attributes:
        TransactionType (StrEnum): Transaction Types representing common
            Transaction.
        id (int): The primary key of the Transaction database record.
        transaction_date (datetime): The date of the Transaction.
        transaction_type (TransactionType): The Transaction type of the Transaction.
        narration (str): A short description of the purpose of the Transaction.
        reference (:obj:`str`, optional): Identifying information about the Transaction.
        main_account_amount (:obj:`Decimal`, optional): The amount to be posted to the Transaction
            main Account. Only applies to compound (Journal Entry) Transactions.
        credited (:obj:`bool`, optional): Determines whether the Transaction amount will
            be posted to the credit side of the main Account. Defaults to True.
        compound (:obj:`bool`, optional): Determines whether the (Journal Entry) Transaction amount
            can have Line Items on both sides of the double entry.
        currency_id (int): The id of the Currency associated with the Transaction.
        account_id (int): The id of the Account model to which Transaction amounts are to be posted.

    """

    # Transaction types
    TransactionType = StrEnum(
        "TransactionType",
        {k: v["label"] for k, v in config.transactions["types"].items()},
    )

    __table_args__ = (UniqueConstraint("transaction_no", "entity_id"),)
    __tablename__ = "transaction"
    __mapper_args__ = {
        "polymorphic_identity": "Transaction",
    }

    id: Mapped[int] = mapped_column(ForeignKey("recyclable.id"), primary_key=True)
    transaction_date: Mapped[datetime] = mapped_column()
    transaction_no: Mapped[str] = mapped_column(String(255), nullable=True)
    transaction_type: Mapped[StrEnum] = mapped_column(Enum(TransactionType))
    narration: Mapped[str] = mapped_column(Text(1000))
    reference: Mapped[str] = mapped_column(String(255), nullable=True)
    main_account_amount: Mapped[Decimal] = mapped_column(
        DECIMAL(precision=13, scale=4), default=0
    )
    credited: Mapped[bool] = mapped_column(Boolean, default=True)
    compound: Mapped[bool] = mapped_column(Boolean, default=False)
    currency_id: Mapped[int] = mapped_column(ForeignKey("currency.id"))
    account_id: Mapped[int] = mapped_column(ForeignKey("account.id"))

    # relationships
    currency: Mapped["Currency"] = relationship(foreign_keys=[currency_id])
    account: Mapped["Account"] = relationship(foreign_keys=[account_id])
    line_items: Mapped[Set["LineItem"]] = relationship(
        back_populates="transaction",
        primaryjoin="Transaction.id==LineItem.transaction_id",
    )
    ledgers: Mapped[List["Ledger"]] = relationship(
        back_populates="transaction",
        primaryjoin="Transaction.id==Ledger.transaction_id",
    )

    @validates("line_items", include_removes=True)
    def validate_line_items(self, key, line_item, is_remove):
        """validates adding or removing of Transaction Line Items."""
        if hasattr(self, "_validate_subclass_line_items"):
            self._validate_subclass_line_items(line_item)

        if self.is_posted:
            raise PostedTransactionError(
                f"Cannot {'Remove' if is_remove else 'Add'} Line Items from a Posted Transaction."
            )

        if line_item.id is None:
            raise ValueError(
                "Line Item must be persisted to be added to the Transaction."
            )

        if not self.compound and line_item.credited == self.credited:
            line_item.credited = not self.credited
        return line_item

    @validates("ledgers", include_removes=True)
    def validate_ledgers(self, key, ledger, is_remove):
        """validates adding or removing of Line Item Ledgers"""
        raise ValueError(
            f"Transaction ledgers cannot be {'Removed' if is_remove else 'Added'} manually."
        )

    @property
    def tax(self) -> dict:
        """The taxes that have been applied to the transaction."""
        taxes = dict()
        total = 0
        for line_item in iter(self.line_items):
            if line_item.tax_id:
                amount = (
                    line_item.tax.rate * line_item.amount * line_item.quantity / 100
                )
                total += amount
                if (
                    line_item.tax.code
                    in taxes.keys()  # pylint: disable=consider-iterating-dictionary
                ):
                    taxes[line_item.tax.code]["amount"] += amount
                else:
                    taxes.update(
                        {
                            line_item.tax.code: dict(
                                name=line_item.tax.name,
                                rate=f"{round(line_item.tax.rate, 2)}%",
                                amount=amount,
                            )
                        }
                    )
        return dict(total=total, taxes=taxes)

    @property
    def is_posted(self) -> Decimal:
        """If the Transaction has been posted to the ledge.r"""
        return len(self.ledgers) > 0

    @property
    def amount(self) -> Decimal:
        """The amount of the Transaction."""

        return sum(
            [
                l.amount * l.quantity
                + (
                    (l.amount * l.quantity * l.tax.rate / 100)
                    if l.tax_id and not l.tax_inclusive
                    else 0
                )
                for l in iter(self.line_items)
                if l.credited != self.credited
            ]
        )

    def __repr__(self) -> str:
        return f"{self.account} <{self.transaction_no}>: {self.amount}"

    def _get_main_account(self, session) -> Account:
        """Retrieve the main account of the tranaction from the database."""
        account = session.get(Account, self.account_id)
        if not account:
            raise ValueError("The main Account is required")
        return account

    def _transaction_no(self, session, transaction_type, reporting_period) -> str:
        """Get the next auto-generated transaction number."""
        next_id = (
            session.query(Transaction)
            .filter(Transaction.transaction_type == transaction_type)
            .filter(Transaction.transaction_date > reporting_period.interval()["start"])
            .with_entities(func.count())  # pylint: disable=not-callable
            .execution_options(include_deleted=True)
            .filter(Transaction.entity_id == self.entity_id)
            .scalar()
        ) + getattr(self, "session_index", 1)

        prefix = config.transactions["types"][transaction_type.name][
            "transaction_no_prefix"
        ]
        return f"{prefix}{reporting_period.period_count:02}/{next_id:04}"

    def post(self, session) -> None:
        """
        Posts the Transaction to the Ledger.

        Args:
            session (Session): The accounting session to which the Reporting Period
                 belongs.

        Raises:
            MissingLineItemError: If the Transaction has no Line Items.


        Returns:
            None

        """
        from python_accounting.models import (  # pylint: disable=import-outside-toplevel
            Ledger,
        )

        if not self.line_items:
            raise MissingLineItemError

        session.flush()
        Ledger.post(session, self)

    def contribution(self, session, account: Account) -> Decimal:
        """
        Gets the amount contributed by the account to the transaction total.

        Args:
            session (Session): The accounting session to which the Reporting Period
                 belongs.
            account (Account): The Account who's contribution is to be found.

        Returns:
            Decimal: The amount posted to the Account by the Transaction.

        """
        from python_accounting.models import (  # pylint: disable=import-outside-toplevel
            Balance,
            Ledger,
        )

        query = (
            session.query(
                func.sum(Ledger.amount).label("amount")  # pylint: disable=not-callable
            )
            .filter(Ledger.entity_id == self.entity_id)
            .filter(Ledger.transaction_id == self.id)
            .filter(Ledger.currency_id == self.currency_id)
            .filter(Ledger.post_account_id == account.id)
        )
        return (
            query.filter(Ledger.entry_type == Balance.BalanceType.DEBIT).scalar()
            or 0
            - query.filter(Ledger.entry_type == Balance.BalanceType.CREDIT).scalar()
            or 0
        )

    def validate(self, session) -> None:
        """
        Validates the Transaction properties.

        Args:
            session (Session): The accounting session to which the Balance belongs.

        Raises:
            PostedTransactionError: If Transaction is already posted.
            ClosedReportingPeriodError: If the Transaction date is with a Reporting Period
                in the CLOSED status.
            AdjustingReportingPeriodError: If the Transaction date is with a Reporting Period
                in the ADJUSTING status and is not a Journal Entry.
            InvalidTransactionDateError: If the Transaction date is exactly the beginning of
                the Reporting Period.
            InvalidTransactionTypeError: If the Transaction type is being modified.
            RedundantTransactionError: If the Transaction main Account is also one of its
                Line Items Accounts.

        Returns:
            None

        """

        if self.is_posted:
            raise PostedTransactionError("A Posted Transaction cannot be modified.")

        account = self._get_main_account(session)

        reporting_period = ReportingPeriod.get_period(
            session,
            self.transaction_date,
        )
        self.currency_id = account.currency_id

        if reporting_period.status == ReportingPeriod.Status.CLOSED:
            raise ClosedReportingPeriodError(reporting_period)

        if (
            reporting_period.status == ReportingPeriod.Status.ADJUSTING
            and self.transaction_type != Transaction.TransactionType.JOURNAL_ENTRY
        ):
            raise AdjustingReportingPeriodError(reporting_period)

        if (
            self.transaction_date
            and self.transaction_date == reporting_period.interval()["start"]
        ):
            raise InvalidTransactionDateError

        if self.id and len(inspect(self).attrs.transaction_type.history.deleted) > 0:
            raise InvalidTransactionTypeError

        if not self.transaction_no:
            self.transaction_no = self._transaction_no(
                session, self.transaction_type, reporting_period
            )

        for line_item in self.line_items:
            if line_item.account_id == self.account_id:
                raise RedundantTransactionError(line_item)

    def validate_delete(self, _) -> None:
        """
        Validates if the Transaction can be deleted.

        Args:
            session (Session): The accounting session to which the Balance belongs.

        Raises:
            PostedTransactionError: If Transaction is already posted.

        Returns:
            None

        """

        if self.is_posted:
            raise PostedTransactionError("A Posted Transaction cannot be deleted.")
