"""
Trade Shuffler Module for Robustness Testing

Randomize trade sequences to test strategy sensitivity to trade order.

Methods:
- Random shuffle (permutation)
- Bootstrap sampling (with replacement)
- Block shuffling (preserves autocorrelation)

Author: Quantitative Trading Systems Engineer
Date: March 16, 2026
"""

import numpy as np
import pandas as pd
import logging
from typing import List, Any, Optional, Tuple, Dict
from copy import deepcopy

logger = logging.getLogger(__name__)


class TradeShuffler:
    """
    Randomize trade sequences for robustness testing.
    
    Generates alternative trade sequences by shuffling and resampling
    historical trades to test strategy sensitivity.
    
    Usage:
        >>> shuffler = TradeShuffler()
        >>> shuffled_trades = shuffler.random_shuffle(trades)
    """
    
    def __init__(self, random_seed: int = None):
        """
        Initialize trade shuffler.
        
        Args:
            random_seed: Random seed for reproducibility (optional)
        
        Example:
            >>> shuffler = TradeShuffler(random_seed=42)
        """
        self.random_seed = random_seed
        
        if random_seed is not None:
            np.random.seed(random_seed)
        
        logger.info("TradeShuffler initialized")
    
    def random_shuffle(
        self,
        trades: List[Any],
        n_sequences: int = 1
    ) -> List[List[Any]]:
        """
        Randomly shuffle trade sequence (permutation without replacement).
        
        Args:
            trades: Original list of trades
            n_sequences: Number of shuffled sequences to generate
        
        Returns:
            List of shuffled trade sequences
        
        Example:
            >>> sequences = shuffler.random_shuffle(trades, n_sequences=100)
        """
        if not trades:
            logger.warning("No trades to shuffle")
            return []
        
        logger.debug(f"Generating {n_sequences} random shuffle sequences")
        
        sequences = []
        n_trades = len(trades)
        
        for _ in range(n_sequences):
            # Create permutation
            shuffled_indices = np.random.permutation(n_trades)
            shuffled_trades = [trades[i] for i in shuffled_indices]
            sequences.append(shuffled_trades)
        
        logger.debug(f"Generated {len(sequences)} shuffled sequences")
        return sequences
    
    def bootstrap_sample(
        self,
        trades: List[Any],
        sample_size: int = None,
        n_sequences: int = 1
    ) -> List[List[Any]]:
        """
        Bootstrap sample trades (sampling with replacement).
        
        Args:
            trades: Original list of trades
            sample_size: Size of each sample (default: len(trades))
            n_sequences: Number of bootstrap samples to generate
        
        Returns:
            List of bootstrap sampled trade sequences
        
        Example:
            >>> samples = shuffler.bootstrap_sample(trades, n_sequences=1000)
        """
        if not trades:
            logger.warning("No trades to sample")
            return []
        
        sample_size = sample_size or len(trades)
        
        logger.debug(
            f"Generating {n_sequences} bootstrap samples "
            f"(size={sample_size})"
        )
        
        sequences = []
        n_trades = len(trades)
        
        for _ in range(n_sequences):
            # Sample with replacement
            sampled_indices = np.random.choice(
                n_trades, size=sample_size, replace=True
            )
            sampled_trades = [trades[i] for i in sampled_indices]
            sequences.append(sampled_trades)
        
        logger.debug(f"Generated {len(sequences)} bootstrap samples")
        return sequences
    
    def block_shuffle(
        self,
        trades: List[Any],
        block_size: int = None,
        n_sequences: int = 1
    ) -> List[List[Any]]:
        """
        Block shuffle trades (preserves autocorrelation structure).
        
        Divides trades into blocks, shuffles blocks, then concatenates.
        
        Args:
            trades: Original list of trades
            block_size: Size of each block (default: sqrt(n_trades))
            n_sequences: Number of block shuffled sequences to generate
        
        Returns:
            List of block shuffled trade sequences
        
        Example:
            >>> sequences = shuffler.block_shuffle(trades, block_size=10)
        """
        if not trades:
            logger.warning("No trades to shuffle")
            return []
        
        n_trades = len(trades)
        block_size = block_size or int(np.sqrt(n_trades))
        block_size = max(1, block_size)  # Ensure at least 1
        
        logger.debug(
            f"Generating {n_sequences} block shuffle sequences "
            f"(block_size={block_size})"
        )
        
        sequences = []
        
        for _ in range(n_sequences):
            # Create blocks
            blocks = []
            for start in range(0, n_trades, block_size):
                end = min(start + block_size, n_trades)
                block = trades[start:end]
                if block:  # Only add non-empty blocks
                    blocks.append(block)
            
            # Shuffle blocks
            np.random.shuffle(blocks)
            
            # Concatenate blocks
            shuffled_trades = []
            for block in blocks:
                shuffled_trades.extend(block)
            
            sequences.append(shuffled_trades)
        
        logger.debug(f"Generated {len(sequences)} block shuffled sequences")
        return sequences
    
    def generate_all_methods(
        self,
        trades: List[Any],
        n_sequences_per_method: int = 100,
        block_size: int = None
    ) -> Dict[str, List[List[Any]]]:
        """
        Generate shuffled sequences using all methods.
        
        Args:
            trades: Original list of trades
            n_sequences_per_method: Number of sequences per method
            block_size: Block size for block shuffling
        
        Returns:
            Dictionary with sequences from each method
        
        Example:
            >>> all_sequences = shuffler.generate_all_methods(trades, n_sequences=100)
            >>> print(f"Random shuffle: {len(all_sequences['random'])} sequences")
        """
        logger.info("Generating sequences using all shuffling methods")
        
        results = {
            'random': self.random_shuffle(trades, n_sequences_per_method),
            'bootstrap': self.bootstrap_sample(trades, n_sequences=n_sequences_per_method),
            'block': self.block_shuffle(trades, block_size, n_sequences_per_method)
        }
        
        total_sequences = sum(len(v) for v in results.values())
        logger.info(f"Generated {total_sequences} total sequences")
        
        return results
    
    def get_trade_statistics(
        self,
        trades: List[Any]
    ) -> Dict[str, Any]:
        """
        Calculate statistics for original trade sequence.
        
        Args:
            trades: List of trades
        
        Returns:
            Dictionary with trade statistics
        
        Example:
            >>> stats = shuffler.get_trade_statistics(trades)
            >>> print(f"Win rate: {stats['win_rate']:.1%}")
        """
        if not trades:
            return {}
        
        pnls = [t.pnl for t in trades if t.pnl is not None]
        
        if not pnls:
            return {}
        
        pnls = np.array(pnls)
        winning_trades = [t for t in trades if t.pnl and t.pnl > 0]
        losing_trades = [t for t in trades if t.pnl and t.pnl < 0]
        
        return {
            'total_trades': len(trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': len(winning_trades) / len(trades) if trades else 0,
            'total_pnl': sum(pnls),
            'avg_pnl': np.mean(pnls),
            'std_pnl': np.std(pnls),
            'best_trade': np.max(pnls),
            'worst_trade': np.min(pnls),
            'avg_winner': np.mean([t.pnl for t in winning_trades]) if winning_trades else 0,
            'avg_loser': np.mean([t.pnl for t in losing_trades]) if losing_trades else 0,
            'profit_factor': abs(sum(t.pnl for t in winning_trades) / sum(t.pnl for t in losing_trades))
                           if losing_trades and sum(t.pnl for t in losing_trades) != 0 else float('inf')
        }


def shuffle_trades(
    trades: List[Any],
    method: str = 'random',
    n_sequences: int = 100,
    block_size: int = None,
    random_seed: int = None
) -> List[List[Any]]:
    """
    Convenience function to shuffle trades.
    
    Args:
        trades: Original trade list
        method: Shuffling method ('random', 'bootstrap', 'block')
        n_sequences: Number of sequences to generate
        block_size: Block size for block shuffling
        random_seed: Random seed for reproducibility
    
    Returns:
        List of shuffled trade sequences
    
    Example:
        >>> sequences = shuffle_trades(trades, method='bootstrap', n_sequences=1000)
    """
    shuffler = TradeShuffler(random_seed=random_seed)
    
    if method == 'random':
        return shuffler.random_shuffle(trades, n_sequences)
    elif method == 'bootstrap':
        return shuffler.bootstrap_sample(trades, n_sequences=n_sequences)
    elif method == 'block':
        return shuffler.block_shuffle(trades, block_size, n_sequences)
    else:
        raise ValueError(f"Unknown shuffling method: {method}")


def analyze_sequence_stability(
    trades: List[Any],
    n_simulations: int = 1000
) -> Dict[str, Any]:
    """
    Analyze stability of strategy performance across shuffled sequences.
    
    Args:
        trades: Original trade list
        n_simulations: Number of simulations per method
    
    Returns:
        Dictionary with stability metrics
    
    Example:
        >>> stability = analyze_sequence_stability(trades, n_simulations=500)
        >>> print(f"Return std dev: {stability['return_std_dev']:.4f}")
    """
    logger.info(f"Analyzing sequence stability with {n_simulations} simulations")
    
    shuffler = TradeShuffler()
    
    # Generate sequences using all methods
    all_sequences = shuffler.generate_all_methods(
        trades, n_sequences_per_method=n_simulations
    )
    
    # Calculate statistics for each method
    results = {}
    
    for method, sequences in all_sequences.items():
        pnls_list = []
        
        for seq in sequences:
            total_pnl = sum(t.pnl for t in seq if t.pnl is not None)
            pnls_list.append(total_pnl)
        
        pnls_array = np.array(pnls_list)
        
        results[method] = {
            'mean_pnl': np.mean(pnls_array),
            'std_pnl': np.std(pnls_array),
            'min_pnl': np.min(pnls_array),
            'max_pnl': np.max(pnls_array),
            'prob_loss': np.mean(pnls_array < 0),
            'sequences': n_simulations
        }
    
    # Calculate overall stability metrics
    all_pnls = np.concatenate([np.array(v) for v in [
        np.array([sum(t.pnl for t in seq if t.pnl is not None) for seq in seqs])
        for seqs in all_sequences.values()
    ]])
    
    results['overall'] = {
        'combined_mean': np.mean(all_pnls),
        'combined_std': np.std(all_pnls),
        'coefficient_of_variation': np.std(all_pnls) / abs(np.mean(all_pnls)) if np.mean(all_pnls) != 0 else float('inf'),
        'stability_score': 1.0 / (1.0 + np.std(all_pnls))  # Higher is more stable
    }
    
    logger.info(
        f"Stability analysis complete: "
        f"Coefficient of variation={results['overall']['coefficient_of_variation']:.4f}"
    )
    
    return results
