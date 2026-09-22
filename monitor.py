#!/usr/bin/env python3
import argparse
import html
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

DEFAULT_URL = "https://www.vhsit.berlin.de/VHSKURSE/BusinessPages/CourseDetail.aspx?id=785629"


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip().lower()


def control_text(tag) -> str:
    parts = []
    if tag.name == "button":
        parts.append(tag.get_text(" ", strip=True))
    for attr in ("value", "title", "alt", "aria-label", "name", "id"):
        v = tag.get(attr)
        if isinstance(v, str):
            parts.append(v)
    return norm(" ".join(parts))


def find_booking_control(soup: BeautifulSoup):
    # We intentionally inspect only form controls. The permanent site header
    # contains "Warenkorb (0)" and must not count as availability.
    controls = soup.find_all(["input", "button"])
    for tag in controls:
        text = control_text(tag)
        if "warenkorb" in text:
            return tag, text
    return None, ""


def extract_dates(soup: BeautifulSoup):
    text = soup.get_text(" ", strip=True)
    # Typical VHS rendering: "Mi, 30.09.2026, 13:00 - 17:20"
    pattern = re.compile(
        r"(?:Mo|Di|Mi|Do|Fr|Sa|So),\s*\d{2}\.\d{2}\.\d{4},\s*"
        r"\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}",
        re.IGNORECASE,
    )
    return list(dict.fromkeys(pattern.findall(text)))


def write_output(path: str | None, **values):
    if not path:
        return
    with Path(path).open("a", encoding="utf-8") as f:
        for key, value in values.items():
            value = str(value).replace("\n", " ").replace("\r", " ")
            f.write(f"{key}={value}\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--github-output")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; VHSAvailabilityWatcher/1.0; "
            "+https://github.com/)"
        ),
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.5",
    }
    response = requests.get(args.url, headers=headers, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    page_text = norm(soup.get_text(" ", strip=True))
    if "kursnummer" not in page_text and "sprachtest" not in page_text:
        raise RuntimeError("Die Antwort sieht nicht wie eine VHS-Kursdetailseite aus.")

    control, marker = find_booking_control(soup)
    available = control is not None
    dates = extract_dates(soup)
    details = "; ".join(dates) if dates else "Termintext nicht automatisch erkannt"

    print(f"URL: {args.url}")
    print(f"Buchbar: {'JA' if available else 'nein'}")
    print(f"Termin(e): {details}")
    if available:
        print(f"Gefundener Buchungsmarker: {html.escape(marker)}")

    if args.debug:
        print("\nForm controls mit relevanten Begriffen:")
        for tag in soup.find_all(["input", "button"]):
            t = control_text(tag)
            if any(word in t for word in ("warenkorb", "buch", "anmeld")):
                print(f"- <{tag.name}> {t}")

    write_output(
        args.github_output,
        available="true" if available else "false",
        details=details,
        marker=marker,
    )


if __name__ == "__main__":
    main()
