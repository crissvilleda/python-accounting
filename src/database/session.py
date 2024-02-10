# database/session.py
# Copyright (C) 2024 - 2028 the PythonAccounting authors and contributors
# <see AUTHORS file>
#
# This module is part of PythonAccounting and is released under
# the MIT License: https://www.opensource.org/licenses/mit-license.php

"""
Provides accounting specific overrides for some sqlalchemy session methods.

"""
from sqlalchemy.orm.session import Session

from src.models import Entity
from src.database.session_overrides import SessionOverridesMixin
from src.database.accounting_functions import AccountingFunctionsMixin
from src.database.event_listeners import EventListenersMixin


class AccountingSession(
    SessionOverridesMixin, EventListenersMixin, AccountingFunctionsMixin, Session
):
    """This class extends the standard SqlAlchemy session by providing custom methods
    specific to accounting.

    Attributes:
        entity (Entity): The Entity currently associated with the session. All database
            queries will be scoped to this entity.
    """

    entity: Entity

    def __init__(self, bind=None, info=None) -> None:
        super(AccountingSession, self).__init__(bind=bind, info=info)


def get_ession(engine) -> Session:
    """
    Construct the accounting session.

    Args:
        engine: The database engine to create a session for.

    Returns:
        AccountingSession.

    """

    return AccountingSession(
        bind=engine,
        info={
            "include_deleted": engine.get_execution_options().get(
                "include_deleted", False
            ),
            "ignore_isolation": engine.get_execution_options().get(
                "ignore_isolation", False
            ),
        },
    )