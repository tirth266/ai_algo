"""
Risk Management Configuration

Defines trading protection limits and safety controls.

Author: Quantitative Trading Systems Engineer
Date: March 17, 2026
"""

from config.settings import get_config


class RiskConfig:
    """
    Risk management configuration.
    
    Provides safety controls to protect capital:
    - Maximum trades per day
    - Maximum daily loss
    - Maximum open positions
    - Emergency kill switch
    """
    
    def __init__(self):
        """Initialize risk configuration."""
        self.config = get_config()
        
        # Daily limits
        self.max_trades_per_day = self.config.MAX_TRADES_PER_DAY
        self.max_daily_loss = self.config.MAX_DAILY_LOSS  # As fraction
        
        # Position limits
        self.max_open_positions = self.config.MAX_OPEN_POSITIONS
        self.capital_per_trade = self.config.CAPITAL_PER_TRADE
        
        # Risk per trade
        self.max_risk_per_trade = self.config.MAX_RISK_PER_TRADE
        self.stop_loss_percentage = self.config.STOP_LOSS_PERCENTAGE
        self.target_percentage = self.config.TARGET_PERCENTAGE
        
        # Portfolio risk
        self.max_portfolio_risk = self.config.MAX_PORTFOLIO_RISK
        
        # Kill switch
        self.trading_enabled = True
    
    def can_place_trade(self, current_trades: int, daily_pnl: float, 
                       open_positions: int) -> tuple:
        """
        Check if a new trade can be placed.
        
        Args:
            current_trades: Number of trades today
            daily_pnl: Current daily PnL
            open_positions: Number of open positions
        
        Returns:
            Tuple of (can_trade: bool, reason: str)
        """
        # Check kill switch
        if not self.trading_enabled:
            return False, "Trading disabled by kill switch"
        
        # Check daily trade limit
        if current_trades >= self.max_trades_per_day:
            return False, f"Daily trade limit reached ({self.max_trades_per_day})"
        
        # Check daily loss limit
        if daily_pnl < -(self.max_daily_loss * self.get_capital()):
            return False, f"Daily loss limit hit (₹{daily_pnl:.2f})"
        
        # Check position limit
        if open_positions >= self.max_open_positions:
            return False, f"Max open positions reached ({self.max_open_positions})"
        
        return True, "OK"
    
    def calculate_position_size(self, symbol_price: float) -> int:
        """
        Calculate position size based on risk.
        
        Args:
            symbol_price: Current price
        
        Returns:
            Quantity to trade
        """
        # Risk-based sizing
        risk_amount = self.capital_per_trade * self.max_risk_per_trade
        stop_loss_distance = symbol_price * (self.stop_loss_percentage / 100)
        
        quantity = int(risk_amount / stop_loss_distance)
        
        # Round to lot size (assuming 1 for simplicity)
        return max(1, quantity)
    
    def get_capital(self) -> float:
        """Get total trading capital."""
        return self.capital_per_trade * self.max_open_positions
    
    def enable_trading(self):
        """Enable trading (kill switch off)."""
        self.trading_enabled = True
    
    def disable_trading(self, reason: str = None):
        """Disable trading (kill switch on)."""
        self.trading_enabled = False
        if reason:
            print(f"🚨 KILL SWITCH ACTIVATED: {reason}")
    
    def is_trading_enabled(self) -> bool:
        """Check if trading is enabled."""
        return self.trading_enabled


# Global risk config instance
_risk_config = None


def get_risk_config() -> RiskConfig:
    """
    Get global risk configuration.
    
    Returns:
        RiskConfig instance
    """
    global _risk_config
    
    if _risk_config is None:
        _risk_config = RiskConfig()
    
    return _risk_config


if __name__ == "__main__":
    # Test risk config
    risk = get_risk_config()
    
    print("=" * 60)
    print("RISK CONFIGURATION TEST")
    print("=" * 60)
    
    print(f"\nMax Trades/Day: {risk.max_trades_per_day}")
    print(f"Max Daily Loss: {risk.max_daily_loss:.1%}")
    print(f"Max Open Positions: {risk.max_open_positions}")
    print(f"Capital/Trade: ₹{risk.capital_per_trade:,}")
    print(f"Stop Loss: {risk.stop_loss_percentage}%")
    print(f"Target: {risk.target_percentage}%")
    print(f"Trading Enabled: {risk.is_trading_enabled()}")
    
    # Test trade check
    can_trade, reason = risk.can_place_trade(
        current_trades=5,
        daily_pnl=-1000,
        open_positions=2
    )
    print(f"\nCan Place Trade: {can_trade} ({reason})")
