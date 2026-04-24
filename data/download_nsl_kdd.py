import sys
from pathlib import Path

import requests


URL = "https://raw.githubusercontent.com/defcom17/NSL_KDD/master/KDDTrain%2B.csv"
OUT_PATH = Path("data/KDDTrain.csv")
CHUNK_SIZE = 8192


def print_progress(downloaded: int, total: int | None) -> None:
    if total and total > 0:
        percent = downloaded / total
        bar_width = 40
        filled = int(bar_width * percent)
        bar = "#" * filled + "-" * (bar_width - filled)
        mb_done = downloaded / (1024 * 1024)
        mb_total = total / (1024 * 1024)
        sys.stdout.write(f"\r[{bar}] {percent * 100:6.2f}% ({mb_done:.2f}/{mb_total:.2f} MB)")
    else:
        mb_done = downloaded / (1024 * 1024)
        sys.stdout.write(f"\rDownloaded: {mb_done:.2f} MB")
    sys.stdout.flush()


def download_file(url: str, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with requests.get(url, stream=True, timeout=30) as response:
            response.raise_for_status()
            total_size = int(response.headers.get("Content-Length", 0)) or None
            downloaded = 0

            with out_path.open("wb") as f:
                for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                    if not chunk:
                        continue
                    f.write(chunk)
                    downloaded += len(chunk)
                    print_progress(downloaded, total_size)

        sys.stdout.write("\nDownload completed successfully.\n")
        sys.stdout.flush()
    except requests.exceptions.RequestException as exc:
        if out_path.exists():
            out_path.unlink(missing_ok=True)
        raise RuntimeError(f"Failed to download dataset: {exc}") from exc
    except OSError as exc:
        raise RuntimeError(f"Failed to write file to disk: {exc}") from exc


def main() -> None:
    print(f"Downloading NSL-KDD training set from: {URL}")
    print(f"Saving to: {OUT_PATH}")
    download_file(URL, OUT_PATH)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Error: {exc}")
        sys.exit(1)
