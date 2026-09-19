"""Scrape race-tagged activities from Strava web interface and update activities.csv."""
import csv
import http.cookiejar
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from vigor.db import parse_date

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


def scrape_all_activities(session, csrf_token, max_pages=None, since_date=None):
    """
    Scrape all activities from Strava training page.
    Returns a list of activity dicts with their metadata.

    Args:
        session: requests session with cookies
        csrf_token: CSRF token for authenticated requests
        max_pages: Maximum number of pages to fetch (None = unlimited)
        since_date: Only fetch activities after this date (datetime object)
    """
    activities = []
    page = 1

    print("Fetching all activities from Strava...", file=sys.stderr)

    while True:
        if max_pages and page > max_pages:
            print(f"Reached page limit ({max_pages} pages)", file=sys.stderr)
            break

        # Fetch all activities (no tag filter)
        url = f"https://www.strava.com/athlete/training_activities?keywords=&sport_type=&commute=&private_activities=&trainer=&gear=&new_activity_only=false&order=&page={page}"

        headers_with_ajax = {
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
            models = data.get('models', [])

            if not models:
                print(f"No more activities on page {page}", file=sys.stderr)
                break

            # Check if we should stop based on date
            should_stop = False
            for model in models:
                # Extract activity data from the model
                activity = {
                    'id': str(model.get('id', '')),
                    'name': model.get('name', ''),
                    'type': model.get('sport_type', model.get('display_type', '')),
                    'start_date': model.get('start_time', ''),
                    'start_date_local_raw': model.get('start_date_local_raw', 0),
                    'distance_raw': model.get('distance_raw', 0),
                    'moving_time_raw': model.get('moving_time_raw', 0),
                    'elevation_gain_raw': model.get('elevation_gain_raw', 0),
                    'is_race': model.get('tags', {}).get('1', False),  # tag "1" = race
                }

                # Check if this activity is older than since_date
                if since_date and activity['start_date_local_raw']:
                    activity_date = datetime.fromtimestamp(activity['start_date_local_raw'])
                    if activity_date < since_date:
                        should_stop = True
                        print(f"Reached activities older than {since_date.strftime('%Y-%m-%d')}, stopping", file=sys.stderr)
                        break

                activities.append(activity)

            print(f"Page {page}: Found {len(models)} activities (total: {len(activities)})", file=sys.stderr)

            if should_stop:
                break

            page += 1

        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error parsing page {page}: {e}", file=sys.stderr)
            break

    print(f"\nTotal activities found: {len(activities)}", file=sys.stderr)
    return activities


def get_latest_activity_from_csv(csv_path):
    """
    Read the activities.csv and return the most recent activity date.
    Returns datetime object or None if CSV doesn't exist or is empty.
    """
    if not csv_path.exists():
        return None

    try:
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            latest_date = None

            for row in reader:
                date = parse_date(row.get('Activity Date', '').strip())
                if date:
                    if latest_date is None or date > latest_date:
                        latest_date = date
            return latest_date
    except Exception as e:
        print(f"Error reading CSV: {e}", file=sys.stderr)
        return None


def format_strava_date(timestamp):
    """Convert Strava timestamp to CSV format."""
    if not timestamp:
        return ""
    try:
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime('%b %d, %Y, %I:%M:%S %p')
    except (ValueError, OSError):
        return ""


def update_activities_csv(csv_path, new_activities, race_ids):
    """
    Update activities.csv with new activities and add/update Race column.

    Args:
        csv_path: Path to activities.csv
        new_activities: List of activity dicts from scraper
        race_ids: Set of activity IDs that are races

    Returns:
        Number of new activities added
    """
    csv_path = Path(csv_path)

    # Read existing CSV if it exists
    existing_rows = []
    existing_ids = set()
    fieldnames = None

    if csv_path.exists():
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            fieldnames = list(reader.fieldnames) if reader.fieldnames else None
            for row in reader:
                existing_rows.append(row)
                existing_ids.add(row.get('Activity ID', '').strip())

    # Define expected fieldnames based on Strava export format
    if fieldnames is None:
        fieldnames = [
            'Activity ID', 'Activity Date', 'Activity Name', 'Activity Type',
            'Distance', 'Moving Time', 'Elevation Gain', 'Race'
        ]
    elif 'Race' not in fieldnames:
        # Add Race column if it doesn't exist
        fieldnames.append('Race')

    # Update race flag for existing rows
    for row in existing_rows:
        activity_id = row.get('Activity ID', '').strip()
        row['Race'] = '1' if activity_id in race_ids else row.get('Race', '0')

    # Add new activities
    new_count = 0
    for activity in new_activities:
        activity_id = str(activity.get('id', ''))
        if activity_id and activity_id not in existing_ids:
            # Convert activity data to CSV row format
            row = {field: '' for field in fieldnames}
            row['Activity ID'] = activity_id
            row['Activity Name'] = activity.get('name', '')
            row['Activity Type'] = activity.get('type', '')
            row['Activity Date'] = format_strava_date(activity.get('start_date_local_raw'))
            row['Distance'] = str(activity.get('distance_raw', ''))
            row['Moving Time'] = str(int(activity.get('moving_time_raw', 0)))
            row['Elevation Gain'] = str(activity.get('elevation_gain_raw', ''))
            row['Race'] = '1' if (activity_id in race_ids or activity.get('is_race')) else '0'

            existing_rows.append(row)
            existing_ids.add(activity_id)
            new_count += 1

    # Sort by date (most recent first)
    def get_sort_date(row):
        date_str = row.get('Activity Date', '')
        try:
            if 'T' in date_str or ' ' in date_str:
                return datetime.fromisoformat(date_str.replace('Z', '+00:00').replace(' ', 'T'))
            else:
                return datetime.strptime(date_str, '%b %d, %Y, %I:%M:%S %p')
        except (ValueError, AttributeError):
            return datetime.min

    existing_rows.sort(key=get_sort_date, reverse=True)

    # Write updated CSV
    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(existing_rows)

    print(f"\nUpdated {csv_path}", file=sys.stderr)
    print(f"  - Added {new_count} new activities", file=sys.stderr)
    print(f"  - Updated race flags for all activities", file=sys.stderr)
    print(f"  - Total activities: {len(existing_rows)}", file=sys.stderr)

    return new_count


def _setup_session(cookies_str):
    """Setup authenticated session with Strava cookies."""
    cookie_jar = http.cookiejar.CookieJar()
    for cookie_str in cookies_str.split('; '):
        if '=' not in cookie_str:
            continue
        key, value = cookie_str.split('=', 1)
        cookie = http.cookiejar.Cookie(
            version=0, name=key, value=value,
            port=None, port_specified=False,
            domain='.strava.com', domain_specified=True, domain_initial_dot=True,
            path='/', path_specified=True,
            secure=True, expires=None, discard=True,
            comment=None, comment_url=None, rest={}, rfc2109=False
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

    # Get CSRF token
    csrf_token = ''
    for cookie in cookie_jar:
        if cookie.name == '_csrf_token':
            csrf_token = cookie.value
            break

    return session, csrf_token


def update_races():
    """Update races.txt by scraping race-tagged activities from Strava."""
    from vigor.paths import data_dir

    print("Updating races.txt", file=sys.stderr)
    print("=" * 50, file=sys.stderr)

    cookies_file = data_dir() / "strava_cookies.txt"
    if not cookies_file.exists():
        print("\nNo Strava cookies found. You need to provide your session cookies.", file=sys.stderr)
        print(f"\nCreate a file at: {cookies_file}", file=sys.stderr)
        print("\nWith your Strava cookies (from browser DevTools > Network > any request > Cookie header)", file=sys.stderr)
        return 1

    with open(cookies_file, 'r', encoding='utf-8') as f:
        cookies_str = f.read().strip()

    race_ids = scrape_races_http(cookies_str)

    if race_ids:
        output_path = data_dir() / "races.txt"
        save_races(race_ids, output_path)
        print(f"\nSuccess! Saved {len(race_ids)} races to: {output_path}", file=sys.stderr)
    else:
        print("\nNo race activities found.", file=sys.stderr)
        return 1

    return 0


def update_activities():
    """Update activities.csv by scraping all activities from Strava (incremental)."""
    from vigor.paths import data_dir

    print("Updating activities.csv", file=sys.stderr)
    print("=" * 50, file=sys.stderr)

    cookies_file = data_dir() / "strava_cookies.txt"
    if not cookies_file.exists():
        print("\nNo Strava cookies found. You need to provide your session cookies.", file=sys.stderr)
        print(f"\nCreate a file at: {cookies_file}", file=sys.stderr)
        print("\nWith your Strava cookies (from browser DevTools > Network > any request > Cookie header)", file=sys.stderr)
        return 1

    with open(cookies_file, 'r', encoding='utf-8') as f:
        cookies_str = f.read().strip()

    # Setup session
    session, csrf_token = _setup_session(cookies_str)

    # First, get race IDs
    print("\nFetching race tags...", file=sys.stderr)
    race_ids = scrape_races_http(cookies_str)
    races_path = data_dir() / "races.txt"
    save_races(race_ids, races_path)

    # Then update activities CSV
    csv_path = data_dir() / "activities.csv"

    # Incremental update - fetch only new activities
    since_date = get_latest_activity_from_csv(csv_path)
    if since_date:
        print(f"\nIncremental update: fetching activities since {since_date.strftime('%Y-%m-%d')}", file=sys.stderr)
    else:
        print("\nNo existing CSV found, fetching all activities", file=sys.stderr)

    activities = scrape_all_activities(session, csrf_token, since_date=since_date)

    if activities:
        new_count = update_activities_csv(csv_path, activities, race_ids)
        print(f"\nSuccess! Updated {csv_path}", file=sys.stderr)
        print(f"Added {new_count} new activities", file=sys.stderr)
    else:
        print("\nNo new activities found.", file=sys.stderr)
        # Still update race flags for existing activities
        if csv_path.exists():
            update_activities_csv(csv_path, [], race_ids)

    return 0


def main():
    """Legacy main for backwards compatibility."""
    return update_races()


if __name__ == "__main__":
    sys.exit(main())
