"""
Экспорт результатов парсинга в CSV и JSON.
"""

import csv
import json
from pathlib import Path
from typing import List, Union
from dataclasses import asdict

from .api_parser import KeywordVolume


def to_csv(
    results: Union[List[KeywordVolume], List[dict]],
    output_path: str = "wordstat_results.csv",
):
    """Экспорт в CSV."""
    path = Path(output_path)
    if not results:
        print("Нет данных для экспорта")
        return

    fieldnames = list(asdict(results[0]).keys())

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in results:
            if isinstance(row, KeywordVolume):
                writer.writerow(asdict(row))
            else:
                writer.writerow(row)

    print(f"[+] Сохранено {len(results)} записей: {path.absolute()}")


def to_json(
    results: Union[List[KeywordVolume], List[dict]],
    output_path: str = "wordstat_results.json",
):
    """Экспорт в JSON."""
    path = Path(output_path)
    if not results:
        print("Нет данных для экспорта")
        return

    data = [asdict(r) if isinstance(r, KeywordVolume) else r for r in results]

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[+] Сохранено {len(results)} записей: {path.absolute()}")


def export_all(
    results: Union[List[WordstatResult], List[dict]],
    output_dir: str = ".",
    prefix: str = "wordstat_results",
):
    """Экспорт в CSV и JSON одновременно."""
    csv_path = f"{output_dir}/{prefix}.csv"
    json_path = f"{output_dir}/{prefix}.json"
    to_csv(results, csv_path)
    to_json(results, json_path)
