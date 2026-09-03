from __future__ import annotations

import argparse
import re
import tempfile
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from cloud.traffic_parser import extract_pdf_text, parse_traffic_plan, plans_to_json


INDEX_URL = "https://www.police.pref.hyogo.lg.jp/traffic/violation/jyouho/index.htm"
PDF_LINK_PATTERN = re.compile(r'href=["\'](?P<href>[^"\']+\.pdf)["\']', re.IGNORECASE)
PDF_DATE_PATTERN = re.compile(r"(?P<year>20\d{2})(?P<month>\d{2})(?P<day>\d{2})\.pdf$")
USER_AGENT = "HyogoTrafficAlert/1.0 (public-information updater)"


def download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def find_pdf_urls(index_html: str) -> list[str]:
    return list(
        dict.fromkeys(
            urllib.parse.urljoin(INDEX_URL, match.group("href"))
            for match in PDF_LINK_PATTERN.finditer(index_html)
        )
    )


def date_parts_from_url(url: str) -> tuple[int, int]:
    match = PDF_DATE_PATTERN.search(url)
    if not match:
        raise ValueError(f"PDF URL does not contain a publication date: {url}")
    return int(match.group("year")), int(match.group("month"))


def parse_pdf_file(pdf_path: Path, source_url: str):
    year, month = date_parts_from_url(source_url)
    return parse_traffic_plan(extract_pdf_text(pdf_path), year, month)


def generate_from_web(output_path: Path) -> None:
    index_html = download(INDEX_URL).decode("utf-8")
    pdf_urls = find_pdf_urls(index_html)
    if not pdf_urls:
        raise RuntimeError("No traffic-plan PDF links found on official page")

    all_plans = []
    with tempfile.TemporaryDirectory() as temp_directory:
        for position, pdf_url in enumerate(pdf_urls):
            pdf_path = Path(temp_directory) / f"plan-{position}.pdf"
            pdf_path.write_bytes(download(pdf_url))
            all_plans.extend(parse_pdf_file(pdf_path, pdf_url))

    unique_plans = list(dict.fromkeys(all_plans))
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        plans_to_json(unique_plans, INDEX_URL, generated_at),
        encoding="utf-8",
    )


def generate_from_local_pdf(pdf_path: Path, source_url: str, output_path: Path) -> None:
    plans = parse_pdf_file(pdf_path, source_url)
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(plans_to_json(plans, source_url, generated_at), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate traffic-plan JSON from Hyogo Police PDFs")
    parser.add_argument("--output", type=Path, default=Path("data/traffic-data.json"))
    parser.add_argument("--pdf", type=Path)
    parser.add_argument("--source-url")
    args = parser.parse_args()

    if args.pdf:
        if not args.source_url:
            parser.error("--source-url is required with --pdf")
        generate_from_local_pdf(args.pdf, args.source_url, args.output)
    else:
        generate_from_web(args.output)


if __name__ == "__main__":
    main()
