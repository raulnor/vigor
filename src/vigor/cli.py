import argparse
import sys

from vigor import paths, web

def main(argv=None):
    parser = argparse.ArgumentParser(prog="vigor")
    sub = parser.add_subparsers(dest="command", required=False)

    sub.add_parser("web", help="Run the local web view",
                   add_help=False).set_defaults(run=web.main)
    sub.add_parser("path", help="Print vigor's data directory",
                   add_help=False).set_defaults(run=lambda _: print(paths.data_dir()))
    sub.add_parser("update-races", help="Update races.txt from Strava race tags",
                   add_help=False).set_defaults(run=lambda _: __import__('vigor.strava_scraper', fromlist=['update_races']).update_races())
    sub.add_parser("update-activities", help="Update activities.csv from Strava (incremental)",
                   add_help=False).set_defaults(run=lambda _: __import__('vigor.strava_scraper', fromlist=['update_activities']).update_activities())

    args, rest = parser.parse_known_args(argv)
    if not hasattr(args, 'run'):
        return web.main(rest)
    return args.run(rest)

if __name__ == "__main__":
    sys.exit(main())