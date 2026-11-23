"""
API-клиент для Яндекс.Вордстат через Yandex Cloud API.

Эндпоинт: searchapi.api.cloud.yandex.net/v2/wordstat/topRequests
Документация: https://cloud.yandex.ru/docs/wordstat/api-ref

Один запрос API = одна фраза.
num_phrases — количество похожих фраз в ответе (1–2000).
"""

import os
import time
import random
from dataclasses import dataclass, field
from typing import List

from .safe_session import SafeSession

# ─── Конфигурация (заглушки — читается из окружения) ───

YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")
FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")


@dataclass
class KeywordVolume:
    """Объём показов для одной ключевой фразы."""
    phrase: str
    exact_volume: int = 0        # точное совпадение [фраза]
    community_volume: int = 0    # фраза (расширенная)
    flags: dict = field(default_factory=dict)


class WordstatAPI:
    """Клиент для Yandex Cloud Wordstat API.

    Один HTTP-запрос = одна входная фраза.
    Авторизация: API-ключ сервисного аккаунта (начинается с AQVN...).
    """

    API_HOST = "searchapi.api.cloud.yandex.net"
    API_PATH = "/v2/wordstat/topRequests"

    def __init__(self, min_delay: float = 3.0, max_delay: float = 5.0, max_per_minute: int = 10):
        """
        Args:
            min_delay: Минимальная задержка между запросами (сек)
            max_delay: Максимальная задержка между запросами (сек)
            max_per_minute: Макс запросов в минуту
        """
        if not YANDEX_API_KEY:
            raise ValueError(
                "Переменная окружения YANDEX_API_KEY не задана. "
                "Это API-ключ сервисного аккаунта (начинается с AQVN...). "
                "Создай .env-файл или установи: export YANDEX_API_KEY='твой_ключ'"
            )
        if not FOLDER_ID:
            raise ValueError(
                "Переменная окружения YANDEX_FOLDER_ID не задана. "
                "Создай .env-файл или установи: export YANDEX_FOLDER_ID='твой_folder_id'"
            )

        self.min_delay = min_delay
        self.max_delay = max_delay
        self.max_per_minute = max_per_minute
        self.api_key = YANDEX_API_KEY

        self.safe_session = SafeSession(
            min_delay=min_delay,
            max_delay=max_delay,
            max_per_minute=max_per_minute,
        )

    def _build_headers(self) -> dict:
        """Заголовки запроса с API-ключом сервисного аккаунта."""
        return {
            "Authorization": f"Api-Key {self.api_key}",
            "Content-Type": "application/json",
        }

    def search(self, phrase: str, num_phrases: int = 500) -> List[KeywordVolume]:
        """
        Запросить частотность для ОДНОЙ фразы.

        Args:
            phrase: Одна ключевая фраза
            num_phrases: Макс похожих фраз в ответе (1–2000, по умолчанию: 500)

        Returns:
            Список KeywordVolume для всех найденных вариантов
        """
        payload = {
            "folderId": FOLDER_ID,
            "phrase": phrase,
            "num_phrases": num_phrases,
        }

        url = f"https://{self.API_HOST}{self.API_PATH}"
        resp = self.safe_session.post(
            url,
            json=payload,
            headers=self._build_headers(),
        )

        # ─── Обработка 429 (Too Many Requests) ───
        if resp and resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 0))
            if retry_after > 0:
                print(f"    [!] 429: ожидаем {retry_after} сек (Retry-After)")
                time.sleep(retry_after)
            else:
                wait = random.uniform(30, 60)
                print(f"    [!] 429: нет Retry-After, ждём {wait:.0f} сек...")
                time.sleep(wait)
            # Повторяем запрос после ожидания
            resp = self.safe_session.post(
                url,
                json=payload,
                headers=self._build_headers(),
            )

        if resp is None or resp.status_code != 200:
            status = resp.status_code if resp else "no response"
            body = resp.text[:500] if resp else ""
            print(f"    [!] Ошибка HTTP {status}: {body}")
            return []

        data = resp.json()
        return self._parse_response(data)

    @staticmethod
    def _safe_int(value, default: int = 0) -> int:
        """Конвертация строки/числа в int (int64 сериализуется как строка)."""
        if value is None:
            return default
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return default
        return default

    def _parse_response(self, data: dict) -> List[KeywordVolume]:
        """
        Распарсить JSON-ответ Wordstat API v2.

        Структура ответа:
        {
          "results": [
            { "phrase": "...", "count": 1234 },
            ...
          ],
          "associations": [ ... ]  // похожие запросы (не используем)
        }
        """
        results = []

        # Основные результаты по запрошенной фразе
        for item in data.get("results", []):
            results.append(KeywordVolume(
                phrase=item.get("phrase", ""),
                exact_volume=self._safe_int(item.get("count", 0)),
                community_volume=0,
            ))

        # Сопутствующие запросы (из ассоциаций, если есть)
        for item in data.get("associations", []):
            results.append(KeywordVolume(
                phrase=item.get("phrase", ""),
                exact_volume=self._safe_int(item.get("count", 0)),
                community_volume=0,
            ))

        return results

    def search_many(self, phrases: List[str], num_phrases: int = 500) -> List[KeywordVolume]:
        """
        Запросить частотность для списка фраз.

        Один запрос API = одна фраза.
        Пауза 3–5 сек между запросами с рандомным джиттером.

        Args:
            phrases: Список ключевых фраз
            num_phrases: Макс результатов на фразу (1–2000, по умолчанию: 500)

        Returns:
            Все результаты в одной плоской коллекции
        """
        all_results: List[KeywordVolume] = []

        for i, phrase in enumerate(phrases):
            print(f"  [{i+1}/{len(phrases)}] {phrase}")

            # ─── Пауза перед запросом (кроме первого) ───
            if i > 0:
                delay = random.uniform(self.min_delay, self.max_delay)
                print(f"    ... пауза {delay:.1f} сек")
                time.sleep(delay)

            try:
                results = self.search(phrase, num_phrases=num_phrases)
                all_results.extend(results)
                count = len(results)
                if results:
                    top = max(results, key=lambda r: r.exact_volume)
                    print(f"    → {count} вариантов. Топ: [{top.exact_volume:,}] «{top.phrase}»")
                else:
                    print(f"    → нет данных")
            except Exception as e:
                print(f"    → ошибка: {e}")

        return all_results

    def close(self):
        """Закрыть сессию."""
        self.safe_session.close()
