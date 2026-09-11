"""Read a Strava bulk-export activities.csv into activity dicts."""
import csv
import os
import re
from datetime import datetime
from pathlib import Path

MI = 1609.344
KM = 1000.0


def find_csv(start=None):
    """Walk up from start (or CWD) looking for activities.csv."""
    start = Path(start or os.getcwd()).resolve()
    for d in (start, *start.parents):
        p = d / "activities.csv"
        if p.exists():
            return p
    return None


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


def _to_meters(km):
    # Strava's export puts distance in km or meters depending on the column;
    # a value over 1000 is already meters.
    if km is None:
        return None
    return km if km > 1000 else km * 1000


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
            meters = _to_meters(_num(g("dist")))
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
    return acts