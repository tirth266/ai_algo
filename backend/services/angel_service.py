"""
Angel One Broker Service Layer

Production-grade centralized service for ALL Angel One broker interactions.

This service layer provides a unified interface for:
- Authentication and token management
- Order placement and management
- Position and portfolio retrieval
- Error handling and retry logic
- Standardized API responses

CRITICAL DESIGN PRINCIPLE:
NO OTHER MODULE should directly call broker APIs.
All broker interactions MUST go through this service.

Author: Quantitative Trading Systems Engineer
Date: April 8, 2026
"""

import logging
import time
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

from .token_manager import TokenManager

try:
    from SmartApi import SmartConnect
    from SmartApi.smartExceptions import SmartApiException
except ImportError:
    SmartConnect = None
    SmartApiException = None

logger = logging.getLogger(__name__)


# ============================================================================
# Standardized Response Types
# ============================================================================

class ApiStatus(Enum):
    """Standard API response status codes."""
    SUCCESS = "success"
    ERROR = "error"
    RETRY_EXHAUSTED = "retry_exhausted"
    UNAUTHORIZED = "unauthorized"
    RATE_LIMIT = "rate_limit"
    VALIDATION_ERROR = "validation_error"
    TIMEOUT = "timeout"


@dataclass
class ApiResponse:
    """Standardized API response format."""
    status: ApiStatus
    message: str
    data: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None
    retry_count: int = 0
    timestamp: datetime = field(default_factory=datetime.now)

    def is_success(self) -> bool:
        """Check if response indicates success."""
        return self.status == ApiStatus.SUCCESS

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "status": self.status.value,
            "message": self.message,
            "data": self.data,
            "error_code": self.error_code,
            "retry_count": self.retry_count,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class OrderRequest:
    """Standardized order request."""
    symbol: str
    direction: str  # "BUY" or "SELL"
    quantity: int
    price: float
    order_type: str = "MARKET"  # "MARKET", "LIMIT", "SL", "SL-M"
    stop_loss: Optional[float] = None
    product: str = "INTRADAY"  # "INTRADAY", "DELIVERY", "CARRYFORWARD"
    validity: str = "DAY"  # "DAY", "IOC", "TTL"


@dataclass
class Position:
    """Standardized position data."""
    symbol: str
    quantity: int
    entry_price: float
    current_price: float
    pnl: float
    pnl_pct: float
    direction: str
    product: str


@dataclass
class Order:
    """Standardized order data."""
    order_id: str
    symbol: str
    direction: str
    quantity: int
    price: float
    status: str
    order_type: str
    timestamp: datetime


# ============================================================================
# Retry and Error Handling
# ============================================================================

class BrokerError(Exception):
    """Base broker error."""
    pass


class BrokerAuthError(BrokerError):
    """Authentication/authorization error."""
    pass


class BrokerOrderError(BrokerError):
    """Order placement error."""
    pass


class BrokerConnectionError(BrokerError):
    """Connection/communication error."""
    pass


class BrokerRateLimitError(BrokerError):
    """Rate limit exceeded."""
    pass


def _map_error_to_status(error: Exception, attempt: int = 0) -> Tuple[ApiStatus, str, Optional[str]]:
    """Map exception to API status and error information."""
    error_msg = str(error).lower()

    if "unauthorized" in error_msg or "invalid token" in error_msg:
        return ApiStatus.UNAUTHORIZED, "Authentication failed", "AUTH_ERROR"

    if "rate limit" in error_msg or "too many requests" in error_msg:
        return ApiStatus.RATE_LIMIT, "Rate limit exceeded", "RATE_LIMIT"

    if "timeout" in error_msg or "connection" in error_msg.lower():
        return ApiStatus.TIMEOUT, "Connection timeout", "TIMEOUT"

    return ApiStatus.ERROR, str(error), "API_ERROR"


# ============================================================================
# Angel Service
# ============================================================================

class AngelService:
    """
    Production-grade Angel One broker service layer.

    This service centralizes all broker interactions and ensures:
    1. Consistent error handling and retries
    2. Token lifecycle management via TokenManager
    3. Standardized request/response formats
    4. Single point of control for broker operations
    5. Comprehensive logging for audit trail

    Usage:
        >>> service = AngelService()
        >>> result = service.login(client_id, password, totp)
        >>> if result.is_success():
        ...     positions = service.get_positions()
    """

    # Configuration constants
    MAX_RETRIES = 3
    RETRY_DELAY = 1.0  # seconds
    RETRY_BACKOFF = 1.5  # exponential backoff multiplier
    REQUEST_TIMEOUT = 30  # seconds
    RATE_LIMIT_DELAY = 2.0  # seconds

    def __init__(self, token_manager: Optional[TokenManager] = None):
        """
        Initialize Angel Service.

        Args:
            token_manager: Optional TokenManager instance. If not provided,
                          creates a new instance using environment variables.
        """
        import os

        self.token_manager = token_manager or TokenManager(
            api_key=os.getenv("ANGEL_ONE_API_KEY", "LFHr3Azz"),
            client_id=os.getenv("ANGEL_ONE_CLIENT_ID", ""),
            mpin=os.getenv("ANGEL_ONE_MPIN") or os.getenv("ANGEL_ONE_PASSWORD"),
            totp_seed=os.getenv("ANGEL_ONE_TOTP_SEED"),
        )

        self.client: Optional[SmartConnect] = None
        self.is_authenticated = False
        self._last_request_time = 0.0

        logger.info("AngelService initialized")

    # ========================================================================
    # Authentication
    # ========================================================================

    def login(
        self,
        client_id: Optional[str] = None,
        password: Optional[str] = None,
        totp: Optional[str] = None,
        retries: int = MAX_RETRIES,
    ) -> ApiResponse:
        """
        Authenticate with Angel One.

        Args:
            client_id: Angel One client ID (uses env if not provided)
            password: Account password/MPIN (uses env if not provided)
            totp: One-time password (auto-generated if not provided)
            retries: Number of retry attempts

        Returns:
            ApiResponse with authentication status and tokens
        """
        logger.info("Starting Angel One authentication...")

        try:
            result = self.token_manager.login(
                client_code=client_id,
                password=password,
                totp=totp,
                retries=retries,
            )

            if result.get("success"):
                self.client = self._create_client()
                self.is_authenticated = True

                logger.info("Angel One authentication successful")
                return ApiResponse(
                    status=ApiStatus.SUCCESS,
                    message="Authentication successful",
                    data={
                        "jwt_token": self.token_manager.jwt_token[:20] + "...",
                        "authenticated": True,
                    },
                )
            else:
                self.is_authenticated = False
                msg = result.get("message", "Login failed")
                logger.error(f"Authentication failed: {msg}")
                return ApiResponse(
                    status=ApiStatus.UNAUTHORIZED,
                    message=msg,
                    error_code="AUTH_FAILED",
                )

        except Exception as e:
            self.is_authenticated = False
            logger.error(f"Authentication exception: {str(e)}", exc_info=True)
            return ApiResponse(
                status=ApiStatus.ERROR,
                message=str(e),
                error_code="AUTH_EXCEPTION",
            )

    def refresh_token(self) -> ApiResponse:
        """
        Refresh authentication token.

        Returns:
            ApiResponse with refresh status
        """
        logger.info("Refreshing Angel One token...")

        try:
            result = self.token_manager.refresh()

            if result.get("success"):
                logger.info("Token refreshed successfully")
                return ApiResponse(
                    status=ApiStatus.SUCCESS,
                    message="Token refreshed successfully",
                    data={"authenticated": True},
                )
            else:
                msg = result.get("message", "Refresh failed")
                logger.error(f"Token refresh failed: {msg}")
                self.is_authenticated = False
                return ApiResponse(
                    status=ApiStatus.UNAUTHORIZED,
                    message=msg,
                    error_code="REFRESH_FAILED",
                )

        except Exception as e:
            logger.error(f"Token refresh exception: {str(e)}", exc_info=True)
            self.is_authenticated = False
            return ApiResponse(
                status=ApiStatus.ERROR,
                message=str(e),
                error_code="REFRESH_EXCEPTION",
            )

    def _ensure_authenticated(self) -> bool:
        """
        Ensure valid authentication, refreshing if needed.

        Returns:
            True if authenticated, False otherwise
        """
        if self.is_authenticated and self.token_manager.is_authenticated():
            return True

        logger.warning("Token not valid, attempting refresh...")
        result = self.refresh_token()
        return result.is_success()

    # ========================================================================
    # Order Management
    # ========================================================================

    def place_order(
        self,
        order_request: OrderRequest,
        retries: int = MAX_RETRIES,
    ) -> ApiResponse:
        """
        Place an order with Angel One.

        Args:
            order_request: OrderRequest with trade details
            retries: Number of retry attempts

        Returns:
            ApiResponse with order ID and status

        Raises:
            BrokerAuthError: If authentication fails
            BrokerOrderError: If order placement fails after retries
        """
        if not self._ensure_authenticated():
            logger.error("Cannot place order: authentication failed")
            raise BrokerAuthError("Authentication failed")

        logger.info(
            f"Placing order: {order_request.direction} {order_request.quantity} "
            f"{order_request.symbol} @ {order_request.order_type}"
        )

        for attempt in range(1, retries + 1):
            try:
                self._apply_rate_limit()

                # Build order parameters
                params = self._build_order_params(order_request)

                # Place order via SmartAPI
                response = self._call_api(
                    lambda: self.client.placeOrder(**params),
                    operation="placeOrder",
                    attempt=attempt,
                    max_attempts=retries,
                )

                # Extract order ID
                order_id = self._extract_order_id(response)

                if not order_id:
                    raise BrokerOrderError("No order ID in response")

                logger.info(
                    f"Order placed successfully: order_id={order_id}, "
                    f"symbol={order_request.symbol}"
                )

                return ApiResponse(
                    status=ApiStatus.SUCCESS,
                    message="Order placed successfully",
                    data={
                        "order_id": order_id,
                        "symbol": order_request.symbol,
                        "quantity": order_request.quantity,
                        "direction": order_request.direction,
                        "price": order_request.price,
                        "order_type": order_request.order_type,
                    },
                    retry_count=attempt - 1,
                )

            except BrokerRateLimitError:
                if attempt < retries:
                    wait_time = self.RATE_LIMIT_DELAY * (self.RETRY_BACKOFF ** (attempt - 1))
                    logger.warning(f"Rate limited, retrying in {wait_time:.1f}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    return ApiResponse(
                        status=ApiStatus.RATE_LIMIT,
                        message="Rate limit exceeded after retries",
                        error_code="RATE_LIMIT_EXHAUSTED",
                        retry_count=attempt,
                    )

            except BrokerAuthError:
                if self.refresh_token().is_success():
                    continue
                else:
                    return ApiResponse(
                        status=ApiStatus.UNAUTHORIZED,
                        message="Authentication failed",
                        error_code="AUTH_FAILED",
                        retry_count=attempt,
                    )

            except Exception as e:
                if attempt < retries:
                    wait_time = self.RETRY_DELAY * (self.RETRY_BACKOFF ** (attempt - 1))
                    logger.warning(
                        f"Order placement failed (attempt {attempt}/{retries}): {str(e)}. "
                        f"Retrying in {wait_time:.1f}s..."
                    )
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(
                        f"Order placement failed after {retries} attempts: {str(e)}"
                    )
                    status, msg, error_code = _map_error_to_status(e, attempt)
                    return ApiResponse(
                        status=status,
                        message=msg,
                        error_code=error_code,
                        retry_count=attempt,
                    )

        # Should not reach here
        return ApiResponse(
            status=ApiStatus.RETRY_EXHAUSTED,
            message="Order placement failed after all retries",
            error_code="MAX_RETRIES_EXCEEDED",
            retry_count=retries,
        )

    def get_orders(self, retries: int = MAX_RETRIES) -> ApiResponse:
        """
        Get all open orders.

        Args:
            retries: Number of retry attempts

        Returns:
            ApiResponse with list of orders
        """
        if not self._ensure_authenticated():
            return ApiResponse(
                status=ApiStatus.UNAUTHORIZED,
                message="Authentication failed",
                error_code="AUTH_FAILED",
            )

        logger.info("Retrieving open orders...")

        for attempt in range(1, retries + 1):
            try:
                self._apply_rate_limit()

                response = self._call_api(
                    lambda: self.client.orderBook(),
                    operation="orderBook",
                    attempt=attempt,
                    max_attempts=retries,
                )

                orders = self._parse_orders(response)

                logger.info(f"Retrieved {len(orders)} open orders")

                return ApiResponse(
                    status=ApiStatus.SUCCESS,
                    message="Orders retrieved successfully",
                    data={"orders": [o.__dict__ for o in orders]},
                    retry_count=attempt - 1,
                )

            except Exception as e:
                if attempt < retries:
                    wait_time = self.RETRY_DELAY * (self.RETRY_BACKOFF ** (attempt - 1))
                    logger.warning(
                        f"Failed to retrieve orders (attempt {attempt}/{retries}): {str(e)}"
                    )
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Failed to retrieve orders after {retries} attempts")
                    status, msg, error_code = _map_error_to_status(e, attempt)
                    return ApiResponse(
                        status=status,
                        message=msg,
                        error_code=error_code,
                        retry_count=attempt,
                    )

        return ApiResponse(
            status=ApiStatus.RETRY_EXHAUSTED,
            message="Failed to retrieve orders after all retries",
            error_code="MAX_RETRIES_EXCEEDED",
            retry_count=retries,
        )

    # ========================================================================
    # Portfolio Management
    # ========================================================================

    def get_positions(self, retries: int = MAX_RETRIES) -> ApiResponse:
        """
        Get all open positions.

        Args:
            retries: Number of retry attempts

        Returns:
            ApiResponse with list of positions
        """
        if not self._ensure_authenticated():
            return ApiResponse(
                status=ApiStatus.UNAUTHORIZED,
                message="Authentication failed",
                error_code="AUTH_FAILED",
            )

        logger.info("Retrieving positions...")

        for attempt in range(1, retries + 1):
            try:
                self._apply_rate_limit()

                response = self._call_api(
                    lambda: self.client.getPosition(),
                    operation="getPosition",
                    attempt=attempt,
                    max_attempts=retries,
                )

                positions = self._parse_positions(response)

                logger.info(f"Retrieved {len(positions)} positions")

                return ApiResponse(
                    status=ApiStatus.SUCCESS,
                    message="Positions retrieved successfully",
                    data={"positions": [p.__dict__ for p in positions]},
                    retry_count=attempt - 1,
                )

            except Exception as e:
                if attempt < retries:
                    wait_time = self.RETRY_DELAY * (self.RETRY_BACKOFF ** (attempt - 1))
                    logger.warning(
                        f"Failed to retrieve positions (attempt {attempt}/{retries}): {str(e)}"
                    )
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Failed to retrieve positions after {retries} attempts")
                    status, msg, error_code = _map_error_to_status(e, attempt)
                    return ApiResponse(
                        status=status,
                        message=msg,
                        error_code=error_code,
                        retry_count=attempt,
                    )

        return ApiResponse(
            status=ApiStatus.RETRY_EXHAUSTED,
            message="Failed to retrieve positions after all retries",
            error_code="MAX_RETRIES_EXHAUSTED",
            retry_count=retries,
        )

    # ========================================================================
    # Internal Helpers
    # ========================================================================

    def _create_client(self) -> SmartConnect:
        """Create a new SmartConnect client."""
        if not SmartConnect:
            raise ImportError("SmartApi package not installed")

        client = SmartConnect(api_key=self.token_manager.api_key)
        token = self.token_manager.get_valid_token()
        client.setAccessToken(token)

        return client

    def _apply_rate_limit(self) -> None:
        """Apply rate limiting between API calls."""
        elapsed = time.time() - self._last_request_time
        if elapsed < 0.1:  # Minimum 100ms between requests
            time.sleep(0.1 - elapsed)
        self._last_request_time = time.time()

    def _call_api(
        self,
        api_func,
        operation: str,
        attempt: int,
        max_attempts: int,
    ) -> Dict[str, Any]:
        """
        Call broker API with error handling.

        Args:
            api_func: Callable that makes the API call
            operation: Name of operation for logging
            attempt: Current attempt number
            max_attempts: Total attempts

        Returns:
            API response

        Raises:
            BrokerAuthError: If authentication fails
            BrokerRateLimitError: If rate limited
            BrokerConnectionError: If connection fails
            Exception: For other errors
        """
        try:
            response = api_func()

            if not response or not response.get("status"):
                raise BrokerOrderError(f"Invalid {operation} response: {response}")

            if response.get("status") != "Success" and response.get("status") != 1:
                error_msg = response.get("message", "Unknown error")

                if "rate limit" in error_msg.lower():
                    raise BrokerRateLimitError(error_msg)

                if "unauthorized" in error_msg.lower() or "token" in error_msg.lower():
                    raise BrokerAuthError(error_msg)

                raise BrokerOrderError(f"{operation} failed: {error_msg}")

            return response

        except SmartApiException as e:
            error_msg = str(e).lower()

            if "rate limit" in error_msg:
                raise BrokerRateLimitError(str(e))

            if "unauthorized" in error_msg or "token" in error_msg:
                raise BrokerAuthError(str(e))

            raise BrokerConnectionError(str(e))

    def _build_order_params(self, order_request: OrderRequest) -> Dict[str, Any]:
        """Build order parameters for Angel One API."""
        return {
            "variety": "NORMAL",
            "tradingsymbol": order_request.symbol,
            "symboltoken": self._get_instrument_token(order_request.symbol),
            "transactiontype": order_request.direction,
            "exchange": self._get_exchange(order_request.symbol),
            "ordertype": order_request.order_type,
            "producttype": order_request.product,
            "quantity": str(order_request.quantity),
            "price": str(order_request.price) if order_request.order_type != "MARKET" else "0",
            "triggerprice": str(order_request.stop_loss or 0),
            "disclosedquantity": "0",
            "validity": order_request.validity,
        }

    def _get_instrument_token(self, symbol: str) -> str:
        """Get instrument token for symbol."""
        # This would typically look up from cached instrument master
        # For now, returning placeholder
        return "token_" + symbol.replace("-", "_")

    def _get_exchange(self, symbol: str) -> str:
        """Determine exchange based on symbol."""
        if symbol.endswith("-EQ") or symbol.endswith("-BL") or symbol.endswith("-TS"):
            return "NSE"
        if symbol.endswith("-BE") or symbol.endswith("-BO"):
            return "BSE"
        return "NSE"

    def _extract_order_id(self, response: Dict[str, Any]) -> Optional[str]:
        """Extract order ID from broker response."""
        if not response:
            return None

        data = response.get("data", {})
        return data.get("orderid") or data.get("order_id")

    def _parse_orders(self, response: Dict[str, Any]) -> List[Order]:
        """Parse orders from broker response."""
        orders = []
        orders_data = response.get("data", [])

        if not isinstance(orders_data, list):
            orders_data = [orders_data] if orders_data else []

        for order_data in orders_data:
            try:
                order = Order(
                    order_id=order_data.get("orderid", ""),
                    symbol=order_data.get("tradingsymbol", ""),
                    direction=order_data.get("transactiontype", ""),
                    quantity=int(order_data.get("quantity", 0)),
                    price=float(order_data.get("price", 0)),
                    status=order_data.get("orderstatus", ""),
                    order_type=order_data.get("ordertype", ""),
                    timestamp=datetime.now(),
                )
                orders.append(order)
            except Exception as e:
                logger.warning(f"Failed to parse order: {str(e)}")

        return orders

    def _parse_positions(self, response: Dict[str, Any]) -> List[Position]:
        """Parse positions from broker response."""
        positions = []
        positions_data = response.get("data", [])

        if not isinstance(positions_data, list):
            positions_data = [positions_data] if positions_data else []

        for pos_data in positions_data:
            try:
                position = Position(
                    symbol=pos_data.get("tradingsymbol", ""),
                    quantity=int(pos_data.get("netquantity", 0)),
                    entry_price=float(pos_data.get("avgprice", 0)),
                    current_price=float(pos_data.get("lastprice", 0)),
                    pnl=float(pos_data.get("pnl", 0)),
                    pnl_pct=float(pos_data.get("pnlpercent", 0)),
                    direction="BUY" if int(pos_data.get("netquantity", 0)) > 0 else "SELL",
                    product=pos_data.get("producttype", ""),
                )
                positions.append(position)
            except Exception as e:
                logger.warning(f"Failed to parse position: {str(e)}")

        return positions


# ============================================================================
# Module-level Factory
# ============================================================================

_global_service: Optional[AngelService] = None


def get_angel_service(token_manager: Optional[TokenManager] = None) -> AngelService:
    """
    Get global Angel Service instance (singleton pattern).

    This ensures a single point of contact for all broker interactions.

    Args:
        token_manager: Optional TokenManager (only used on first call)

    Returns:
        AngelService instance
    """
    global _global_service

    if _global_service is None:
        _global_service = AngelService(token_manager=token_manager)

    return _global_service


def reset_angel_service() -> None:
    """Reset the global service (for testing/cleanup)."""
    global _global_service
    _global_service = None
