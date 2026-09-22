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
        value = tag.get(attr)
        if isinstance(value, str):
            parts.append(value)

    return norm(" ".join(parts))


def find_booking_control(soup: BeautifulSoup):
    # Nur echte Buttons/Formularfelder prüfen.
    # "Warenkorb (0)" oben auf der Seite zählt NICHT.
    for tag in soup.find_all(["input", "button"]):
        text = control_text(tag)

        if "warenkorb" in text:
            return tag, text

    return None, ""


def extract_dates(soup: BeautifulSoup):
    text = soup.get_text(" ", strip=True)

    pattern = re.compile(
        r"(?:Mo|Di|Mi|Do|Fr|Sa|So),\s*\d{2}\.\d{2}\.\d{4},\s*"
        r"\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}",
        re.IGNORECASE,
    )

    return list(dict.fromkeys(pattern.findall(text)))


def write_output(path: str | None, **values):
    if not path:
        return

    with Path(path).open("a", encoding="utf-8") as file:
        for key, value in values.items():
            value = str(value).replace("\n", " ").replace("\r", " ")
            file.write(f"{key}={value}\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--github-output")
    parser.add_argument("--debug", action="store_true")

    args = parser.parse_args()

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/140.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.5",
        "Cache-Control": "no-cache",
    }

    print(f"Pruefe: {args.url}")

    try:
        response = requests.get(
            args.url,
            headers=headers,
            timeout=30,
            allow_redirects=True,
        )

        print(f"HTTP Status: {response.status_code}")

        response.raise_for_status()

    except requests.RequestException as exc:
        print(f"VHS-Seite momentan nicht erreichbar: {exc}")
        print("Kein Alarm. Naechster Versuch beim naechsten Lauf.")

        write_output(
            args.github_output,
            available="false",
            details="VHS-Seite momentan nicht erreichbar",
            marker="",
        )
        return

    soup = BeautifulSoup(response.text, "html.parser")
    page_text = norm(soup.get_text(" ", strip=True))

    # VHS liefert gelegentlich eine andere/fehlerhafte Seite.
    # Das soll den GitHub-Workflow NICHT rot machen.
    if "kursnummer" not in page_text and "sprachtest" not in page_text:
        print("Keine normale VHS-Kursdetailseite erhalten.")
        print("Kein Alarm. Naechster Versuch beim naechsten Lauf.")

        write_output(
            args.github_output,
            available="false",
            details="VHS-Kursdetailseite momentan nicht verfuegbar",
            marker="",
        )
        return

    control, marker = find_booking_control(soup)

    available = control is not None

    dates = extract_dates(soup)

    if dates:
        details = "; ".join(dates)
    else:
        details = "Termintext nicht automatisch erkannt"

    print(f"Buchbar: {'JA' if available else 'nein'}")
    print(f"Termin(e): {details}")

    if available:
        print("!!! BUCHUNGSBUTTON GEFUNDEN !!!")
        print(f"Marker: {html.escape(marker)}")

    if args.debug:
        print("\nRelevante Formularfelder:")

        for tag in soup.find_all(["input", "button"]):
            text = control_text(tag)

            if any(
                word in text
                for word in ("warenkorb", "buch", "anmeld")
            ):
                print(f"- <{tag.name}> {text}")

    write_output(
        args.github_output,
        available="true" if available else "false",
        details=details,
        marker=marker,
    )


if __name__ == "__main__":
    main()
