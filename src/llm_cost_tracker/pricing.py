from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from importlib.resources import files
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class ModelPrice:
    provider: str
    model: str
    input_price: Decimal
    output_price: Decimal
    source_url: str


class PriceCatalog:
    def __init__(self, prices: List[ModelPrice], unit_tokens: int) -> None:
        self.prices = prices
        self.unit_tokens = Decimal(unit_tokens)
        self._index: Dict[Tuple[str, str], ModelPrice] = {
            (price.provider, price.model): price for price in prices
        }

    @classmethod
    def load(cls) -> "PriceCatalog":
        path = files("llm_cost_tracker").joinpath("data/pricing.json")
        data = json.loads(path.read_text(encoding="utf-8"))
        prices = [
            ModelPrice(
                provider=item["provider"],
                model=item["model"],
                input_price=Decimal(item["input_price"]),
                output_price=Decimal(item["output_price"]),
                source_url=item["source_url"],
            )
            for item in data["models"]
        ]
        return cls(prices=prices, unit_tokens=data["unit_tokens"])

    def estimate(
        self,
        provider: str,
        model: str,
        input_tokens: Optional[int],
        output_tokens: Optional[int],
    ) -> Optional[Decimal]:
        price = self._index.get((provider, model))
        if price is None or input_tokens is None or output_tokens is None:
            return None
        cost = (
            Decimal(input_tokens) * price.input_price
            + Decimal(output_tokens) * price.output_price
        ) / self.unit_tokens
        return cost.quantize(Decimal("0.0000000001"))

