import os
import json
import time
from fyers_apiv3 import fyersModel
import webbrowser
from urllib.parse import parse_qs, urlparse
from pathlib import Path

class FyersAccount:
    SESSION_FILE = "fyers_sessions.json"
    
    def __init__(self, accounts_config):
        """
        Initialize FyersAccount with multiple account credentials
        
        Args:
            accounts_config: List of dictionaries containing account credentials
            [
                {
                    "client_id": "xxx",
                    "secret_key": "xxx",
                    "redirect_uri": "xxx"
                },
                ...
            ]
        """
        self.accounts = accounts_config
        self.current_account = None
        self.fyers = None
        self._load_session()

    def _load_session(self):
        """Load existing session if available"""
        try:
            if Path(self.SESSION_FILE).exists():
                with open(self.SESSION_FILE, 'r') as f:
                    session_data = json.load(f)
                    
                # Check if session is still valid (less than 24 hours old)
                if time.time() - session_data.get('timestamp', 0) < 24 * 3600:
                    self.current_account = session_data['account']
                    self.fyers = fyersModel.FyersModel(
                        token=session_data['access_token'],
                        is_async=False,
                        client_id=self.current_account['client_id'],
                        log_path=""
                    )
                    print("Loaded existing session")
                    return True
        except Exception as e:
            print(f"Failed to load session: {e}")
        return False

    def _save_session(self, access_token):
        """Save session data to file"""
        session_data = {
            'account': self.current_account,
            'access_token': access_token,
            'timestamp': time.time()
        }
        with open(self.SESSION_FILE, 'w') as f:
            json.dump(session_data, f)

    def _get_auth_code(self):
        """Generate and get the authorization code"""
        # Generate auth URL using SessionModel
        auth_url = self.session.generate_authcode()
        webbrowser.open(auth_url, new=2)
        
        print("Please login to Fyers and authorize the application.")
        print("After authorization, copy the full redirect URL and paste it here:")
        redirect_url = input().strip()
        
        # Parse the authorization code from the URL
        parsed = urlparse(redirect_url)
        auth_code = parse_qs(parsed.query).get('auth_code', [None])[0]
        
        if not auth_code:
            raise ValueError("Failed to get authorization code")
        
        return auth_code

    def _get_access_token(self, auth_code):
        """Get access token using the authorization code"""
        try:
            self.session.set_token(auth_code)
            response = self.session.generate_token()
            
            if not response or not response.get('access_token'):
                raise ValueError("Failed to get access token")
            return response['access_token']
        except Exception as e:
            raise Exception(f"Error getting access token: {str(e)}")

    def _try_login_account(self, account):
        """Try to login with a single account"""
        try:
            self.current_account = account
            self.session = fyersModel.SessionModel(
                client_id=account['client_id'],
                secret_key=account['secret_key'],
                redirect_uri=account['redirect_uri'],
                response_type="code",
                grant_type="authorization_code",
                state="sample"
            )
            
            auth_code = self._get_auth_code()
            access_token = self._get_access_token(auth_code)
            
            self.fyers = fyersModel.FyersModel(
                token=access_token,
                is_async=False,
                client_id=account['client_id'],
                log_path=""
            )
            
            # Save successful session
            self._save_session(access_token)
            print(f"Successfully logged in with account {account['client_id']}")
            return True
            
        except Exception as e:
            print(f"Login failed for account {account['client_id']}: {str(e)}")
            return False

    def login(self):
        """Try logging in with all accounts until one succeeds"""
        if self.fyers:  # Already logged in with valid session
            return self.fyers
            
        for account in self.accounts:
            if self._try_login_account(account):
                return self.fyers
                
        raise Exception("Failed to login with all accounts")
