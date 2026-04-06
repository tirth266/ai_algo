/**
 * String utility functions
 */

export const toTitleCase = (str: string): string => {
  return str.replace(/_/g, ' ')
    .split(' ')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');
};

export const formatNumber = (num: number, decimals: number = 2): string => {
  if (Math.abs(num) >= 1000000) {
    return `${(num / 1000000).toFixed(decimals)}M`;
  }
  if (Math.abs(num) >= 1000) {
    return `${(num / 1000).toFixed(decimals)}K`;
  }
  return num.toFixed(decimals);
};

export const formatCurrency = (amount: number): string => {
  return `₹${formatNumber(amount, 0)}`;
};
