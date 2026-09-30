"""Inventory domain models — realistic module for pyreorder examples.

This file showcases two features working together:

* **``alpha`` strategy** on ``enums`` and ``functions`` — stable alphabetical
  ordering, which is ideal when there's no caller/callee dependency to
  preserve.
* **Rich undersort** — the ``Product`` class contains methods spanning every
  visibility (public / protected / private) and type (instance / class /
  static), so pyreorder's in-class reordering is easy to see.

Run::

    pyreorder diff tests/data/inventory_models_unsorted.py
    pyreorder run  tests/data/inventory_models_unsorted.py

The authoritative output (``inventory_models_sorted.py``) was generated with
``Config(strategies={"enums": "alpha", "functions": "alpha"})``.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

TAX_RATE = Decimal("0.20")
MAX_SKU_LENGTH = 16
CURRENCY = "EUR"


class Category(enum.Enum):
    BOOKS = "books"
    ELECTRONICS = "electronics"
    FOOD = "food"
    TOYS = "toys"


class Warehouse(enum.Enum):
    CENTRAL = "central"
    NORTH = "north"
    SOUTH = "south"
    WEST = "west"
    EAST = "east"


@dataclass
class Price:
    """A money value with currency."""

    amount: Decimal
    currency: str = CURRENCY

    def with_tax(self) -> Decimal:
        return self.amount * (Decimal("1") + TAX_RATE)


class Product:
    """A product with rich method ordering for undersort demonstration."""

    def __init__(self, sku: str, name: str, price: Price) -> None:
        self.sku = sku
        self.name = name
        self.price = price
        self._stock: dict[Warehouse, int] = {}
        self.__margin = Decimal("0.30")

    def total_value(self) -> Decimal:
        """Total stock value across all warehouses."""
        count = sum(self._stock.values())
        return self.price.amount * count

    def display_name(self) -> str:
        """Human-readable label."""
        return f"{self.name} ({self.sku})"

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> Product:
        """Build a :class:`Product` from a plain dict."""
        price = Price(Decimal(data["price"]))
        return cls(data["sku"], data["name"], price)

    @staticmethod
    def is_valid_sku(sku: str) -> bool:
        """Check whether *sku* meets the formatting rules."""
        return bool(sku) and len(sku) <= MAX_SKU_LENGTH

    def _set_stock(self, warehouse: Warehouse, qty: int) -> None:
        self._stock[warehouse] = qty

    def _total_stock(self) -> int:
        return sum(self._stock.values())

    @classmethod
    def _default_margin(cls) -> Decimal:
        return Decimal("0.30")

    @staticmethod
    def _round_cents(value: Decimal) -> Decimal:
        return value.quantize(Decimal("0.01"))

    def __update_margin(self, value: Decimal) -> None:
        object.__setattr__(self, "_Product__margin", value)

    def __recalculate(self) -> None:
        self.__update_margin(self.price.amount * Decimal("0.1"))


def format_price(price: Price) -> str:
    """Format *price* as a currency string."""
    return f"{price.amount:.2f} {price.currency}"


def calculate_tax(amount: Decimal) -> Decimal:
    """Return the tax component of *amount*."""
    return amount * TAX_RATE


def aggregate_stock(products: list[Product]) -> int:
    """Sum the total stock across all *products*."""
    return sum(p._total_stock() for p in products)


def find_by_sku(products: list[Product], sku: str) -> Product | None:
    """Linear search for a product by *sku*."""
    for product in products:
        if product.sku == sku:
            return product
    return None


def main() -> None:
    """Demonstrate creating and querying products."""
    chair = Product("CHR-001", "Office Chair", Price(Decimal("199.00")))
    desk = Product.from_dict({"sku": "DSK-001", "name": "Standing Desk", "price": "450.00"})
    catalog = [chair, desk]
    print(f"catalog size: {len(catalog)}")
    print(format_price(chair.price))
    print(f"total stock: {aggregate_stock(catalog)}")


if TYPE_CHECKING:
    import uuid  # noqa: F401


if __name__ == "__main__":
    main()
