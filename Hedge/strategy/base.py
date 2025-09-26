from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Union
import uuid
from account import FyersAccount

@dataclass
class Position:
    symbol: str
    qty: int
    entry_price: float
    entry_time: datetime
    side: str  # 'BUY' or 'SELL'
    product_type: str  # 'INTRADAY', 'MARGIN', 'CNC'
    order_id: str
    status: str
    pnl: float = 0
    exit_price: float = 0
    exit_time: Optional[datetime] = None

@dataclass
class Order:
    order_id: str
    symbol: str
    qty: int
    price: float
    side: str
    product_type: str
    order_type: str  # 'MARKET', 'LIMIT', 'SL', 'SL-M'
    status: str
    timestamp: datetime
    trigger_price: float = 0

class BaseStrategy:
    """Base class for implementing trading strategies"""
    
    def __init__(self, fyers: FyersAccount, capital: float = 1000000):
        self.fyers = fyers
        self.capital = capital
        self.available_margin = capital
        self.positions: Dict[str, Position] = {}
        self.orders: Dict[str, Order] = {}
        self.trades_history: List[Position] = []
        self.order_history: List[Order] = []

    def get_ltp(self, symbol: str) -> float:
        """Get Last Traded Price for a symbol"""
        try:
            quotes = self.fyers.execute_api_call('quotes', {
                "symbols": symbol
            })
            if isinstance(quotes, dict) and 'd' in quotes:
                for quote in quotes['d']:
                    if 'v' in quote and isinstance(quote['v'], dict):
                        return float(quote['v'].get('lp', 0))
            return 0
        except Exception as e:
            print(f"Error fetching LTP for {symbol}: {e}")
            return 0

    def get_market_depth(self, symbol: str) -> Dict:
        """Get market depth for a symbol"""
        try:
            depth = self.fyers.execute_api_call('depth', {
                "symbol": symbol
            })
            if isinstance(depth, dict) and 'd' in depth:
                return {
                    'bids': depth['d'].get('bids', [])[:5],
                    'asks': depth['d'].get('asks', [])[:5]
                }
            return {'bids': [], 'asks': []}
        except Exception as e:
            print(f"Error fetching depth for {symbol}: {e}")
            return {'bids': [], 'asks': []}

    def place_order(self, symbol: str, qty: int, side: str, 
                   order_type: str = 'MARKET', price: float = 0, 
                   trigger_price: float = 0, product_type: str = 'INTRADAY') -> str:
        """Place a new order"""
        try:
            order_id = str(uuid.uuid4())
            
            # Validate parameters
            if qty <= 0:
                raise ValueError("Quantity must be positive")
            if side not in ['BUY', 'SELL']:
                raise ValueError("Invalid side")
            if order_type not in ['MARKET', 'LIMIT', 'SL', 'SL-M']:
                raise ValueError("Invalid order type")
            if product_type not in ['INTRADAY', 'MARGIN', 'CNC']:
                raise ValueError("Invalid product type")

            # Get current market price if needed
            market_price = price if price > 0 else self.get_ltp(symbol)
            if not market_price:
                raise ValueError(f"Unable to get price for {symbol}")

            # Check margin requirement
            margin_required = qty * market_price
            if margin_required > self.available_margin:
                raise ValueError(f"Insufficient margin. Required: {margin_required}, Available: {self.available_margin}")

            # Create order object
            order = Order(
                order_id=order_id,
                symbol=symbol,
                qty=qty,
                price=price,
                side=side,
                product_type=product_type,
                order_type=order_type,
                status='PENDING',
                timestamp=datetime.now(),
                trigger_price=trigger_price
            )

            # Store order
            self.orders[order_id] = order

            # Execute immediately if market order
            if order_type == 'MARKET':
                self._execute_order(order_id)

            return order_id

        except Exception as e:
            raise Exception(f"Order placement failed: {str(e)}")

    def modify_order(self, order_id: str, new_qty: Optional[int] = None,
                    new_price: Optional[float] = None) -> bool:
        """Modify an existing order"""
        try:
            if order_id not in self.orders:
                raise ValueError("Order not found")

            order = self.orders[order_id]
            if order.status != 'PENDING':
                raise ValueError("Can only modify pending orders")

            if new_qty is not None:
                if new_qty <= 0:
                    raise ValueError("Quantity must be positive")
                order.qty = new_qty

            if new_price is not None:
                if new_price <= 0:
                    raise ValueError("Price must be positive")
                order.price = new_price

            return True

        except Exception as e:
            raise Exception(f"Order modification failed: {str(e)}")

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an existing order"""
        try:
            if order_id not in self.orders:
                raise ValueError("Order not found")

            order = self.orders[order_id]
            if order.status not in ['PENDING', 'OPEN']:
                raise ValueError("Can only cancel pending or open orders")

            order.status = 'CANCELLED'
            self.order_history.append(order)
            del self.orders[order_id]

            return True

        except Exception as e:
            raise Exception(f"Order cancellation failed: {str(e)}")

    def close_position(self, symbol: str) -> bool:
        """Close an open position"""
        try:
            if symbol not in self.positions:
                raise ValueError("Position not found")

            position = self.positions[symbol]
            exit_price = self.get_ltp(symbol)
            if not exit_price:
                raise ValueError(f"Unable to get exit price for {symbol}")

            # Calculate P&L
            if position.side == 'BUY':
                pnl = (exit_price - position.entry_price) * position.qty
            else:
                pnl = (position.entry_price - exit_price) * position.qty

            # Update position
            position.exit_price = exit_price
            position.exit_time = datetime.now()
            position.pnl = pnl
            position.status = 'CLOSED'

            # Update capital and margin
            self.capital += pnl
            self.available_margin += position.qty * position.entry_price

            # Move to history
            self.trades_history.append(position)
            del self.positions[symbol]

            return True

        except Exception as e:
            raise Exception(f"Position closure failed: {str(e)}")

    def get_portfolio_value(self) -> float:
        """Get current portfolio value"""
        portfolio_value = self.capital

        for position in self.positions.values():
            current_price = self.get_ltp(position.symbol)
            if current_price:
                if position.side == 'BUY':
                    pnl = (current_price - position.entry_price) * position.qty
                else:
                    pnl = (position.entry_price - current_price) * position.qty
                portfolio_value += pnl

        return portfolio_value

    def _execute_order(self, order_id: str) -> bool:
        """Internal method to execute an order"""
        try:
            order = self.orders[order_id]
            execution_price = order.price if order.price > 0 else self.get_ltp(order.symbol)
            if not execution_price:
                raise ValueError(f"Unable to get execution price for {order.symbol}")

            # Update margin
            margin_required = order.qty * execution_price
            self.available_margin -= margin_required

            # Create position
            position = Position(
                symbol=order.symbol,
                qty=order.qty,
                entry_price=execution_price,
                entry_time=datetime.now(),
                side=order.side,
                product_type=order.product_type,
                order_id=order_id,
                status='OPEN'
            )

            # Update order status
            order.status = 'EXECUTED'
            self.order_history.append(order)
            del self.orders[order_id]

            # Store position
            self.positions[order.symbol] = position

            return True

        except Exception as e:
            raise Exception(f"Order execution failed: {str(e)}")