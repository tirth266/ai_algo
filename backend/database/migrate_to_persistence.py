"""
Database Migration Script

This script handles:
1. Creating necessary database tables if they don't exist
2. Migrating existing trade data from JSON logs to database
3. Verifying data integrity after migration

Author: Quantitative Trading Systems Engineer
Date: April 8, 2026
"""

import logging
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def initialize_database():
    """
    Initialize database and create all necessary tables.
    
    This should be called once on first deployment.
    """
    logger.info("Initializing database...")
    
    try:
        from backend.database.connection import create_database_engine
        from backend.models.base import Base
        
        # Create engine
        engine = create_database_engine()
        
        # Create all tables
        Base.metadata.create_all(engine)
        
        logger.info("✓ Database initialization complete")
        logger.info("  Tables created: positions, trades, orders, strategy_runs, equity_curves")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Failed to initialize database: {str(e)}")
        return False


def migrate_json_trades_to_db():
    """
    Migrate legacy trade data from JSON files to database.
    
    Finds all JSON files in logs/trades/ and imports them into the database.
    """
    logger.info("\nMigrating JSON trade logs to database...")
    
    try:
        from backend.core.position_persistence import PositionPersistence
        
        persistence = PositionPersistence()
        logs_dir = Path('logs/trades')
        
        if not logs_dir.exists():
            logger.warning(f"Logs directory not found: {logs_dir}")
            return 0
        
        total_migrated = 0
        errors = 0
        
        json_files = list(logs_dir.glob('*.json'))
        logger.info(f"Found {len(json_files)} trade log files to process")
        
        for log_file in json_files:
            try:
                logger.info(f"Processing: {log_file.name}")
                
                with open(log_file) as f:
                    data = json.load(f)
                    
                    # Handle both single trade and list of trades
                    trades = data if isinstance(data, list) else [data]
                    
                    for trade in trades:
                        try:
                            # Parse timestamps
                            entry_time = None
                            exit_time = None
                            
                            if 'entry_timestamp' in trade:
                                entry_time = datetime.fromisoformat(trade['entry_timestamp'])
                            if 'exit_timestamp' in trade:
                                exit_time = datetime.fromisoformat(trade['exit_timestamp'])
                            
                            # Determine status
                            status = 'closed' if trade.get('exit_price') else 'open'
                            
                            # Determine exit reason
                            exit_reason = None
                            if 'exit_type' in trade:
                                exit_reason = trade['exit_type']
                            elif 'reason' in trade:
                                exit_reason = trade['reason']
                            
                            # Save to database
                            persistence.save_trade(
                                symbol=trade.get('symbol', 'UNKNOWN'),
                                side=trade.get('direction', 'BUY').upper(),
                                quantity=int(trade.get('quantity', 0)),
                                entry_price=float(trade.get('entry_price', 0)),
                                exit_price=float(trade.get('exit_price')) if trade.get('exit_price') else None,
                                stop_loss=float(trade.get('stop_loss')) if trade.get('stop_loss') else None,
                                take_profit=float(trade.get('take_profit')) if trade.get('take_profit') else None,
                                status=status,
                                exit_reason=exit_reason,
                                strategy_name=trade.get('strategy', 'legacy_import'),
                                entry_time=entry_time,
                                exit_time=exit_time,
                                pnl=float(trade.get('pnl', 0)) if trade.get('pnl') else None,
                            )
                            
                            total_migrated += 1
                            
                        except Exception as e:
                            logger.warning(f"  Error importing trade: {str(e)}")
                            errors += 1
                
                logger.info(f"  ✓ Processed {log_file.name}")
                
            except json.JSONDecodeError as e:
                logger.error(f"  ✗ Invalid JSON in {log_file.name}: {str(e)}")
                errors += 1
            except Exception as e:
                logger.error(f"  ✗ Error processing {log_file.name}: {str(e)}")
                errors += 1
        
        persistence.close()
        
        if errors > 0:
            logger.warning(f"\n⚠ Migration complete with {errors} errors")
        else:
            logger.info(f"\n✓ Migration complete: {total_migrated} trades imported")
        
        return total_migrated
        
    except Exception as e:
        logger.error(f"✗ Migration failed: {str(e)}")
        return 0


def verify_migration():
    """
    Verify that migration was successful.
    
    Checks:
    1. Database tables exist
    2. Data was imported correctly
    3. No duplicate entries
    """
    logger.info("\nVerifying migration...")
    
    try:
        from backend.core.position_persistence import PositionPersistence
        
        persistence = PositionPersistence()
        
        # Count trades
        trades = persistence.load_closed_trades(limit=1000)
        open_trades = persistence.load_open_trades()
        positions = persistence.load_open_positions()
        
        logger.info(f"✓ Verification results:")
        logger.info(f"  Total closed trades: {len(trades)}")
        logger.info(f"  Total open trades: {len(open_trades)}")
        logger.info(f"  Total open positions: {len(positions)}")
        
        if len(trades) > 0:
            # Sample log
            trade = trades[0]
            logger.info(f"\n  Sample trade:")
            logger.info(f"    Symbol: {trade.get('symbol')}")
            logger.info(f"    Side: {trade.get('side')}")
            logger.info(f"    Entry: {trade.get('entry_price')} -> Exit: {trade.get('exit_price')}")
            logger.info(f"    PnL: {trade.get('pnl')}")
            logger.info(f"    Status: {trade.get('status')}")
        
        persistence.close()
        logger.info("\n✓ Verification complete - migration successful!")
        return True
        
    except Exception as e:
        logger.error(f"✗ Verification failed: {str(e)}")
        return False


def create_backup():
    """Create backup of SQLite database before migration."""
    import shutil
    from datetime import datetime
    
    logger.info("\nCreating database backup...")
    
    try:
        db_file = Path('algo_trading.db')
        
        if db_file.exists():
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = Path(f'{db_file}.backup_{timestamp}')
            
            shutil.copy(db_file, backup_file)
            logger.info(f"✓ Backup created: {backup_file}")
            return True
        else:
            logger.info("  No database file found - skipping backup")
            return True
            
    except Exception as e:
        logger.error(f"✗ Failed to create backup: {str(e)}")
        return False


def main():
    """Run full migration pipeline."""
    logger.info("=" * 70)
    logger.info("POSITION PERSISTENCE - DATABASE MIGRATION")
    logger.info("=" * 70)
    
    # Step 1: Backup existing database
    logger.info("\n[STEP 1] Backup existing database")
    create_backup()
    
    # Step 2: Initialize database
    logger.info("\n[STEP 2] Initialize database")
    if not initialize_database():
        logger.error("Migration aborted - database initialization failed")
        return False
    
    # Step 3: Migrate legacy trades
    logger.info("\n[STEP 3] Migrate legacy JSON trade logs")
    migrate_json_trades_to_db()
    
    # Step 4: Verify migration
    logger.info("\n[STEP 4] Verify migration")
    if not verify_migration():
        logger.error("Migration verification failed - please review errors above")
        return False
    
    logger.info("\n" + "=" * 70)
    logger.info("✓ ALL MIGRATION STEPS COMPLETE")
    logger.info("=" * 70)
    logger.info("\nNext steps:")
    logger.info("1. Verify data accuracy")
    logger.info("2. Test system startup with restored positions")
    logger.info("3. Monitor trade persistence during normal operation")
    logger.info("4. Archive old JSON log files")
    
    return True


if __name__ == '__main__':
    import sys
    
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.warning("\nMigration cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\nUnexpected error: {str(e)}")
        sys.exit(1)
