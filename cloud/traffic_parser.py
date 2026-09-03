from __future__ import annotations

import json
import re
import subprocess
import unicodedata
from dataclasses import asdict, dataclass, replace
from datetime import date
from pathlib import Path


DISTRICTS = ("神戸", "阪神", "東播", "西播", "但馬", "淡路", "高速")
CONTENT_PATTERN = r"速度|飲酒|交差点関連|自転車(?:違反)?"
ROW_PATTERN = re.compile(
    rf"^(?:(?P<day>\d{{1,2}})\s+[月火水木金土日]\s+)?"
    rf"(?P<district>{'|'.join(DISTRICTS)})\s+"
    rf"(?P<route>.+?)\s+(?P<content>{CONTENT_PATTERN})$"
)


@dataclass(frozen=True)
class TrafficPlan:
    date: str
    district: str
    route: str
    content: str


def normalize_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split())


def extract_pdf_text(pdf_path: Path) -> str:
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), "-"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def parse_traffic_plan(text: str, year: int, month: int) -> list[TrafficPlan]:
    groups: list[list[tuple[int | None, TrafficPlan]]] = []
    current_group: list[tuple[int | None, TrafficPlan]] = []

    for raw_line in text.splitlines():
        line = normalize_text(raw_line.replace("\f", ""))
        match = ROW_PATTERN.match(line)
        if not match:
            continue

        district = match.group("district")
        if district == "神戸" and current_group:
            groups.append(current_group)
            current_group = []

        current_group.append(
            (
                int(match.group("day")) if match.group("day") else None,
                TrafficPlan(
                    date="",
                    district=district,
                    route=normalize_text(match.group("route")),
                    content=normalize_text(match.group("content")),
                ),
            )
        )

        if district == "高速":
            groups.append(current_group)
            current_group = []

    if current_group:
        groups.append(current_group)

    plans: list[TrafficPlan] = []
    for group in groups:
        found_districts = tuple(plan.district for _, plan in group)
        days = {day for day, _ in group if day is not None}
        if found_districts != DISTRICTS or len(days) != 1:
            raise ValueError(
                f"Unexpected PDF table structure: districts={found_districts}, days={sorted(days)}"
            )

        day = days.pop()
        plan_date = date(year, month, day).isoformat()
        plans.extend(replace(plan, date=plan_date) for _, plan in group)

    if not plans:
        raise ValueError("No traffic plan rows found in PDF")

    return plans


def plans_to_json(plans: list[TrafficPlan], source_url: str, generated_at: str) -> str:
    payload = {
        "generatedAt": generated_at,
        "sourceUrl": source_url,
        "disclaimer": "公開情報は変更される場合があり、掲載場所以外でも取締りは行われます。",
        "plans": [asdict(plan) for plan in plans],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
