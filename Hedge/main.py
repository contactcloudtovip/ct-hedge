import os
import time
from datetime import datetime
from account import FyersAccount
from strategy.fifteen_daily import FifteenDailyStrategy
import asyncio

def test_load_balancer(fyers):
    """Test load balancer functionality"""
    print("\n=== Testing Load Balancer ===")
    
    # Track API calls per account
    account_usage = {}
    
    for i in range(10):
        try:
            print(f"\nAPI Call #{i+1}")
            result = fyers.execute_api_call('get_profile')
            
            # Get client_id, handle both dict and None responses
            client_id = result.get('client_id') if isinstance(result, dict) else 'Unknown'
            
            # Track account usage
            account_usage[client_id] = account_usage.get(client_id, 0) + 1
            
            print(f"Call successful using account: {client_id}")
            
            # Print API response details
            print(f"Response: {result}")
            
            # Small delay to simulate real usage
            time.sleep(0.5)
            
        except Exception as e:
            print(f"Call failed: {e}")
    
    # Print summary
    print("\n=== Load Balancer Summary ===")
    for client_id, calls in account_usage.items():
        print(f"Account {client_id}: {calls} calls")

def test_all_accounts(fyers):
    """Test each account individually and as part of load balancer"""
    print("\n=== Account Details ===")
    for account in fyers.balancer.active_accounts:
        print(f"\nAccount: {account['client_id']}")
        try:
            # Get account details
            profile = account['model'].get_profile()
            funds = account['model'].funds()  # Changed from get_funds() to funds()
            
            # Print profile details
            if isinstance(profile, dict):
                print("\nProfile:")
                print(f"  User ID: {profile.get('fy_id', 'N/A')}")
                print(f"  Name: {profile.get('name', 'N/A')}")
                print(f"  Email: {profile.get('email_id', 'N/A')}")
                print(f"  PAN: {profile.get('pan', 'N/A')}")  # Changed from pan_number to pan
                print(f"  Mobile: {profile.get('mobile_number', 'N/A')}")
                print(f"  Client Type: {profile.get('client_type', 'N/A')}")
            
            # Print funds details - updated structure according to Fyers API V3
            if isinstance(funds, dict):
                fund_detail = funds.get('fund_limit', [{}])[0]
                print("\nFunds:")
                print(f"  Available Balance: ₹{fund_detail.get('available_balance', 0):,.2f}")
                print(f"  Used Margin: ₹{fund_detail.get('utilized_amount', 0):,.2f}")
                print(f"  Total Balance: ₹{fund_detail.get('total_balance', 0):,.2f}")
                print(f"  Opening Balance: ₹{fund_detail.get('opening_balance', 0):,.2f}")
            
            # Print holdings
            try:
                holdings = account['model'].holdings()
                if isinstance(holdings, dict):
                    print("\nHoldings:")
                    for holding in holdings.get('holdings', []):
                        print(f"  {holding.get('symbol', 'N/A')}")
                        print(f"    Quantity: {holding.get('quantity', 0)}")
                        print(f"    Average Price: ₹{holding.get('average_price', 0):,.2f}")
                        print(f"    LTP: ₹{holding.get('ltp', 0):,.2f}")
            except Exception as e:
                print("\nHoldings: Unable to fetch")
            
            print("\nAPI Limits:")
            print(f"  Calls made: {account['calls']}")
            print(f"  Last reset: {account['last_reset'].strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"  Rate limit: {fyers.balancer.calls_per_minute} calls per minute")
            
        except Exception as e:
            print(f"Failed to get account details: {e}")
    
    print("\n=== Testing Load Balancer ===")
    account_usage = {}
    call_results = []
    
    # Make multiple API calls to test load balancing
    for i in range(15):
        try:
            # Rotate between different API calls
            if i % 3 == 0:
                result = fyers.execute_api_call('get_profile')
                api_name = 'Profile'
            elif i % 3 == 1:
                result = fyers.execute_api_call('funds')
                api_name = 'Funds'
            else:
                result = fyers.execute_api_call('positions')
                api_name = 'Positions'
                
            # Get account info from result
            account_info = result.get('account_info', {})
            client_id = account_info.get('client_id')
            calls_made = account_info.get('calls_made')
            last_reset = account_info.get('last_reset')
            
            # Track usage
            account_usage[client_id] = account_usage.get(client_id, 0) + 1
            
            # Record result
            call_results.append({
                'call_number': i + 1,
                'api': api_name,
                'account': client_id,
                'calls_made': calls_made,
                'last_reset': last_reset,
                'success': True
            })
            
            print(f"\nAPI Call #{i+1} ({api_name})")
            print(f"✓ Success using account: {client_id}")
            print(f"  Calls made: {calls_made}")
            print(f"  Last reset: {last_reset}")
            
        except Exception as e:
            call_results.append({
                'call_number': i + 1,
                'api': api_name,
                'account': 'Failed',
                'success': False,
                'error': str(e)
            })
            print(f"\nAPI Call #{i+1} ({api_name})")
            print(f"✗ Failed: {str(e)}")
    
    # Print detailed summary
    print("\n=== Test Summary ===")
    print("\nAccount Usage:")
    for client_id, calls in account_usage.items():
        print(f"\nAccount {client_id}:")
        print(f"  Total calls: {calls}")
        account = next((a for a in fyers.balancer.active_accounts if a['client_id'] == client_id), None)
        if account:
            print(f"  Current rate limit usage: {account['calls']}/100 calls")
            print(f"  Last reset: {account['last_reset'].strftime('%H:%M:%S')}")
    
    print("\nSuccess Rate:")
    success_count = sum(1 for r in call_results if r['success'])
    total_calls = len(call_results)
    success_rate = (success_count / total_calls) * 100
    print(f"Total Calls: {total_calls}")
    print(f"Successful: {success_count}")
    print(f"Success Rate: {success_rate:.1f}%")

async def main():
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
            },
            {
                "client_id": "YSILYC9DO1-100",
                "secret_key": "OSXGUDF322",
                "redirect_uri": "http://127.0.0.1:5000/fyers/callback",
                "response_type": "code",
                "grant_type": "authorization_code",
                "state": "sample"
            }
        ]

        # Initialize Fyers account with load balancer
        print("\nInitializing Fyers account...")
        fyers = FyersAccount(accounts)
        
        # Create strategy instance
        print("\nCreating strategy...")
        strategy = FifteenDailyStrategy(fyers, capital=1000000)
        
        # Set backtest date range
        start_date = datetime(2025, 9, 23)  # First day of current expiry
        end_date = datetime.now()
        
        print(f"\nRunning backtest from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        await strategy.run_backtest(start_date, end_date)
        
        print("\nBacktest complete!")

    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())