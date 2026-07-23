import os
import pickle
import threading
import logging
from datetime import datetime
from curl_cffi import requests
from sqlalchemy.orm import Session
from app.models import SessionLocal, ScraperAccount
from app.core.browser_trust import BrowserTrustService

class SessionManager:
    """
    Centralized Session Manager for maintaining authenticated curl_cffi sessions.
    Handles proactive refreshing, persistence, and synchronization (preventing thundering herds).
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if not cls._instance:
                cls._instance = super(SessionManager, cls).__new__(cls)
                cls._instance._init()
            return cls._instance

    def _init(self):
        self.sessions = {} # username -> curl_cffi requests.Session
        self.account_locks = {} # username -> threading.Lock
        self.sessions_dir = os.path.join(os.path.dirname(__file__), "..", "..", "sessions")
        os.makedirs(self.sessions_dir, exist_ok=True)
        
    def _get_account_lock(self, username: str):
        with self._lock:
            if username not in self.account_locks:
                self.account_locks[username] = threading.Lock()
            return self.account_locks[username]

    def _update_account_status(self, username: str, status: str, success: bool = True):
        try:
            with SessionLocal() as db:
                account = db.query(ScraperAccount).filter(ScraperAccount.username == username).first()
                if account:
                    account.status = status
                    if success:
                        account.last_login = datetime.utcnow()
                        account.consecutive_failures = 0
                    else:
                        account.consecutive_failures += 1
                        
                        # Optionally mark as inactive if too many failures
                        if account.consecutive_failures >= 5:
                            account.is_active = False
                            account.status = "Blocked due to 5 consecutive failures"
                            
                    db.commit()
        except Exception as e:
            logging.error(f"[SessionManager] Failed to update DB status for {username}: {e}")

    def get_session(self, username: str, password: str, sitekey: str, captcha_api_key: str, force_refresh: bool = False, proxy_string: str = None) -> requests.Session:
        """
        Retrieves a valid curl_cffi session for the given account.
        If force_refresh is True, or no valid session exists, it triggers the BrowserTrustService.
        """
        acc_lock = self._get_account_lock(username)
        
        with acc_lock:
            # 1. Return from memory if it exists and we're not forcing a refresh
            if not force_refresh and username in self.sessions:
                return self.sessions[username]
                
            # 2. Try loading from disk if we're not forcing a refresh
            cookie_file = os.path.join(self.sessions_dir, f"{username}.pkl")
            if not force_refresh and os.path.exists(cookie_file):
                try:
                    with open(cookie_file, 'rb') as f:
                        cookies = pickle.load(f)
                    
                    session = self._create_curl_cffi_session(cookies)
                    self.sessions[username] = session
                    logging.info(f"[SessionManager] Loaded valid session for {username} from disk.")
                    self._update_account_status(username, "Active (Loaded from disk)")
                    return session
                except Exception as e:
                    logging.warning(f"[SessionManager] Failed to load disk session for {username}: {e}")
                    
            # 3. If we reach here, we must do a full Browser Authentication
            self._update_account_status(username, "Authenticating (Browser)", success=False) # Not success yet
            
            trust_svc = BrowserTrustService(captcha_api_key=captcha_api_key, proxy_string=proxy_string)
            cookie_jar = trust_svc.authenticate(username, password, sitekey)
            
            if cookie_jar:
                # Save to disk
                try:
                    with open(cookie_file, 'wb') as f:
                        pickle.dump(cookie_jar, f)
                except Exception as e:
                    logging.error(f"[SessionManager] Failed to save session to disk for {username}: {e}")
                
                session = self._create_curl_cffi_session(cookie_jar)
                self.sessions[username] = session
                self._update_account_status(username, "Active", success=True)
                logging.info(f"[SessionManager] Successfully authenticated and established new session for {username}.")
                return session
            else:
                self._update_account_status(username, "Authentication Failed", success=False)
                logging.error(f"[SessionManager] Failed to acquire new session for {username}.")
                return None

    def invalidate_session(self, username: str):
        """
        Removes the session from memory and disk so the next get_session() triggers a refresh.
        """
        logging.warning(f"[SessionManager] Invalidating session for {username}...")
        with self._get_account_lock(username):
            if username in self.sessions:
                del self.sessions[username]
                
            cookie_file = os.path.join(self.sessions_dir, f"{username}.pkl")
            if os.path.exists(cookie_file):
                try:
                    os.remove(cookie_file)
                except Exception:
                    pass
                    
            self._update_account_status(username, "Invalidated (Requires Re-Auth)", success=False)

    def _create_curl_cffi_session(self, cookies: dict) -> requests.Session:
        """
        Creates a lightweight HTTP client (curl_cffi) spoofing Chrome 120, loaded with the authenticated cookies.
        """
        session = requests.Session(impersonate="chrome120")
        target_domain = os.getenv('BOOKING_PORTAL_URL', "https://pk-gr-services.gvcworld.eu")
        
        # Add basic standard headers just in case
        session.headers.update({
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Origin": target_domain,
            "Referer": f"{target_domain}/",
        })
        
        # Inject the cookies
        for name, value in cookies.items():
            session.cookies.set(name, value, domain=target_domain.split('//')[-1])
            
        return session
