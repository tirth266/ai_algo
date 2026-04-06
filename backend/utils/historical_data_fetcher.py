"""
Historical Data Fetcher for Zerodha Kite

Fetches real historical data from Zerodha API and saves to CSV.
Avoids mock data issues and provides realistic market patterns.

Usage:
    python backend/utils/historical_data_fetcher.py
    
Configuration:
    - Symbol: NSE:NIFTY 50
    - Timeframe: 5 minute
    - Days: 90 days
    - Output: data/nifty50_90d.csv
"""

import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import logging
import sys

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from trading.zerodha_auth_web import get_zerodha_auth_web

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def fetch_nifty_historical_data(days=90, symbol="NSE:NIFTY 50", timeframe="5minute"):
    """
    Fetch real historical data from Zerodha Kite API.
    
    Args:
        days: Number of days of historical data (default: 90)
        symbol: Trading symbol (default: NSE:NIFTY 50)
        timeframe: Candle interval (default: 5minute)
    
    Returns:
        DataFrame with OHLCV data or None if failed
        
    Usage:
        df = fetch_nifty_historical_data(days=90)
        if df is not None:
            print(f"Fetched {len(df)} candles")
    """
    try:
        logger.info(f"Fetching {days} days of {timeframe} data for {symbol}")
        
        # Get auth instance
        auth = get_zerodha_auth_web()
        
        # Check if connected
        if not auth.is_connected():
            logger.error("Not connected to Zerodha. Please login first.")
            logger.info("\nTo connect:")
            logger.info("  1. Go to: http://localhost:3000/broker")
            logger.info("  2. Click 'Connect Broker'")
            logger.info("  3. Complete Zerodha login")
            return None
        
        # Get kite client
        kite = auth.kite
        
        if kite is None:
            logger.error("Kite client not initialized")
            return None
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        logger.info(f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        
        # Fetch historical data from Zerodha
        # Note: Using instrument_token for NIFTY 50
        # You may need to adjust this based on your broker's instrument master
        try:
            candles = kite.historical_data(
                instrument_token=get_instrument_token(symbol),
                from_date=start_date,
                to_date=end_date,
                interval=timeframe
            )
            
            logger.info(f"Fetched {len(candles)} candles from Zerodha API")
            
            if not candles:
                logger.warning("No data returned from API")
                return None
            
            # Convert to DataFrame
            df = pd.DataFrame(candles)
            
            # Ensure datetime column is proper format
            df['datetime'] = pd.to_datetime(df['date'], utc=True)
            
            # Set datetime as index
            df.set_index('datetime', inplace=True)
            
            # Sort by datetime
            df.sort_index(inplace=True)
            
            # Select only needed columns
            df = df[['open', 'high', 'low', 'close', 'volume']]
            
            logger.info(f"✅ Successfully fetched {len(df)} candles")
            logger.info(f"   Date Range: {df.index.min()} to {df.index.max()}")
            logger.info(f"   Price Range: ₹{df['close'].min():,.2f} to ₹{df['close'].max():,.2f}")
            
            return df
            
        except Exception as api_error:
            logger.error(f"API Error: {api_error}")
            
            # Check if it's a permissions issue
            error_str = str(api_error).lower()
            if 'permission' in error_str or 'subscription' in error_str:
                logger.error("\n⚠️  It appears you don't have historical data permissions")
                logger.error("   Contact Zerodha support to enable:")
                logger.error("     • Historical API access")
                logger.error("     • NIFTY 50 data subscription")
            return None
        
    except Exception as e:
        logger.error(f"Error fetching historical data: {e}", exc_info=True)
        return None


def get_instrument_token(symbol):
    """
    Get instrument token for a symbol.
    
    For NIFTY 50, the token is typically available in the instrument master.
    You can also hardcode it if needed.
    
    Common tokens:
        - NSE:NIFTY 50 -> Use appropriate token from instrument master
        - NSE:BANKNIFTY -> Use appropriate token from instrument master
    
    Args:
        symbol: Trading symbol string
    
    Returns:
        Instrument token (int)
    """
    # TODO: You should fetch the actual instrument master from Zerodha
    # For now, using placeholder - replace with actual token
    # Download instrument master: https://kite.zerodha.com/static/csv/instruments.csv
    
    # Placeholder tokens - UPDATE THESE WITH ACTUAL VALUES
    instrument_tokens = {
        'NSE:NIFTY 50': 256265,  # Replace with actual token
        'NSE:BANKNIFTY': 26010,  # Replace with actual token
        'NSE:RELIANCE': 738561,  # Example token
    }
    
    token = instrument_tokens.get(symbol)
    
    if token is None:
        logger.warning(f"No instrument token found for {symbol}, using default")
        # Default to NIFTY 50 token
        token = 256265
    
    return token


def save_to_csv(df, filepath='data/nifty50_90d.csv'):
    """
    Save DataFrame to CSV file.
    
    Args:
        df: DataFrame with datetime index
        filepath: Output file path
    
    Returns:
        True if saved successfully
    """
    try:
        # Create directory if it doesn't exist
        output_path = Path(filepath)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save to CSV
        df.to_csv(output_path)
        
        logger.info(f"✅ Saved {len(df)} rows to {filepath}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving to CSV: {e}")
        return False


def load_from_csv(filepath='data/nifty50_90d.csv'):
    """
    Load historical data from CSV file.
    
    Args:
        filepath: Path to CSV file
    
    Returns:
        DataFrame or None if failed
    """
    try:
        if not Path(filepath).exists():
            logger.info(f"CSV file not found: {filepath}")
            return None
        
        # Load CSV with datetime parsing
        df = pd.read_csv(
            filepath,
            parse_dates=['datetime'],
            index_col='datetime'
        )
        
        logger.info(f"✅ Loaded {len(df)} candles from {filepath}")
        return df
        
    except Exception as e:
        logger.error(f"Error loading CSV: {e}")
        return None


def fetch_or_load(days=90, use_cached=True):
    """
    Fetch fresh data or load from cache.
    
    Args:
        days: Number of days of data
        use_cached: Use cached CSV if exists (default: True)
    
    Returns:
        DataFrame with historical data
    """
    csv_path = 'data/nifty50_90d.csv'
    
    # Try to load from cache first
    if use_cached:
        cached_df = load_from_csv(csv_path)
        if cached_df is not None:
            logger.info("Using cached data")
            return cached_df
    
    # Fetch fresh data
    logger.info("Fetching fresh data from Zerodha...")
    df = fetch_nifty_historical_data(days=days)
    
    if df is not None:
        # Save to cache
        save_to_csv(df, csv_path)
    
    return df


def main():
    """Main function to fetch and save NIFTY 50 data."""
    print("="*70)
    print("  ZERODHA HISTORICAL DATA FETCHER")
    print("="*70)
    print()
    
    # Configuration
    days = 90
    symbol = "NSE:NIFTY 50"
    timeframe = "5minute"
    output_file = "data/nifty50_90d.csv"
    
    print(f"Symbol: {symbol}")
    print(f"Timeframe: {timeframe}")
    print(f"Days: {days}")
    print(f"Output: {output_file}")
    print()
    
    # Fetch or load data
    df = fetch_or_load(days=days, use_cached=True)
    
    if df is None:
        print("\n❌ FAILED TO FETCH DATA")
        print("\nPossible reasons:")
        print("  1. Not connected to Zerodha broker")
        print("  2. Invalid instrument token")
        print("  3. No historical data permissions")
        print("\nNext Steps:")
        print("  1. Connect broker: http://localhost:3000/broker")
        print("  2. Verify instrument tokens in code")
        print("  3. Contact Zerodha for API permissions")
        return
    
    # Display summary
    print("\n" + "="*70)
    print("  DATA SUMMARY")
    print("="*70)
    print(f"Total Candles: {len(df)}")
    print(f"Date Range: {df.index.min().strftime('%Y-%m-%d %H:%M')} to {df.index.max().strftime('%Y-%m-%d %H:%M')}")
    print(f"Price Range: ₹{df['close'].min():,.2f} to ₹{df['close'].max():,.2f}")
    print(f"Average Volume: {df['volume'].mean():,.0f}")
    print()
    
    # Check if enough data for warm-up
    min_bars_required = 100
    if len(df) >= min_bars_required:
        print(f"✅ Sufficient data for strategy warm-up ({len(df)} >= {min_bars_required})")
    else:
        print(f"⚠️  Insufficient data ({len(df)} < {min_bars_required})")
        print(f"   Need at least {min_bars_required} bars (8.3 hours of 5-min data)")
    
    print("\n" + "="*70)
    print("  READY FOR BACKTEST!")
    print("="*70)
    print(f"\nRun backtest with:")
    print(f"  python run_terminal_backtest.py --data {output_file}")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
