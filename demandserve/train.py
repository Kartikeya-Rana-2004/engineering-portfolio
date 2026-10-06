import argparse
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile
from .model import train

URL = "https://archive.ics.uci.edu/static/public/275/bike%2Bsharing%2Bdataset.zip"
ROOT = Path(__file__).resolve().parents[1]


def download(path):
    with urllib.request.urlopen(URL, timeout=60) as response:
        archive = response.read(2 * 1024 * 1024 + 1)
    if len(archive) > 2 * 1024 * 1024:
        raise ValueError("archive exceeded download cap")
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        members = [name for name in z.namelist() if name.rsplit("/",1)[-1] == "day.csv"]
        if len(members) != 1:
            raise ValueError("expected one day.csv")
        # Read only the expected file; never extract arbitrary archive paths.
        content = z.read(members[0])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--input", type=Path, default=ROOT / "data/bike-sharing/day.csv")
    args = parser.parse_args()
    if args.download:
        download(args.input)
    model, report = train(args.input)
    (ROOT / "models").mkdir(exist_ok=True)
    (ROOT / "models/demandserve.json").write_text(json.dumps(model, indent=2) + "\n")
    (ROOT / "evidence/demandserve-evaluation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key:value for key,value in report.items() if key != "test_predictions"}, indent=2))


if __name__ == "__main__":
    main()
