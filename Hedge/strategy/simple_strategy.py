from datetime import datetime
from .base import BaseStrategy
import asyncio

class SimpleOptionStrategy(BaseStrategy):
    """
    A simple options trading strategy that:
    1. Monitors BANKNIFTY options in a price range
    2. Places orders based on specific criteria
    3. Manages positions with defined risk parameters
    """
    
    def __init__(self, fyers, capital=1000000):
        super().__init__(fyers, capital)
        self.index_symbol = "NSE:NIFTYBANK-INDEX"
        self.price_range = (400, 1600)  # LTP range to monitor
        self.max_positions = 2  # Maximum number of concurrent positions
        self.stop_loss_pct = 0.15  # 15% stop loss
        self.target_pct = 0.30  # 30% target
        self.qty = 25  # Standard quantity for orders
        
    async def run(self):
        """Main strategy execution loop"""
        print(f"\nStarting Simple Option Strategy")
        print(f"Initial Capital: ₹{self.capital:,.2f}")
        
        while True:
            try:
                # Get current spot price
                spot_price = self.get_ltp(self.index_symbol)
                print(f"\nBANKNIFTY Spot: {spot_price}")
                
                # Generate strike prices
                base_strike = round(spot_price / 100) * 100
                strikes = range(base_strike - 1000, base_strike + 1000, 100)
                
                # Get option symbols
                option_symbols = []
                for strike in strikes:
                    ce_symbol = f"NFO:BANKNIFTY25SEP{strike}CE"
                    pe_symbol = f"NFO:BANKNIFTY25SEP{strike}PE"
                    option_symbols.extend([ce_symbol, pe_symbol])
                
                # Monitor existing positions
                await self._manage_positions()
                
                # Look for new opportunities if we have capacity
                if len(self.positions) < self.max_positions:
                    await self._scan_opportunities(option_symbols)
                
                # Print portfolio status
                self._print_status()
                
                # Wait before next iteration
                await asyncio.sleep(5)
                
            except Exception as e:
                print(f"Strategy execution error: {e}")
                await asyncio.sleep(5)
    
    async def _manage_positions(self):
        """Manage existing positions"""
        for symbol, position in list(self.positions.items()):
            current_price = self.get_ltp(symbol)
            if not current_price:
                continue
                
            entry_price = position.entry_price
            pnl_pct = (current_price - entry_price) / entry_price
            
            # Check stop loss and target
            if position.side == 'BUY':
                if pnl_pct <= -self.stop_loss_pct or pnl_pct >= self.target_pct:
                    print(f"\nClosing position {symbol}")
                    print(f"Entry: {entry_price:.2f}, Current: {current_price:.2f}")
                    print(f"P&L: {pnl_pct:.1%}")
                    self.close_position(symbol)
            else:
                if pnl_pct >= self.stop_loss_pct or pnl_pct <= -self.target_pct:
                    print(f"\nClosing position {symbol}")
                    print(f"Entry: {entry_price:.2f}, Current: {current_price:.2f}")
                    print(f"P&L: {pnl_pct:.1%}")
                    self.close_position(symbol)
    
    async def _scan_opportunities(self, symbols):
        """Scan for new trading opportunities"""
        min_ltp, max_ltp = self.price_range
        
        for symbol in symbols:
            try:
                ltp = self.get_ltp(symbol)
                if not min_ltp <= ltp <= max_ltp:
                    continue
                    
                # Get market depth
                depth = self.get_market_depth(symbol)
                if not depth['bids'] or not depth['asks']:
                    continue
                
                # Simple criteria: Significant bid-ask imbalance
                total_bid_qty = sum(bid['qty'] for bid in depth['bids'])
                total_ask_qty = sum(ask['qty'] for ask in depth['asks'])
                
                if total_bid_qty > total_ask_qty * 2:  # Strong buying pressure
                    print(f"\nBuy signal for {symbol}")
                    print(f"Bid Qty: {total_bid_qty}, Ask Qty: {total_ask_qty}")
                    order_id = self.place_order(
                        symbol=symbol,
                        qty=self.qty,
                        side='BUY',
                        order_type='MARKET'
                    )
                    print(f"Placed buy order: {order_id}")
                    break
                    
                elif total_ask_qty > total_bid_qty * 2:  # Strong selling pressure
                    print(f"\nSell signal for {symbol}")
                    print(f"Bid Qty: {total_bid_qty}, Ask Qty: {total_ask_qty}")
                    order_id = self.place_order(
                        symbol=symbol,
                        qty=self.qty,
                        side='SELL',
                        order_type='MARKET'
                    )
                    print(f"Placed sell order: {order_id}")
                    break
                
            except Exception as e:
                print(f"Error processing {symbol}: {e}")
    
    def _print_status(self):
        """Print current strategy status"""
        print("\n=== Strategy Status ===")
        print(f"Capital: ₹{self.capital:,.2f}")
        print(f"Available Margin: ₹{self.available_margin:,.2f}")
        print(f"Portfolio Value: ₹{self.get_portfolio_value():,.2f}")
        
        if self.positions:
            print("\nActive Positions:")
            for symbol, pos in self.positions.items():
                current_price = self.get_ltp(symbol)
                if current_price:
                    pnl = (current_price - pos.entry_price) * pos.qty
                    pnl_pct = (current_price - pos.entry_price) / pos.entry_price
                    print(f"\n{symbol}:")
                    print(f"  Side: {pos.side}")
                    print(f"  Qty: {pos.qty}")
                    print(f"  Entry: ₹{pos.entry_price:,.2f}")
                    print(f"  Current: ₹{current_price:,.2f}")
                    print(f"  P&L: ₹{pnl:,.2f} ({pnl_pct:.1%})")