from abc import ABC, abstractmethod
from typing import Optional
import pandas as pd


class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies.
    Every strategy must implement generate_signal().
    """

    def __init__(self, name: str, capital: float = 25000.0):
        self.name = name
        self.capital = capital

    @abstractmethod
    def generate_signal(self, candles: pd.DataFrame) -> Optional[str]:
        """
        Given a DataFrame of OHLCV candles, return:
          'BUY'  - enter long
          'SELL' - exit / enter short
          None   - no signal
        """
        pass

    def get_quantity(self, price: float) -> int:
        """Default position sizing: capital / price."""
        return max(1, int(self.capital / price))
