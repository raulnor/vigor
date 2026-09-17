"""Read a Strava bulk-export activities.csv into activity dicts."""
import csv
import re
from datetime import datetime
from vigor.paths import data_dir

MI = 1609.344
KM = 1000.0

def _num(v):
    if v is None:
        return None
    v = str(v).replace(",", "").strip()
    if v == "" or v.lower() == "null":
        return None
    try:
        return float(v)
    except ValueError:
        return None
    

_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})")
_DATE_FMTS = ("%b %d, %Y, %I:%M:%S %p", "%B %d, %Y, %I:%M:%S %p",
              "%Y-%m-%d %H:%M:%S", "%Y-%m-%d")


def _parse_date(s):
    if not s:
        return None
    s = s.strip()
    m = _ISO.match(s)
    if m:
        return datetime(*(int(x) for x in m.groups()))
    for fmt in _DATE_FMTS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _col(fieldnames, *cands):
    low = {c.lower() for c in cands}
    for name in fieldnames:
        if name and name.strip().lower() in low:
            return name
    return None


def _serialize(acts):
    out = []
    for a in acts:
        d = a["date"]
        out.append({
            "id": a["id"],
            "name": a["name"],
            "type": a["type"],
            "meters": a["meters"],
            "moving": a["moving"],
            "elev_m": a["elev_m"],
            "ahr": a["ahr"],
            "pace_s_per_m": a["pace_s_per_m"],
            "ts": (d - d.__class__(1970, 1, 1)).total_seconds() * 1000 if d else None,
            "year": d.year if d else None,
            "date_str": d.strftime("%b %d, %Y") if d else "\u2014",
        })
    return out

def load_activities(csv_path):
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fn = reader.fieldnames or []
        C = {
            "id": _col(fn, "Activity ID"),
            "date": _col(fn, "Activity Date"),
            "name": _col(fn, "Activity Name"),
            "type": _col(fn, "Activity Type"),
            "dist": _col(fn, "Distance"),
            "moving": _col(fn, "Moving Time"),
            "elev": _col(fn, "Elevation Gain"),
            "ahr": _col(fn, "Average Heart Rate"),
        }
        acts = []
        for r in reader:
            g = lambda k: (r.get(C[k]) if C[k] else None)
            meters = _num(g("dist"))
            moving = _num(g("moving"))
            acts.append({
                "id": (g("id") or "").strip(),
                "date": _parse_date(g("date")),
                "name": (g("name") or "").strip() or "(untitled)",
                "type": (g("type") or "").strip() or "\u2014",
                "meters": meters,
                "moving": moving,
                "elev_m": _num(g("elev")),
                "ahr": _num(g("ahr")),
                "pace_s_per_m": (moving / meters) if (meters and moving) else None,
            })
    acts.sort(key=lambda a: (a["date"] is not None, a["date"] or datetime.min), reverse=True)
    return _serialize(acts)


def load_shoes(activities_path):
    """Load shoes from activities and calculate mileage."""
    shoes = {}

    with open(activities_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            gear = row.get("Activity Gear", "").strip()
            if not gear:
                continue

            # Parse activity date
            date_str = row.get("Activity Date", "").strip()
            activity_date = _parse_date(date_str)

            # Initialize shoe entry if not seen before
            if gear not in shoes:
                shoes[gear] = {
                    "name": gear,
                    "meters": 0,
                    "count": 0,
                    "oldest": activity_date,
                    "newest": activity_date,
                }
            else:
                # Update oldest and newest dates
                if activity_date:
                    if shoes[gear]["oldest"] is None or activity_date < shoes[gear]["oldest"]:
                        shoes[gear]["oldest"] = activity_date
                    if shoes[gear]["newest"] is None or activity_date > shoes[gear]["newest"]:
                        shoes[gear]["newest"] = activity_date

            # Add mileage
            dist_str = row.get("Distance", "").replace(",", "").strip()
            try:
                meters = float(dist_str) if dist_str else 0
                shoes[gear]["meters"] += meters
                shoes[gear]["count"] += 1
            except ValueError:
                pass

    # Convert dates to timestamps for JSON serialization
    result = []
    for shoe in shoes.values():
        shoe_data = {
            "name": shoe["name"],
            "meters": shoe["meters"],
            "count": shoe["count"],
            "oldest": shoe["oldest"].isoformat() if shoe["oldest"] else None,
            "newest": shoe["newest"].isoformat() if shoe["newest"] else None,
        }
        result.append(shoe_data)

    return result
