from account import FyersAccount
from strategy.simple_strategy import SimpleOptionStrategy
import asyncio

async def main():
    try:
        # Configure account
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

        # Initialize Fyers account
        fyers = FyersAccount(accounts)
        
        # Create and run strategy
        strategy = SimpleOptionStrategy(fyers, capital=1000000)
        await strategy.run()

    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())