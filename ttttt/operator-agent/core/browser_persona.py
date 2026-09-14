import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

@dataclass
class BrowserPersona:
    persona_id: str
    tls_target: str
    user_agent: str
    sec_ch_ua: str
    sec_ch_ua_platform: str
    sec_ch_ua_mobile: str = "?0"
    accept_language: str = "en-US,en;q=0.9"
    viewport_width: int = 1920
    viewport_height: int = 1080
    min_jitter_ms: int = 350
    max_jitter_ms: int = 1800
    extra_headers: Dict[str, str] = field(default_factory=dict)

    def get_default_headers(self) -> Dict[str, str]:
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": self.accept_language,
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "sec-ch-ua": self.sec_ch_ua,
            "sec-ch-ua-mobile": self.sec_ch_ua_mobile,
            "sec-ch-ua-platform": f'"{self.sec_ch_ua_platform}"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1"
        }
        headers.update(self.extra_headers)
        return headers

    def get_api_headers(self, token: Optional[str] = None) -> Dict[str, str]:
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": self.accept_language,
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Content-Type": "application/json",
            "sec-ch-ua": self.sec_ch_ua,
            "sec-ch-ua-mobile": self.sec_ch_ua_mobile,
            "sec-ch-ua-platform": f'"{self.sec_ch_ua_platform}"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin"
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def apply_jitter(self, multiplier: float = 1.0):
        jitter_s = (random.randint(self.min_jitter_ms, self.max_jitter_ms) / 1000.0) * multiplier
        time.sleep(jitter_s)
        return jitter_s


class BrowserPersonaManager:
    PERSONA_CATALOG: List[BrowserPersona] = [
        BrowserPersona(
            persona_id="win11_chrome124",
            tls_target="chrome124",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            sec_ch_ua='"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            sec_ch_ua_platform="Windows",
            viewport_width=1920,
            viewport_height=1080,
            min_jitter_ms=400,
            max_jitter_ms=1600
        ),
        BrowserPersona(
            persona_id="win10_chrome120",
            tls_target="chrome120",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            sec_ch_ua='"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            sec_ch_ua_platform="Windows",
            viewport_width=1536,
            viewport_height=864,
            min_jitter_ms=350,
            max_jitter_ms=1400
        ),
        BrowserPersona(
            persona_id="macos_safari17",
            tls_target="safari17_0",
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
            sec_ch_ua="",
            sec_ch_ua_platform="macOS",
            viewport_width=1440,
            viewport_height=900,
            min_jitter_ms=500,
            max_jitter_ms=1900
        ),
        BrowserPersona(
            persona_id="win11_edge122",
            tls_target="edge101",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
            sec_ch_ua='"Chromium";v="122", "Not(A:Brand";v="24", "Microsoft Edge";v="122"',
            sec_ch_ua_platform="Windows",
            viewport_width=1920,
            viewport_height=1080,
            min_jitter_ms=450,
            max_jitter_ms=1750
        ),
        BrowserPersona(
            persona_id="macos_chrome124",
            tls_target="chrome124",
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            sec_ch_ua='"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            sec_ch_ua_platform="macOS",
            viewport_width=1680,
            viewport_height=1050,
            min_jitter_ms=380,
            max_jitter_ms=1550
        ),
        BrowserPersona(
            persona_id="win10_chrome119",
            tls_target="chrome119",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            sec_ch_ua='"Google Chrome";v="119", "Chromium";v="119", "Not?A_Brand";v="24"',
            sec_ch_ua_platform="Windows",
            viewport_width=1366,
            viewport_height=768,
            min_jitter_ms=420,
            max_jitter_ms=1650
        )
    ]

    @classmethod
    def get_persona_for_worker(cls, worker_id: str) -> BrowserPersona:
        hash_val = sum(ord(c) for c in str(worker_id))
        idx = hash_val % len(cls.PERSONA_CATALOG)
        return cls.PERSONA_CATALOG[idx]

    @classmethod
    def get_random_persona(cls) -> BrowserPersona:
        return random.choice(cls.PERSONA_CATALOG)
