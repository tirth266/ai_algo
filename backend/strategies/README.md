# Strategies

Add new strategy files here. Each strategy must:
1. Inherit from BaseStrategy
2. Implement generate_signal(candles: pd.DataFrame) -> Optional[str]
3. Be registered in the strategy manager

## Template
```python
from .base_strategy import BaseStrategy
import pandas as pd
from typing import Optional


class MyStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(name="MyStrategy", capital=25000.0)

    def generate_signal(self, candles: pd.DataFrame) -> Optional[str]:
        # your logic here
        return None
```
