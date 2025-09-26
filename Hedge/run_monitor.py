from account import FyersAccount
from options_monitor import OptionsMonitor
import asyncio
import webbrowser
from pathlib import Path

def main():
    try:
        # Configure accounts
        accounts = [
            {
                "client_id": "X65ZE2P406-100",
                "secret_key": "A6N30SIICM",
                "redirect_uri": "http://127.0.0.1:5000/",
                "response_type": "code",
                "grant_type": "authorization_code",
                "state": "sample"
            }
        ]

        # Initialize Fyers account with load balancer
        fyers = FyersAccount(accounts)
        
        # Create and run options monitor
        monitor = OptionsMonitor(fyers)
        
        # Open dashboard in browser
        dashboard_path = Path(__file__).parent / 'options_dashboard.html'
        webbrowser.open(f'file://{dashboard_path.absolute()}')
        
        # Run the monitor
        asyncio.run(monitor.run())

    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()