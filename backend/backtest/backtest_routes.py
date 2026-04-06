"""
Backtesting API Routes

Flask blueprint for backtesting endpoints.

Endpoints:
POST   /api/backtest/run          - Run backtest
POST   /api/backtest/monte-carlo  - Run Monte Carlo simulation
POST   /api/backtest/walk-forward - Run walk-forward analysis
GET    /api/backtest/results      - Get backtest results
GET    /api/backtest/history      - Get historical data preview
"""

from flask import Blueprint, request, jsonify
from typing import Dict, Any
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Create blueprint
backtest_bp = Blueprint('backtest', __name__, url_prefix='/api/backtest')


@backtest_bp.route('/run', methods=['POST'])
def run_backtest():
    """
    Run backtest for Combined Power Strategy.
    
    Request Body:
        {
            "strategy": "combined_power_strategy",
            "symbol": "RELIANCE",
            "timeframe": "5minute",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "capital_per_trade": 25000
        }
    
    Response:
        {
            "success": true,
            "results": {
                "total_pnl": 12450,
                "win_rate": 58,
                "max_drawdown": -4.5,
                "sharpe_ratio": 1.82,
                ...
            }
        }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        # Validate required fields
        required_fields = ['symbol', 'timeframe', 'start_date', 'end_date']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        # Extract parameters
        symbol = data['symbol'].upper()
        timeframe = data['timeframe']
        start_date = data['start_date']
        end_date = data['end_date']
        initial_capital = data.get('initial_capital', 100000.0)
        capital_per_trade = data.get('capital_per_trade', 25000.0)
        strategy_name = data.get('strategy', 'combined_power_strategy')
        
        logger.info(f"Running backtest: {symbol} ({timeframe}) from {start_date} to {end_date}")
        
        # Import and run backtest engine
        from .institutional_backtest_engine import InstitutionalBacktestEngine
        
        # Create engine with parameters
        engine = InstitutionalBacktestEngine(
            initial_capital=initial_capital,
            capital_per_trade=capital_per_trade,
            slippage_percent=0.0005,
            brokerage_per_trade=20.0,
            stop_loss_percent=0.02,
            take_profit_percent=0.04,
            max_positions=5,
            verbose=True
        )
        
        # Run backtest (kite_client=None will use mock data)
        kite_client = None  # TODO: Get from broker service if connected
        
        try:
            results = engine.run_backtest(
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date,
                kite_client=kite_client
            )
        except Exception as e:
            logger.error(f"Backtest execution failed: {str(e)}", exc_info=True)
            return jsonify({
                'success': False,
                'error': f'Backtest failed: {str(e)}'
            }), 500
        
        logger.info(f"Backtest complete. Total P&L: ₹{results['total_pnl']:,.2f}")
        
        # Prepare response (exclude detailed trade list for summary)
        response_data = {
            'success': True,
            'results': {
                'symbol': results['symbol'],
                'initial_capital': results['initial_capital'],
                'final_capital': results['final_capital'],
                'total_pnl': results['total_pnl'],
                'return_percent': results['return_percent'],
                'total_trades': results['total_trades'],
                'winning_trades': results['winning_trades'],
                'losing_trades': results['losing_trades'],
                'win_rate': results['win_rate'],
                'loss_rate': results['loss_rate'],
                'avg_pnl': results['avg_pnl'],
                'avg_win': results['avg_win'],
                'avg_loss': results['avg_loss'],
                'profit_factor': results['profit_factor'],
                'expectancy': results['expectancy'],
                'max_drawdown': results['max_drawdown'],
                'sharpe_ratio': results['sharpe_ratio'],
                'trades_count': len(results['trades']),
                'equity_curve_points': len(results['equity_curve'])
            },
            'detailed_trades': results['trades'][:100],  # First 100 trades
            'equity_curve': results['equity_curve'][-100:]  # Last 100 points
        }
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Error running backtest: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@backtest_bp.route('/results/<backtest_id>', methods=['GET'])
def get_backtest_results(backtest_id: str):
    """
    Get detailed backtest results by ID.
    
    Path Parameters:
        backtest_id: Unique backtest identifier
    
    Response:
        Complete backtest results including all trades and equity curve
    """
    try:
        # TODO: Implement storage and retrieval of backtest results
        # For now, return placeholder
        return jsonify({
            'success': False,
            'error': 'Backtest result storage not implemented yet'
        }), 501
        
    except Exception as e:
        logger.error(f"Error getting backtest results: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@backtest_bp.route('/optimize', methods=['POST'])
def optimize_parameters():
    """
    Run parameter optimization (grid search).
    
    Request Body:
        {
            "symbol": "RELIANCE",
            "timeframe": "5minute",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "param_grid": {
                "supertrend_factor": [2.0, 2.5, 3.0, 3.5, 4.0],
                "min_votes": [2, 3, 4, 5]
            },
            "n_jobs": 4  # Number of parallel processes (-1 for all CPUs)
        }
    
    Response:
        {
            "success": true,
            "results": {
                "best_params": {...},
                "results_matrix": {...},  # For heatmap visualization
                "robust_zone": {...},      # Stable parameter region
                "overfitting_analysis": {...}
            },
            "export_urls": {
                "csv": "/api/backtest/results/optimization.csv",
                "json": "/api/backtest/results/optimization.json"
            }
        }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        # Validate required fields
        required_fields = ['symbol', 'timeframe', 'start_date', 'end_date', 'param_grid']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        # Extract parameters
        symbol = data['symbol'].upper()
        timeframe = data['timeframe']
        start_date = data['start_date']
        end_date = data['end_date']
        param_grid = data['param_grid']
        n_jobs = data.get('n_jobs', -1)
        
        logger.info(f"Starting parameter optimization for {symbol}")
        logger.info(f"Parameter grid: {list(param_grid.keys())}")
        
        # Import and run optimizer
        from .parameter_optimizer import ParameterOptimizer
        
        optimizer = ParameterOptimizer()
        
        results = optimizer.run_grid_search(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            param_grid=param_grid,
            n_jobs=n_jobs,
            show_progress=True
        )
        
        logger.info(
            f"Optimization complete. Best Sharpe: {results['best_params']['sharpe_ratio']:.2f}"
        )
        
        # Export results
        from pathlib import Path
        export_dir = Path('backtest/results/optimization')
        export_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_file = export_dir / f"optimization_{symbol}_{timestamp}.csv"
        json_file = export_dir / f"optimization_{symbol}_{timestamp}.json"
        
        optimizer.export_to_csv(results, str(csv_file))
        optimizer.export_to_json(results, str(json_file))
        
        # Prepare response
        response_data = {
            'success': True,
            'results': {
                'total_combinations': results['total_combinations'],
                'successful_runs': results['successful_runs'],
                'failed_runs': results['failed_runs'],
                'best_params': results['best_params'],
                'results_matrix': results['results_matrix'],
                'robust_zone': results['robust_zone'],
                'overfitting_analysis': results['overfitting_analysis']
            },
            'export_urls': {
                'csv': f'/api/backtest/results/optimization_{symbol}_{timestamp}.csv',
                'json': f'/api/backtest/results/optimization_{symbol}_{timestamp}.json'
            }
        }
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Error running optimization: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@backtest_bp.route('/data/preview', methods=['GET'])
def preview_historical_data():
    """
    Preview historical data for a symbol.
    
    Query Parameters:
        symbol: Stock symbol
        timeframe: Candle timeframe
        start_date: Start date
        end_date: End date
    
    Response:
        Sample of historical data (first and last 5 candles)
    """
    try:
        symbol = request.args.get('symbol', '').upper()
        timeframe = request.args.get('timeframe', '5minute')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        if not symbol or not start_date or not end_date:
            return jsonify({
                'success': False,
                'error': 'Missing required parameters: symbol, start_date, end_date'
            }), 400
        
        # Load data preview
        from .data_loader import BacktestDataLoader
        
        loader = BacktestDataLoader()
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        
        data = loader.load_historical_data(symbol, timeframe, start_dt, end_dt)
        
        if data is None or len(data) == 0:
            return jsonify({
                'success': False,
                'error': 'No data found'
            }), 404
        
        # Return sample
        preview_data = {
            'success': True,
            'symbol': symbol,
            'timeframe': timeframe,
            'total_candles': len(data),
            'date_range': {
                'start': str(data.index[0]),
                'end': str(data.index[-1])
            },
            'first_5_candles': data.head(5).to_dict('records'),
            'last_5_candles': data.tail(5).to_dict('records'),
            'summary_stats': {
                'avg_close': float(data['close'].mean()),
                'max_high': float(data['high'].max()),
                'min_low': float(data['low'].min()),
                'avg_volume': float(data['volume'].mean())
            }
        }
        
        return jsonify(preview_data), 200
        
    except Exception as e:
        logger.error(f"Error previewing data: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@backtest_bp.route('/walk-forward', methods=['POST'])
def run_walk_forward():
    """
    Run walk-forward analysis.
    
    Request Body:
        {
            "symbol": "RELIANCE",
            "timeframe": "5minute",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "param_grid": {
                "supertrend_factor": [2.0, 2.5, 3.0, 3.5, 4.0],
                "min_votes": [2, 3, 4, 5]
            },
            "in_sample_days": 30,
            "out_of_sample_days": 7,
            "overlap_percent": 0.0
        }
    
    Response:
        {
            "success": true,
            "results": {
                "total_windows": 12,
                "window_results": [
                    {
                        "window_number": 1,
                        "in_sample_period": "2024-01-01 to 2024-01-30",
                        "out_of_sample_period": "2024-01-31 to 2024-02-06",
                        "optimal_params": {...},
                        "in_sample_metrics": {...},
                        "out_of_sample_metrics": {...},
                        "walk_forward_efficiency": 0.85
                    }
                ],
                "aggregate_metrics": {
                    "avg_walk_forward_efficiency": 0.72,
                    "std_walk_forward_efficiency": 0.15,
                    "min_wfe": 0.45,
                    "max_wfe": 0.95
                },
                "parameter_stability": {
                    "supertrend_factor": 0.85,
                    "min_votes": 0.92
                },
                "anchored_equity_curve": [...],
                "recommendation": {
                    "recommendation": "BUY",
                    "confidence": "MEDIUM",
                    "message": "Acceptable WFE. Strategy shows moderate robustness."
                }
            }
        }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        # Validate required fields
        required_fields = ['symbol', 'timeframe', 'start_date', 'end_date', 'param_grid']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        # Extract parameters
        symbol = data['symbol'].upper()
        timeframe = data['timeframe']
        start_date = data['start_date']
        end_date = data['end_date']
        param_grid = data['param_grid']
        in_sample_days = data.get('in_sample_days', 30)
        out_of_sample_days = data.get('out_of_sample_days', 7)
        overlap_percent = data.get('overlap_percent', 0.0)
        
        logger.info(f"Starting Walk-Forward Analysis for {symbol}")
        logger.info(f"IS: {in_sample_days} days, OOS: {out_of_sample_days} days")
        logger.info(f"Parameter grid: {list(param_grid.keys())}")
        
        # Import and run WFA manager
        from .wfa_manager import WalkForwardManager
        
        manager = WalkForwardManager(initial_capital=data.get('initial_capital', 100000.0))
        
        results = manager.run_walk_forward_analysis(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            param_grid=param_grid,
            in_sample_days=in_sample_days,
            out_of_sample_days=out_of_sample_days,
            overlap_percent=overlap_percent
        )
        
        logger.info(f"WFA complete. Average WFE: {results.aggregate_metrics['avg_walk_forward_efficiency']:.3f}")
        
        # Get recommendation
        recommendation = manager.get_recommendation(results)
        
        # Prepare response
        response_data = {
            'success': True,
            'results': manager.to_dict(results),
            'recommendation': recommendation
        }
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Error running walk-forward analysis: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@backtest_bp.route('/monte-carlo', methods=['POST'])
def run_monte_carlo():
    """
    Run Monte Carlo simulation on backtest trades.
    
    Request Body:
        {
            "trades": [
                {
                    "entry_date": "2024-01-15",
                    "exit_date": "2024-01-16",
                    "pnl": 1250.00,
                    "return_pct": 1.25,
                    "max_drawdown": -0.50,
                    "max_profit": 1.80,
                    "duration_bars": 3,
                    "direction": "LONG"
                },
                ...
            ],
            "equity_curve": [100000, 101250, 99800, ...],
            "initial_capital": 100000,
            "num_simulations": 1000,
            "ruin_threshold": 0.20
        }
    
    Response:
        {
            "success": true,
            "results": {
                "original_equity_curve": [...],
                "simulated_curves_sample": [[...], ...],  # First 100 curves
                "num_simulations": 1000,
                "percentiles": {
                    "5th": [...],
                    "25th": [...],
                    "50th": [...],  # Median
                    "75th": [...],
                    "95th": [...]
                },
                "risk_of_ruin": 0.08,  # 8% chance of 20% drawdown
                "expected_max_drawdown": 0.25,
                "confidence_metrics": {
                    "avg_max_drawdown": 0.18,
                    "std_max_drawdown": 0.07,
                    "avg_final_return": 0.12,
                    "std_final_return": 0.09,
                    "risk_of_ruin": 0.08,
                    "expected_max_drawdown": 0.25,
                    "win_rate": 0.58,
                    "profit_factor": 1.85,
                    "num_simulations": 1000
                }
            }
        }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        # Validate required fields
        if 'trades' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing required field: trades'
            }), 400
        
        # Extract parameters
        trades = data['trades']
        equity_curve = data.get('equity_curve', [])
        initial_capital = data.get('initial_capital', 100000.0)
        num_simulations = data.get('num_simulations', 1000)
        ruin_threshold = data.get('ruin_threshold', 0.20)
        
        logger.info(f"Running Monte Carlo simulation with {num_simulations} iterations")
        logger.info(f"Analyzing {len(trades)} trades")
        
        # Import and run Monte Carlo analyzer
        from .monte_carlo_analyzer import analyze_sequence_risk
        
        results = analyze_sequence_risk(
            trades=trades,
            equity_curve=equity_curve,
            num_simulations=num_simulations,
            initial_capital=initial_capital
        )
        
        logger.info(
            f"Monte Carlo complete. Risk of ruin: {results['risk_of_ruin']:.2%}"
        )
        
        # Prepare response
        response_data = {
            'success': True,
            'results': results
        }
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Error running Monte Carlo: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@backtest_bp.route('/symbols', methods=['GET'])
def get_available_symbols():
    """
    Get list of commonly traded symbols for backtesting.
    
    Response:
        List of symbol names
    """
    # Common NSE symbols
    symbols = [
        'RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK',
        'HINDUNILVR', 'BHARTIARTL', 'ITC', 'SBIN', 'BAJFINANCE',
        'KOTAKBANK', 'LT', 'AXISBANK', 'ASIANPAINT', 'MARUTI',
        'NIFTY50', 'BANKNIFTY'
    ]
    
    return jsonify({
        'success': True,
        'symbols': symbols
    }), 200
