from datetime import datetime
from account import FyersAccount
from strategy.fifteen_daily import FifteenDailyStrategy

async def main():
    # Initialize account
    fyers = FyersAccount(accounts)
    
    # Create strategy
    strategy = FifteenDailyStrategy(fyers)
    
    # Run backtest
    start_date = datetime(2024, 3, 1)
    end_date = datetime.now()
    await strategy.run_backtest(start_date, end_date)

if __name__ == "__main__":
    asyncio.run(main())