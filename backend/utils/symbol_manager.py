import os
import json
import logging
import urllib.request
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class SymbolManager:
    SYMBOL_URL = "https://margincalculator.angelbroking.com/OpenAPI_Config/v1/OpenAPISymbolTokendetails.json"
    CACHE_FILE = os.path.join(os.path.dirname(__file__), "symbols_cache.json")
    
    def __init__(self):
        self.symbols_data = []
        self.load_symbols()

    def _should_download(self):
        if not os.path.exists(self.CACHE_FILE):
            return True
        
        # Check if the file is older than 1 day
        file_mtime = datetime.fromtimestamp(os.path.getmtime(self.CACHE_FILE))
        return datetime.now() - file_mtime > timedelta(days=1)

    def load_symbols(self):
        try:
            if self._should_download():
                logger.info(f"Downloading symbol master from {self.SYMBOL_URL}")
                # Use urllib to download to avoid depending on requests if not needed
                urllib.request.urlretrieve(self.SYMBOL_URL, self.CACHE_FILE)
                logger.info("Symbol master downloaded successfully.")
            
            with open(self.CACHE_FILE, "r") as f:
                self.symbols_data = json.load(f)
            logger.info(f"Loaded {len(self.symbols_data)} symbols from cache.")
            
        except Exception as e:
            logger.error(f"Error loading symbols: {str(e)}")
            self.symbols_data = []

    def get_token(self, symbol: str, exchange: str = 'NSE'):
        """
        Resolves a symbol name to its exchange token and lot size.
        Example: get_token('SBIN-EQ', 'NSE') -> ('3045', '1')
        """
        for item in self.symbols_data:
            if item.get('symbol') == symbol and item.get('exch_seg') == exchange:
                return item.get('token'), item.get('lotsize')
                
        # If not found exactly, try matching just the name and exchange if it lacks -EQ
        # Useful for simpler mappings
        if '-EQ' not in symbol and exchange == 'NSE':
            alt_symbol = f"{symbol}-EQ"
            for item in self.symbols_data:
                if item.get('symbol') == alt_symbol and item.get('exch_seg') == exchange:
                    return item.get('token'), item.get('lotsize')

        return None, None
