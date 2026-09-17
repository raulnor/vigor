"""Scrape race-tagged activities from Strava web interface."""
import http.cookiejar
import json
import re
import sys
from pathlib import Path

import requests


def scrape_races_http(cookies_str):
    """
    Scrape race activities from Strava using HTTP requests with session cookies.
    Returns a set of activity IDs that are tagged as races.
    """
    race_ids = set()

    # Parse cookies from curl format using http.cookiejar
    cookie_jar = http.cookiejar.CookieJar()
    for cookie_str in cookies_str.split('; '):
        if '=' not in cookie_str:
            continue
        key, value = cookie_str.split('=', 1)
        cookie = http.cookiejar.Cookie(
            version=0,
            name=key,
            value=value,
            port=None,
            port_specified=False,
            domain='.strava.com',
            domain_specified=True,
            domain_initial_dot=True,
            path='/',
            path_specified=True,
            secure=True,
            expires=None,
            discard=True,
            comment=None,
            comment_url=None,
            rest={},
            rfc2109=False
        )
        cookie_jar.set_cookie(cookie)

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.strava.com/athlete/training',
    }

    session = requests.Session()
    session.headers.update(headers)
    session.cookies = cookie_jar

    print("Fetching race activities from Strava...", file=sys.stderr)

    # Get CSRF token from session cookies
    csrf_token = ''
    for cookie in cookie_jar:
        if cookie.name == '_csrf_token':
            csrf_token = cookie.value
            break

    # Use the training activities API with tags=1 for races
    page = 1

    while True:
        url = f"https://www.strava.com/athlete/training_activities?keywords=&sport_type=&tags=1&commute=&private_activities=&trainer=&gear=&new_activity_only=false&order=&page={page}"

        headers_with_ajax = {
            **headers,
            'Accept': 'text/javascript, application/javascript',
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRF-Token': csrf_token,
        }

        try:
            response = session.get(url, headers=headers_with_ajax)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"Error fetching page {page}: {e}", file=sys.stderr)
            break

        try:
            data = response.json()
        except:
            # Fall back to HTML parsing if JSON fails
            html = response.text
            matches = re.findall(r'/activities/(\d+)', html)
            if not matches:
                break
            new_ids = set(matches) - race_ids
            race_ids.update(new_ids)
            print(f"Page {page}: Found {len(new_ids)} new races (total: {len(race_ids)})", file=sys.stderr)
            if len(new_ids) < 5:
                break
            page += 1
            continue

        # Extract activity IDs from JSON response
        models = data.get('models', [])

        if not models:
            # No more activities
            break

        # Extract IDs from the models
        new_ids = set()
        for model in models:
            activity_id = str(model.get('id', ''))
            if activity_id:
                new_ids.add(activity_id)

        if not new_ids:
            break

        race_ids.update(new_ids)
        print(f"Page {page}: Found {len(new_ids)} races (total: {len(race_ids)})", file=sys.stderr)

        page += 1

        # Safety limit
        if page > 100:
            print("Reached page limit (100 pages)", file=sys.stderr)
            break

    print(f"\nTotal race activities found: {len(race_ids)}", file=sys.stderr)
    return race_ids


def save_races(race_ids, output_path):
    """Save race activity IDs to a file."""
    output_path = Path(output_path)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("# Race activity IDs scraped from Strava\n")
        f.write("# One activity ID per line\n")
        for race_id in sorted(race_ids):
            f.write(f"{race_id}\n")
    print(f"Saved {len(race_ids)} race IDs to {output_path}", file=sys.stderr)


def main():
    """Main entry point for scraping races."""
    from vigor.paths import data_dir

    print("Strava Race Scraper", file=sys.stderr)
    print("=" * 50, file=sys.stderr)

    # Check if cookies file exists
    cookies_file = data_dir() / "strava_cookies.txt"

    if not cookies_file.exists():
        print("\nNo Strava cookies found. You need to provide your session cookies.", file=sys.stderr)
        print(f"\nCreate a file at: {cookies_file}", file=sys.stderr)
        print("\nWith your Strava cookies (from browser DevTools > Network > any request > Cookie header)", file=sys.stderr)
        print("\nExample format:", file=sys.stderr)
        print("_strava4_session=abc123; strava_remember_id=123456; ...", file=sys.stderr)
        return 1

    # Read cookies from file
    with open(cookies_file, 'r', encoding='utf-8') as f:
        cookies_str = f.read().strip()

    print(f"\nUsing cookies from: {cookies_file}", file=sys.stderr)

    race_ids = scrape_races_http(cookies_str)

    if race_ids:
        output_path = data_dir() / "races.txt"
        save_races(race_ids, output_path)
        print(f"\nSuccess! Race IDs saved to: {output_path}", file=sys.stderr)
        print(f"vigor will now use this file to identify races.", file=sys.stderr)
    else:
        print("\nNo race activities found or scraping failed.", file=sys.stderr)
        print("Check if your cookies are still valid.", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
