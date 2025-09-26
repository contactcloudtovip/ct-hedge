from datetime import datetime, time, timedelta
from typing import Dict, List, Optional, Tuple
from .base import BaseStrategy
import pandas as pd
import asyncio

class FifteenDailyStrategy(BaseStrategy):
    """15-minute BANKNIFTY Options Trading Strategy"""
    
    def __init__(self, fyers, capital=1000000):
        super().__init__(fyers, capital)
        self.index_symbol = "NSE:NIFTYBANK-INDEX"
        self.timeframes = [
            "09:30", "09:45", "10:00", "10:15", "10:30", "10:45",
            "11:00", "11:15", "11:30", "11:45", "12:00", "12:15",
            "12:30", "12:45", "13:00", "13:15", "13:30", "13:45",
            "14:00", "14:15", "14:30", "14:45", "15:00"
        ]
        self.lot_size = 35  # BANKNIFTY lot size
        self.trades = []  # Track all trades
        self.active_positions = []  # Track current positions
        self.prev_candle = None  # Previous candle data

    async def _get_candle_data(self, timestamp: datetime) -> Optional[Dict]:
        """Get historical candle data from Fyers"""
        try:
            from_date = timestamp.strftime('%Y-%m-%d')
            to_date = from_date
            
            data = self.fyers.execute_api_call('history', {
                "symbol": self.index_symbol,
                "resolution": "15",
                "date_format": "1",
                "range_from": from_date,
                "range_to": to_date,
                "cont_flag": "1"
            })
            
            if isinstance(data, dict) and data.get('candles'):
                target_time = timestamp.strftime('%H:%M')
                for candle_data in data['candles']:
                    candle_time = datetime.fromtimestamp(candle_data[0]).strftime('%H:%M')
                    if candle_time == target_time:
                        return {
                            'timestamp': timestamp,
                            'open': candle_data[1],
                            'high': candle_data[2],
                            'low': candle_data[3],
                            'close': candle_data[4],
                            'volume': candle_data[5]
                        }
            return None
            
        except Exception as e:
            print(f"Error fetching candle data: {e}")
            return None

    async def _get_eligible_options(self, candle: Dict) -> Dict[str, List]:
        """Get CE/PE options with LTP between 700-1000"""
        try:
            # Calculate ATM strike
            spot_price = candle['close']
            atm_strike = round(spot_price / 100) * 100
            
            # Get ±1000 points strikes
            strikes = range(atm_strike - 1000, atm_strike + 1000, 100)
            
            ce_options = []
            pe_options = []
            
            for strike in strikes:
                ce_symbol = f"NFO:BANKNIFTY25SEP{strike}CE"
                pe_symbol = f"NFO:BANKNIFTY25SEP{strike}PE"
                
                ce_ltp = self.get_ltp(ce_symbol)
                if 700 <= ce_ltp <= 1000:
                    ce_options.append({
                        'symbol': ce_symbol,
                        'strike': strike,
                        'ltp': ce_ltp
                    })
                
                pe_ltp = self.get_ltp(pe_symbol)
                if 700 <= pe_ltp <= 1000:
                    pe_options.append({
                        'symbol': pe_symbol,
                        'strike': strike,
                        'ltp': pe_ltp
                    })
            
            return {
                'CE': sorted(ce_options, key=lambda x: x['ltp'], reverse=True),
                'PE': sorted(pe_options, key=lambda x: x['ltp'], reverse=True)
            }
            
        except Exception as e:
            print(f"Error getting eligible options: {e}")
            return {'CE': [], 'PE': []}

    def _is_breakout(self, current_price: float, candle: Dict) -> bool:
        """Check if price breaks previous candle's close"""
        if not self.current_candle:
            return False
        return current_price > self.current_candle['close']

    async def _enter_position(self, symbol: str, option_type: str, qty: int) -> bool:
        """Enter a new position"""
        try:
            order_id = self.place_order(
                symbol=symbol,
                qty=qty,
                side='BUY',
                order_type='MARKET'
            )
            if order_id:
                self.active_positions.append({
                    'symbol': symbol,
                    'type': option_type,
                    'entry_time': datetime.now(),
                    'qty': qty,
                    'order_id': order_id
                })
                return True
            return False
            
        except Exception as e:
            print(f"Error entering position: {e}")
            return False

    async def _close_positions(self) -> List:
        """Close all active positions"""
        exits = []
        for position in self.active_positions:
            try:
                exit_price = self.get_ltp(position['symbol'])
                if self.close_position(position['symbol']):
                    exits.append({
                        'symbol': position['symbol'],
                        'exit_time': datetime.now(),
                        'exit_price': exit_price,
                        'pnl': 0  # Calculate P&L
                    })
            except Exception as e:
                print(f"Error closing position {position['symbol']}: {e}")
        
        self.active_positions = []
        return exits

    async def _process_candle(self, candle: Dict):
        """Process each 15-minute candle"""
        try:
            print(f"\nProcessing candle at {candle['timestamp']}")
            print(f"Open: {candle['open']}, High: {candle['high']}")
            print(f"Low: {candle['low']}, Close: {candle['close']}")

            # Get eligible options for trading
            print("\nFetching eligible options...")
            options = await self._get_eligible_options(candle)
            print(f"Found {len(options['CE'])} CE and {len(options['PE'])} PE options")

            # First candle of the day
            if not self.prev_candle:
                print("\nChecking for first entry...")
                print(f"CE candidates (700-1000): {len(options['CE'])}")
                print(f"PE candidates (700-1000): {len(options['PE'])}")

                # Enter position if we have options in range
                if options['CE'] or options['PE']:
                    # Take option with highest LTP between 700-1000
                    all_options = options['CE'] + options['PE']
                    best_option = max(all_options, key=lambda x: x['ltp'])
                    
                    print(f"\nSelected option for first entry:")
                    print(f"Symbol: {best_option['symbol']}")
                    print(f"Strike: {best_option['strike']}")
                    print(f"LTP: {best_option['ltp']}")
                    
                    # Enter position
                    await self._enter_position(
                        symbol=best_option['symbol'],
                        option_type='CE' if 'CE' in best_option['symbol'] else 'PE',
                        qty=self.lot_size
                    )
            
            # Close positions at candle close
            if self.active_positions:
                print("\nClosing positions at candle close")
                exits = await self._close_positions()
                self.trades.extend(exits)
            
            self.prev_candle = candle
            
        except Exception as e:
            print(f"Error processing candle: {e}")
            
    async def run_backtest(self, start_date: datetime, end_date: datetime):
        """Run backtest for specified date range"""
        print(f"\nStarting backtest from {start_date} to {end_date}")
        
        current_date = start_date
        while current_date <= end_date:
            if current_date.weekday() < 5:  # Skip weekends
                print(f"\nProcessing date: {current_date.strftime('%Y-%m-%d')}")
                
                # Reset previous candle for new day
                self.prev_candle = None
                
                for timeframe in self.timeframes:
                    hour, minute = map(int, timeframe.split(':'))
                    current_time = current_date.replace(hour=hour, minute=minute)
                    
                    print(f"\nProcessing time slot: {timeframe}")
                    candle = await self._get_candle_data(current_time)
                    
                    if candle:
                        print("Got candle data, processing...")
                        await self._process_candle(candle)
                    else:
                        print("No candle data available")
                        
            current_date += timedelta(days=1)
            
        # Print backtest summary
        print("\nBacktest complete. Total trades:", len(self.trades))
        
        if self.trades:
            total_pnl = sum(trade['pnl'] for trade in self.trades)
            win_trades = sum(1 for trade in self.trades if trade['pnl'] > 0)
            
            print("\nBacktest Results:")
            print(f"Total Trades: {len(self.trades)}")
            print(f"Winning Trades: {win_trades}")
            print(f"Win Rate: {(win_trades/len(self.trades))*100:.1f}%")
            print(f"Total P&L: ₹{total_pnl:,.2f}")
        else:
            print("No trades executed during backtest period")