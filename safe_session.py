"""
Безопасная сессия с защитой от банов.
"""

import random
import time
from typing import Optional

import requests


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
]


class SafeSession:
    """Сессия с защитой от банов."""

    def __init__(
        self,
        min_delay: float = 2.0,
        max_delay: float = 5.0,
        max_retries: int = 3,
        max_per_minute: int = 15,
    ):
        """
        Args:
            min_delay: Минимальная задержка между запросами (сек)
            max_delay: Максимальная задержка (сек)
            max_retries: Макс. повторов при ошибке
            max_per_minute: Макс запросов в минуту
        """
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.max_retries = max_retries
        self.max_per_minute = max_per_minute

        self._request_times: list = []
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.5,en;q=0.3",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Cache-Control": "max-age=0",
        })

    def _rate_limit(self):
        """Проверка лимита запросов в минуту."""
        now = time.time()
        # Убираем старые записи (> 60 сек)
        self._request_times = [t for t in self._request_times if now - t < 60]

        if len(self._request_times) >= self.max_per_minute:
            wait = 60 - (now - self._request_times[0]) + random.uniform(0.5, 2)
            if wait > 0:
                time.sleep(wait)
            self._request_times = []

    def _backoff_delay(self, attempt: int):
        """Exponential backoff + random jitter."""
        base = 3 * (2 ** attempt)  # 3, 6, 12 сек
        jitter = random.uniform(0, base * 0.5)
        delay = min(base + jitter, 60)  # максимум 60 сек
        return delay

    def get(self, url: str, **kwargs) -> Optional[requests.Response]:
        """Безопасный GET-запрос."""
        for attempt in range(self.max_retries):
            try:
                self._rate_limit()
                self._session.headers["User-Agent"] = random.choice(USER_AGENTS)
                resp = self._session.get(url, timeout=15, **kwargs)

                # Обработка 429 (Too Many Requests)
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", 60))
                    time.sleep(retry_after)
                    continue

                # Обработка 503 (Service Unavailable — исчерпана общая квота)
                if resp.status_code == 503:
                    delay = self._backoff_delay(attempt)
                    print(f"  [!] 503 Service Unavailable. Ждём {delay:.1f} сек...")
                    time.sleep(delay)
                    continue

                # Обработка 403 (Forbidden)
                if resp.status_code == 403:
                    delay = self._backoff_delay(attempt)
                    print(f"  [!] 403 Forbidden. Ждём {delay:.1f} сек...")
                    time.sleep(delay)
                    continue

                self._request_times.append(time.time())
                return resp

            except (requests.ConnectionError, requests.Timeout) as e:
                delay = self._backoff_delay(attempt)
                print(f"  [!] Ошибка #{attempt+1}: {e}. Ждём {delay:.1f} сек...")
                time.sleep(delay)

        return None

    def post(self, url: str, json: dict = None, **kwargs) -> Optional[requests.Response]:
        """Безопасный POST-запрос."""
        for attempt in range(self.max_retries):
            try:
                self._rate_limit()
                self._session.headers["User-Agent"] = random.choice(USER_AGENTS)
                resp = self._session.post(url, json=json, timeout=30, **kwargs)

                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", 60))
                    time.sleep(retry_after)
                    continue

                # Обработка 503 (Service Unavailable — исчерпана общая квота)
                if resp.status_code == 503:
                    delay = self._backoff_delay(attempt)
                    print(f"  [!] 503 Service Unavailable. Ждём {delay:.1f} сек...")
                    time.sleep(delay)
                    continue

                if resp.status_code == 403:
                    delay = self._backoff_delay(attempt)
                    print(f"  [!] 403 Forbidden. Ждём {delay:.1f} сек...")
                    time.sleep(delay)
                    continue

                self._request_times.append(time.time())
                return resp

            except (requests.ConnectionError, requests.Timeout) as e:
                delay = self._backoff_delay(attempt)
                print(f"  [!] Ошибка #{attempt+1}: {e}. Ждём {delay:.1f} сек...")
                time.sleep(delay)

        return None

    def close(self):
        """Закрыть сессию."""
        self._session.close()
