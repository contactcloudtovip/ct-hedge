from account import FyersAccount
import time
import json
from datetime import datetime
from pathlib import Path
import asyncio
import websockets
from jinja2 import Template
import webbrowser

class OptionsMonitor:
    def __init__(self, fyers_account):
        self.fyers = fyers_account
        self.template_file = Path(__file__).parent / 'templates' / 'options_dashboard.html'
        self.output_file = Path(__file__).parent / 'options_dashboard.html'
        self.ce_options = {}
        self.pe_options = {}
        
    async def get_symbols_in_range(self, min_ltp=400, max_ltp=1600):
        """Get CE and PE symbols with LTP in specified range"""
        try:
            # Get BANKNIFTY spot price using correct symbol format
            spot_symbol = "NSE:NIFTYBANK-INDEX"  # Corrected symbol name
            quote_params = {
                "symbols": spot_symbol
            }
            
            print("\nFetching BANKNIFTY spot price...")
            spot_quote = self.fyers.execute_api_call('quotes', quote_params)
            print(f"Spot quote response: {spot_quote}")  # Debug print
            
            if isinstance(spot_quote, dict) and 'd' in spot_quote:
                spot_data = spot_quote['d'][0] if spot_quote['d'] else {}
                print(f"Spot data: {spot_data}")  # Debug print
                
                if isinstance(spot_data, dict) and 'v' in spot_data:
                    v_data = spot_data['v']
                    print(f"V data: {v_data}")  # Debug print
                    
                    if isinstance(v_data, dict):
                        spot_price = float(v_data.get('lp', 0))
                        print(f"BANKNIFTY spot price: {spot_price}")
                        
                        if not spot_price:
                            raise ValueError("Unable to get valid spot price")
                            
                        # Calculate strike prices ±2000 points from spot
                        base_strike = round(spot_price / 100) * 100
                        strikes = range(base_strike - 2000, base_strike + 2000, 100)
                        
                        # Get option symbols with correct format
                        option_symbols = []
                        for strike in strikes:
                            # Format: NFO:BANKNIFTY{expiry}{strike}{CE/PE}
                            ce_symbol = f"NSE:BANKNIFTY25SEP{strike}CE"
                            pe_symbol = f"NSE:BANKNIFTY25SEP{strike}PE"
                            option_symbols.extend([ce_symbol, pe_symbol])
                            
                        print(f"\nGenerated {len(option_symbols)} option symbols")
                        print("Sample symbols:")
                        for symbol in option_symbols[:4]:
                            print(f"  {symbol}")
                        
                        # Process options in batches
                        self.ce_options.clear()
                        self.pe_options.clear()
        
                        # Process in batches of 25 for better reliability
                        for i in range(0, len(option_symbols), 25):
                            batch = option_symbols[i:i+25]
                            batch_symbols = ",".join(batch)
                            print(f"\nProcessing batch {i//25 + 1} of {len(option_symbols)//25 + 1}")
                            print(f"Batch symbols: {batch_symbols}")
            
                            try:
                                quotes = self.fyers.execute_api_call('quotes', {
                                    "symbols": batch_symbols
                                })
                                print(f"Batch response: {quotes}")
                
                                if isinstance(quotes, dict) and 'd' in quotes:
                                    for quote_data in quotes['d']:
                                        if 'n' in quote_data and 'v' in quote_data:
                                            symbol = quote_data['n']
                                            v = quote_data['v']
                            
                                            if isinstance(v, dict):
                                                ltp = float(v.get('lp', 0))
                                                print(f"Symbol: {symbol}, LTP: {ltp}")
                                
                                                if min_ltp <= ltp <= max_ltp:
                                                    option_data = {
                                                        'symbol': symbol,
                                                        'ltp': ltp,
                                                        'change': v.get('pc', 0),
                                                        'volume': v.get('v', 0),
                                                        'oi': v.get('oi', 0),
                                                        'depth': self._get_market_depth(symbol)
                                                    }
                                    
                                                    if 'CE' in symbol:
                                                        self.ce_options[symbol] = option_data
                                                        print(f"Added CE option: {symbol} with LTP: {ltp}")
                                                    else:
                                                        self.pe_options[symbol] = option_data
                                                        print(f"Added PE option: {symbol} with LTP: {ltp}")
                                                else:
                                                    print(f"LTP {ltp} out of range ({min_ltp}-{max_ltp}) for {symbol}")
            
                            except Exception as batch_error:
                                print(f"Error processing batch: {batch_error}")
            
                            # Add small delay between batches
                            await asyncio.sleep(0.5)
        
                        print(f"\nFound {len(self.ce_options)} CE and {len(self.pe_options)} PE options in price range")
                        if self.ce_options or self.pe_options:
                            print("\nOptions in range:")
                            for symbol, data in self.ce_options.items():
                                print(f"CE: {symbol} - LTP: {data['ltp']}")
                            for symbol, data in self.pe_options.items():
                                print(f"PE: {symbol} - LTP: {data['ltp']}")
                
                    else:
                        raise ValueError("Invalid spot price data format")
                else:
                    raise ValueError("Invalid spot quote response")
        except Exception as e:
            print(f"Error fetching symbols: {e}")

    def _get_market_depth(self, symbol):
        """Get market depth for a symbol"""
        try:
            depth = self.fyers.execute_api_call('depth', {"symbol": symbol})
            if isinstance(depth, dict) and 'd' in depth:
                bids = depth['d'].get('bids', [])[:5]
                asks = depth['d'].get('asks', [])[:5]
                
                # Ensure exactly 5 rows for bids and asks
                while len(bids) < 5:
                    bids.append({'qty': 0, 'price': 0})
                while len(asks) < 5:
                    asks.append({'qty': 0, 'price': 0})
                    
                return {
                    'bids': bids,
                    'asks': asks
                }
        except Exception as e:
            print(f"Error fetching depth for {symbol}: {e}")
        
        # Return empty depth with 5 rows if anything fails
        empty_rows = [{'qty': 0, 'price': 0} for _ in range(5)]
        return {
            'bids': empty_rows.copy(),
            'asks': empty_rows.copy()
        }
    
    def generate_html(self):
        """Generate HTML dashboard"""
        template = Template('''
<!DOCTYPE html>
<html>
<head>
    <title>Options Monitor</title>
    <style>
        body { font-family: Arial, sans-serif; }
        .container { display: flex; justify-content: space-between; }
        .table-container { width: 48%; }
        table { width: 100%; border-collapse: collapse; margin: 10px 0; }
        th, td { padding: 8px; border: 1px solid #ddd; text-align: right; }
        th { background-color: #f5f5f5; }
        .positive { color: green; }
        .negative { color: red; }
        .depth-table { font-size: 0.9em; margin-top: 5px; }
        .timestamp { text-align: center; margin: 10px 0; }
    </style>
    <script>
        function refreshData() {
            fetch('/update')
                .then(response => response.json())
                .then(data => {
                    updateTable('ce-table', data.ce_options);
                    updateTable('pe-table', data.pe_options);
                    document.getElementById('timestamp').textContent = data.timestamp;
                });
        }
        
        function updateTable(tableId, data) {
            const tbody = document.getElementById(tableId).getElementsByTagName('tbody')[0];
            tbody.innerHTML = '';
            
            for (const [symbol, option] of Object.entries(data)) {
                const row = tbody.insertRow();
                row.innerHTML = `
                    <td>${symbol}</td>
                    <td class="${option.change >= 0 ? 'positive' : 'negative'}">
                        ${option.ltp.toFixed(2)}
                    </td>
                    <td class="${option.change >= 0 ? 'positive' : 'negative'}">
                        ${option.change.toFixed(2)}%
                    </td>
                    <td>${option.volume.toLocaleString()}</td>
                    <td>${option.oi.toLocaleString()}</td>
                    <td>
                        <table class="depth-table">
                            <tr><th>Bid Qty</th><th>Bid</th><th>Ask</th><th>Ask Qty</th></tr>
                            ${option.depth.bids.map((bid, i) => `
                                <tr>
                                    <td>${bid.qty}</td>
                                    <td>${bid.price}</td>
                                    <td>${option.depth.asks[i].price}</td>
                                    <td>${option.depth.asks[i].qty}</td>
                                </tr>
                            `).join('')}
                        </table>
                    </td>
                `;
            }
        }
        
        setInterval(refreshData, 2000);
    </script>
</head>
<body>
    <div class="timestamp">Last Updated: <span id="timestamp">{{ timestamp }}</span></div>
    <div class="container">
        <div class="table-container">
            <h2>Call Options (CE)</h2>
            <table id="ce-table">
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>LTP</th>
                        <th>Change%</th>
                        <th>Volume</th>
                        <th>OI</th>
                        <th>Market Depth</th>
                    </tr>
                </thead>
                <tbody>
                {% for symbol, option in ce_options.items() %}
                    <tr>
                        <td>{{ symbol }}</td>
                        <td class="{{ 'positive' if option.change >= 0 else 'negative' }}">
                            {{ "%.2f"|format(option.ltp) }}
                        </td>
                        <td class="{{ 'positive' if option.change >= 0 else 'negative' }}">
                            {{ "%.2f"|format(option.change) }}%
                        </td>
                        <td>{{ "{:,}".format(option.volume) }}</td>
                        <td>{{ "{:,}".format(option.oi) }}</td>
                        <td>
                            <table class="depth-table">
                                <tr><th>Bid Qty</th><th>Bid</th><th>Ask</th><th>Ask Qty</th></tr>
                                {% for bid in option.depth.bids %}
                                <tr>
                                    <td>{{ bid.qty }}</td>
                                    <td>{{ bid.price }}</td>
                                    <td>{{ option.depth.asks[loop.index0].price }}</td>
                                    <td>{{ option.depth.asks[loop.index0].qty }}</td>
                                </tr>
                                {% endfor %}
                            </table>
                        </td>
                    </tr>
                {% endfor %}
                </tbody>
            </table>
        </div>
        
        <div class="table-container">
            <h2>Put Options (PE)</h2>
            <table id="pe-table">
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>LTP</th>
                        <th>Change%</th>
                        <th>Volume</th>
                        <th>OI</th>
                        <th>Market Depth</th>
                    </tr>
                </thead>
                <tbody>
                {% for symbol, option in pe_options.items() %}
                    <tr>
                        <td>{{ symbol }}</td>
                        <td class="{{ 'positive' if option.change >= 0 else 'negative' }}">
                            {{ "%.2f"|format(option.ltp) }}
                        </td>
                        <td class="{{ 'positive' if option.change >= 0 else 'negative' }}">
                            {{ "%.2f"|format(option.change) }}%
                        </td>
                        <td>{{ "{:,}".format(option.volume) }}</td>
                        <td>{{ "{:,}".format(option.oi) }}</td>
                        <td>
                            <table class="depth-table">
                                <tr><th>Bid Qty</th><th>Bid</th><th>Ask</th><th>Ask Qty</th></tr>
                                {% for bid in option.depth.bids %}
                                <tr>
                                    <td>{{ bid.qty }}</td>
                                    <td>{{ bid.price }}</td>
                                    <td>{{ option.depth.asks[loop.index0].price }}</td>
                                    <td>{{ option.depth.asks[loop.index0].qty }}</td>
                                </tr>
                                {% endfor %}
                            </table>
                        </td>
                    </tr>
                {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
        ''')
        
        html = template.render(
            ce_options=self.ce_options,
            pe_options=self.pe_options,
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )
        
        with open(self.output_file, 'w') as f:
            f.write(html)
        
    async def run(self):
        """Run the monitor"""
        while True:
            await self.get_symbols_in_range()
            self.generate_html()
            await asyncio.sleep(2)