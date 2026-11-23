#!/usr/bin/env python3
"""
Wordstat API Parser — парсер частотности через Yandex Cloud API.

Один HTTP-запрос = одна фраза.
Пауза 3–5 сек между запросами.
Защита от банов: rate limiting, exponential backoff, 429/503 handling.
num_phrases — похожие фразы в ответе (1–2000, по умолчанию 500).

Установка ключей:
  export YANDEX_API_KEY="AQVN... (API-ключ сервисного аккаунта, не OAuth!)"
  export YANDEX_FOLDER_ID="b1g... (ID каталога Yandex Cloud)"

Или создай .env файл и загрузи: pip install python-dotenv
"""

import os
import sys
from pathlib import Path

# ─── Загрузка .env (если есть) ───
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv не установлен — используем только os.environ

from .api_parser import WordstatAPI, KeywordVolume, YANDEX_API_KEY, FOLDER_ID
from .output import export_all, to_csv, to_json


def check_env():
    """Проверить, заданы ли переменные окружения."""
    missing = []
    if not YANDEX_API_KEY:
        missing.append("YANDEX_API_KEY")
    if not FOLDER_ID:
        missing.append("YANDEX_FOLDER_ID")

    if missing:
        print("=" * 60)
        print("ОШИБКА: Не заданы переменные окружения:")
        print()
        for var in missing:
            print(f"  - {var}")
        print()
        print("Как исправить:")
        print()
        print("  Вариант 1 — через .env-файл:")
        print("    1. Создай файл .env в папке проекта")
        print("    2. Напиши:")
        print("       YANDEX_API_KEY=AQVN... (API-ключ сервисного аккаунта)")
        print("       YANDEX_FOLDER_ID=твой_folder_id")
        print("    3. Установи dotenv: pip install python-dotenv")
        print()
        print("  Вариант 2 — через терминал:")
        print("    set YANDEX_API_KEY=AQVN...")
        print("    set YANDEX_FOLDER_ID=твой_folder_id")
        print()
        print("Где взять:")
        print("  API-ключ:  cloud.yandex.ru → Сервисные аккаунты → Создать → API-ключ")
        print("  Folder ID: cloud.yandex.ru → Настройки → ID папки")
        print()
        print("⚠  НИКОГДА не коммить .env в git!")
        print("=" * 60)
        sys.exit(1)


def parse_args():
    import argparse
    parser = argparse.ArgumentParser(
        description="Яндекс.Вордстат API — подбор частотных ключевых фраз",
    )
    parser.add_argument(
        "--file", "-f",
        default=Path(__file__).parent / "queries.txt",
        help="Файл с запросами (по умолчанию: queries.txt)",
    )
    parser.add_argument(
        "--format",
        choices=["csv", "json", "all"],
        default="all",
        help="Формат вывода (по умолчанию: all)",
    )
    parser.add_argument(
        "--num-phrases",
        type=int,
        default=500,
        help="Макс похожих фраз на один запрос (1–2000, по умолчанию: 500)",
    )
    parser.add_argument(
        "--min-delay",
        type=float,
        default=3.0,
        help="Мин пауза между запросами (сек, по умолчанию: 3.0)",
    )
    parser.add_argument(
        "--max-delay",
        type=float,
        default=5.0,
        help="Макс пауза между запросами (сек, по умолчанию: 5.0)",
    )
    parser.add_argument(
        "--min-volume",
        type=int,
        default=0,
        help="Фильтр: минимальная частотность (по умолчанию: 0 = все)",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Директория для сохранения результатов",
    )
    return parser.parse_args()


def load_queries(filepath: str) -> list:
    """Загрузить список запросов из файла."""
    with open(filepath, "r", encoding="utf-8") as f:
        return [
            line.strip()
            for line in f
            if line.strip() and not line.startswith("#")
        ]


def format_results(results: list, min_volume: int = 0) -> list:
    """Отфильтровать и отсортировать результаты."""
    filtered = [r for r in results if getattr(r, "exact_volume", 0) >= min_volume]
    filtered.sort(key=lambda x: getattr(x, "exact_volume", 0), reverse=True)
    return filtered


def print_results(results: list):
    """Вывести результаты в консоль."""
    print("\n" + "=" * 80)
    print(f"{'Фраза':<40} {'Точное []':>10} {'Расшир. []':>10}")
    print("=" * 80)
    for r in results:
        phrase = getattr(r, "phrase", "?")[:40]
        exact = getattr(r, "exact_volume", 0)
        community = getattr(r, "community_volume", 0)
        print(f"{phrase:<40} {exact:>10,} {community:>10,}")
    print("=" * 80)
    print(f"Всего записей: {len(results)}")
    total_exact = sum(getattr(r, "exact_volume", 0) for r in results)
    print(f"Общий объём:   {total_exact:>10,}")


def main():
    args = parse_args()

    # Проверка переменных окружения
    check_env()

    # Загрузка запросов
    queries = load_queries(args.file)
    print(f"[+] Загружено {len(queries)} запросов из {args.file}")
    print(f"[+] num_phrases: {args.num_phrases}")
    print(f"[+] Пауза: {args.min_delay}–{args.max_delay} сек")
    print()

    # Инициализация API
    api = WordstatAPI(
        min_delay=args.min_delay,
        max_delay=args.max_delay,
    )

    # Запрос
    try:
        print("[+] Начало парсинга...")
        print()
        results = api.search_many(queries, num_phrases=args.num_phrases)
    finally:
        api.close()

    print(f"\n[+] Получено {len(results)} записей")

    # Фильтрация и сортировка
    results = format_results(results, args.min_volume)

    # Вывод
    print_results(results)

    # Экспорт
    if args.format == "csv":
        to_csv(results, args.output_dir)
    elif args.format == "json":
        to_json(results, args.output_dir)
    elif args.format == "all":
        export_all(results, args.output_dir)

    print("\n[✓] Готово!")


if __name__ == "__main__":
    main()
