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
            spot_symbol = "NSE:NIFTYBANK-INDEX"
            quote_params = {
                "symbols": spot_symbol
            }
            
            print("\nFetching BANKNIFTY spot price...")
            quote = self.fyers.execute_api_call('quotes', quote_params)
            print(f"Quote response: {quote}")
            
            if isinstance(quote, dict) and 'd' in quote:
                spot_data = quote['d'][0] if quote['d'] else {}
                spot_price = float(spot_data.get('v', {}).get('lp', 0))
                print(f"BANKNIFTY spot price: {spot_price}")
                
                if not spot_price:
                    raise ValueError("Unable to get valid spot price")
                    
                # Calculate strike prices ±2000 points from spot
                base_strike = round(spot_price / 100) * 100
                strikes = range(base_strike - 2000, base_strike + 2000, 100)
                
                # Get current expiry format
                now = datetime.now()
                expiry = f"{now.strftime('%y')}{now.strftime('%b').upper()}"  # Example: MAR24
                
                # Get option symbols with correct format
                option_symbols = []
                for strike in strikes:
                    # Format: BANKNIFTY{Year}{Month}{StrikePrice}{CE/PE}
                    ce_symbol = f"NFO:BANKNIFTY25SEP{expiry}{strike}CE"
                    pe_symbol = f"NFO:BANKNIFTY{expiry}{strike}PE"
                    option_symbols.extend([ce_symbol, pe_symbol])

                    
                print(f"\nGenerated {len(option_symbols)} option symbols")
                print("Sample symbols:")
                for symbol in option_symbols[:4]:
                    print(f"  {symbol}")
                
                # Get quotes in batches of 50
                self.ce_options.clear()
                self.pe_options.clear()
                
                for i in range(0, len(option_symbols), 50):
                    batch = option_symbols[i:i+50]
                    print(batch)
                    quotes = self.fyers.execute_api_call('quotes', {
                        "symbols": ",".join(batch)
                    })
                    
                    if isinstance(quotes, dict) and 'd' in quotes:
                        for quote_data in quotes['d']:
                            # print(quote)
                            symbol = quote_data.get('n', '')
                            ltp = quote_data.get('v', {}).get('lp', 0)
                            
                            if min_ltp < ltp < max_ltp:
                                depth = self._get_market_depth(symbol)
                                option_data = {
                                    'symbol': symbol,
                                    'ltp': ltp,
                                    'change': quote_data.get('v', {}).get('pc', 0),  # Percentage change
                                    'volume': quote_data.get('v', {}).get('v', 0),   # Volume
                                    'oi': quote_data.get('v', {}).get('oi', 0),      # Open Interest
                                    'depth': depth
                                }
                                
                                if symbol.endswith('CE'):
                                    self.ce_options[symbol] = option_data
                                else:
                                    self.pe_options[symbol] = option_data
                
                print(f"\nFound {len(self.ce_options)} CE and {len(self.pe_options)} PE options in price range")
                
            # else:
            #     raise ValueError(f"Invalid quote response format: {quote}")
                
        except Exception as e:
            print(f"Error fetching symbols: {e}")
    
    def _get_market_depth(self, symbol):
        """Get market depth for a symbol"""
        try:
            depth = self.fyers.execute_api_call('depth', {"symbol": symbol})
            return {
                'bids': depth['d']['bids'][:5],
                'asks': depth['d']['asks'][:5]
            }
        except Exception as e:
            print(f"Error fetching depth for {symbol}: {e}")
            return {'bids': [], 'asks': []}
    
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