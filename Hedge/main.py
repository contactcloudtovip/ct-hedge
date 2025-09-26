import os
from account import FyersAccount

def main():
    try:
        # Configure multiple accounts
        accounts = [
            {
                "client_id": "YSILYC9DO1-100",
                "secret_key": "OSXGUDF322",
                "redirect_uri": "http://127.0.0.1:5000/fyers/callback"
            },
            {
                "client_id": "KH09N0C9MD-100",
                "secret_key": "5PA1WXH08K",
                "redirect_uri": "http://127.0.0.1:3013/login/fyers"
            }
            # Add more backup accounts as needed
        ]

        # Initialize with multiple accounts
        fyers = FyersAccount(accounts)
        
        # Login will automatically try accounts in sequence and use cached session if available
        api = fyers.login()

        # Example API calls
        profile = api.get_profile()
        print("Profile:", profile)

        funds = api.funds()
        print("Funds:", funds)

        positions = api.positions()
        print("Positions:", positions)

    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()