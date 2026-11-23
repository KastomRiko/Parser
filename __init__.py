# Wordstat API Parser — Yandex Cloud
#
# Безопасный парсер Яндекс.Вордстат через официальный API
#
# Защита от банов:
# - Пауза 3-5 сек между запросами
# - Rate limiting (по умолчанию 10 запросов/мин)
# - User-Agent rotation
# - Exponential backoff при ошибках
# - Обработка 429 (Too Many Requests)
#
# Один HTTP-запрос = одна фраза
