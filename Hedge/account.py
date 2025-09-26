import os
import json
import time
from fyers_apiv3 import fyersModel
import webbrowser
from urllib.parse import parse_qs, urlparse
from pathlib import Path
from collections import deque
from datetime import datetime

class FyersError:
    """Fyers API Error Codes and Messages"""
    ERRORS = {
        # Auth Errors
        "expired_token": ["s-1", "Token is expired"],
        "invalid_token": ["s-2", "Invalid token"],
        "token_mismatch": ["s-4", "Token mismatch"],
        "invalid_key": ["s-5", "Invalid key"],
        
        # Rate Limits
        "rate_limit": ["s-3", "Rate limit reached"],
        "too_many_requests": ["429", "Too many requests"],
        
        # API Errors
        "invalid_param": ["error-100", "Invalid parameter"],
        "missing_param": ["error-101", "Missing parameter"],
        "invalid_credentials": ["error-102", "Invalid credentials"],
        "market_closed": ["error-103", "Market is closed"]
    }

class FyersLoadBalancer:
    def __init__(self):
        self.active_accounts = deque()  # [{client_id, model, calls, last_reset}]
        self.calls_per_minute = 100
        self._current_account = None  # Add this line
        
    def add_account(self, client_id, fyers_model):
        """Add an authenticated account to the pool"""
        self.active_accounts.append({
            'client_id': client_id,
            'model': fyers_model,
            'calls': 0,
            'last_reset': datetime.now()
        })
        
    def get_next_account(self):
        """Get next available account in round-robin fashion"""
        if not self.active_accounts:
            raise Exception("No active accounts available")
        
        # Reset counters for accounts that have passed 1 minute
        now = datetime.now()
        for account in self.active_accounts:
            if (now - account['last_reset']).seconds >= 60:
                account['calls'] = 0
                account['last_reset'] = now
        
        # Find first account under rate limit
        for _ in range(len(self.active_accounts)):
            self.active_accounts.rotate(-1)
            if self.active_accounts[0]['calls'] < self.calls_per_minute:
                self._current_account = self.active_accounts[0]  # Add this line
                return self._current_account
                
        raise Exception("All accounts have reached rate limit")

    @property
    def current_account(self):
        """Get current active account"""
        if not self._current_account:
            self._current_account = self.get_next_account()
        return self._current_account

class FyersAccount:
    SESSION_FILE = "fyers_sessions.json"
    
    def __init__(self, accounts_config):
        self.accounts = accounts_config
        self.balancer = FyersLoadBalancer()
        self._initialize_accounts()
        
    def _initialize_accounts(self):
        """Initialize accounts from saved sessions or fresh login"""
        if self._load_sessions():
            return
            
        print("No valid sessions found. Logging in to all accounts...")
        for account in self.accounts:
            try:
                fyers_model = self._login_account(account)
                self.balancer.add_account(account['client_id'], fyers_model)
                print(f"Successfully logged in account {account['client_id']}")
            except Exception as e:
                print(f"Failed to initialize account {account['client_id']}: {e}")
                
        if not self.balancer.active_accounts:
            raise Exception("No accounts could be initialized")
        self._save_sessions()
        
    def _login_account(self, account):
        """Login to Fyers account and return FyersModel instance"""
        try:
            # Initialize session model with all required parameters
            session = fyersModel.SessionModel(
                client_id=account['client_id'],
                secret_key=account['secret_key'],
                redirect_uri=account['redirect_uri'],
                response_type=account.get('response_type', 'code'),
                grant_type=account.get('grant_type', 'authorization_code'),
                state=account.get('state', 'sample')
            )
            
            # Generate auth URL and get authorization code
            auth_url = session.generate_authcode()
            print(f"\nLogin URL for account {account['client_id']}:")
            print(auth_url)
            webbrowser.open(auth_url, new=2)
            
            print("\nPlease authorize in browser and paste the redirect URL here:")
            redirect_url = input().strip()
            
            # Parse auth code from redirect URL
            parsed = urlparse(redirect_url)
            auth_code = parse_qs(parsed.query).get('auth_code', [None])[0]
            if not auth_code:
                raise ValueError("Failed to get authorization code")
                
            # Generate access token
            session.set_token(auth_code)
            response = session.generate_token()
            
            if not response:
                raise ValueError("Empty response from token generation")
            
            if 'error' in response:
                raise ValueError(f"Token generation failed: {response['error']}")
                
            if 'access_token' not in response:
                raise ValueError("No access token in response")
            
            # Create and return FyersModel instance
            return fyersModel.FyersModel(
                token=response['access_token'],
                is_async=False,
                client_id=account['client_id'],
                log_path=""
            )
            
        except Exception as e:
            raise Exception(f"Login failed for {account['client_id']}: {str(e)}")
        
    def _load_sessions(self):
        """Load existing valid sessions"""
        try:
            if not Path(self.SESSION_FILE).exists():
                return False
                
            with open(self.SESSION_FILE, 'r') as f:
                data = json.load(f)
                
            successful = 0
            for session in data.get('sessions', []):
                if time.time() - session.get('timestamp', 0) < 24 * 3600:
                    try:
                        model = fyersModel.FyersModel(
                            token=session['access_token'],
                            is_async=False,
                            client_id=session['account']['client_id'],
                            log_path=""
                        )
                        self.balancer.add_account(session['account']['client_id'], model)
                        successful += 1
                    except Exception as e:
                        print(f"Failed to load session for {session['account']['client_id']}: {e}")
                        
            print(f"Loaded {successful} valid sessions")
            return successful > 0
            
        except Exception as e:
            print(f"Failed to load sessions: {e}")
            return False
            
    def _save_sessions(self):
        """Save current sessions to file"""
        sessions = {
            'sessions': [
                {
                    'account': next(acc for acc in self.accounts if acc['client_id'] == account['client_id']),
                    'access_token': account['model'].token,
                    'timestamp': time.time()
                }
                for account in self.balancer.active_accounts
            ]
        }
        with open(self.SESSION_FILE, 'w') as f:
            json.dump(sessions, f)
            
    def execute_api_call(self, api_method, *args, **kwargs):
        """Execute API call with load balancing and error handling"""
        for _ in range(len(self.balancer.active_accounts)):
            try:
                account = self.balancer.current_account  # Use property instead
                result = getattr(account['model'], api_method)(*args, **kwargs)
                account['calls'] += 1
                
                # Add account details to result if it's a dictionary
                if isinstance(result, dict):
                    result['account_info'] = {
                        'client_id': account['client_id'],
                        'calls_made': account['calls'],
                        'last_reset': account['last_reset'].strftime('%Y-%m-%d %H:%M:%S'),
                        'rate_limit': self.balancer.calls_per_minute
                    }
                return result
                
            except Exception as e:
                error_str = str(e).lower()
                
                # Handle token errors
                if any(code.lower() in error_str or msg.lower() in error_str 
                      for code, msg in [FyersError.ERRORS[k] for k in ['expired_token', 'invalid_token', 'token_mismatch']]):
                    try:
                        acc_config = next(acc for acc in self.accounts if acc['client_id'] == account['client_id'])
                        new_model = self._login_account(acc_config)
                        account['model'] = new_model
                        account['calls'] = 0
                        account['last_reset'] = datetime.now()
                        self._save_sessions()
                        continue
                    except Exception as login_error:
                        print(f"Failed to refresh token for {account['client_id']}: {login_error}")
                
                # For rate limit errors, try next account
                if any(code.lower() in error_str or msg.lower() in error_str 
                      for code, msg in [FyersError.ERRORS[k] for k in ['rate_limit', 'too_many_requests']]):
                    self.balancer._current_account = None  # Reset current account
                    continue
                    
                # For other errors, raise immediately
                raise Exception(f"API Error ({account['client_id']}): {str(e)}")
                
        raise Exception("All accounts failed or reached rate limits")