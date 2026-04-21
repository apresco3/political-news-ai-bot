import argparse
import os
import shutil
from datetime import datetime

SEEN_FILE = "seen_headlines.txt"


def clear_seen_sources(make_backup=True):
    if not os.path.exists(SEEN_FILE):
        open(SEEN_FILE, "w", encoding="utf-8").close()
        print(f"Created empty {SEEN_FILE}.")
        return

    if make_backup:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_file = f"{SEEN_FILE}.{timestamp}.bak"
        shutil.copyfile(SEEN_FILE, backup_file)
        print(f"Backed up {SEEN_FILE} to {backup_file}.")

    open(SEEN_FILE, "w", encoding="utf-8").close()
    print(f"Cleared {SEEN_FILE}. The next bot run will treat RSS headlines as unseen.")


def main():
    parser = argparse.ArgumentParser(
        description="Clear the seen-headlines dedupe file for a fresh demo scrape."
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Clear seen_headlines.txt without creating a timestamped backup.",
    )
    args = parser.parse_args()
    clear_seen_sources(make_backup=not args.no_backup)


if __name__ == "__main__":
    main()
