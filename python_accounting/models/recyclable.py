# models/recyclable.py
# Copyright (C) 2024 - 2028 the PythonAccounting authors and contributors
# <see AUTHORS file>
#
# This module is part of PythonAccounting and is released under
# the MIT License: https://www.opensource.org/licenses/mit-license.php

"""
Represents an interface that relates recycled objects with the recycled models.

"""

from datetime import datetime
from typing import List
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String
from python_accounting.models import Base


class Recyclable(Base):
    """
    Interface for associating recycled objects with its models.

    Attributes:
        deleted_at (:obj:`datetime`, optional): The time the model was recycled.
        destroyed_at (:obj:`datetime`, optional): The time the model was recycled
            permanently deleted.
        recycled_type (str): The class name of the recycled model.
    """

    deleted_at: Mapped[datetime] = mapped_column(nullable=True)
    destroyed_at: Mapped[datetime] = mapped_column(nullable=True)
    recycled_type: Mapped[str] = mapped_column(String(255))

    # relationships
    history: Mapped[List["Recycled"]] = relationship()

    __mapper_args__ = {"polymorphic_on": recycled_type}
