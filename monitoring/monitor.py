
import requests
import time
import logging
from pathlib import Path

BASE_URL = "http://localhost"
PRIMARY_URL = f"{BASE_URL}:5001/health"
SECONDARY_URL = f"{BASE_URL}:5002/health"
GATEWAY_URL = f"{BASE_URL}:8080/status"

CHECK_INTERVAL = 2

LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "monitor.log"),
        logging.StreamHandler()
    ]
)


def check_health(url):
    try:
        response = requests.get(url, timeout=3)
        return response.status_code == 200
    except requests.RequestException:
        return False


def get_gateway_status():
    try:
        response = requests.get(GATEWAY_URL, timeout=3)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError):
        return None


def main():
    logging.info("CloudGuardians monitoring started")

    previous_region = None
    previous_primary = None
    previous_secondary = None

    try:
        while True:
            primary_ok = check_health(PRIMARY_URL)
            secondary_ok = check_health(SECONDARY_URL)
            status = get_gateway_status()

            if primary_ok != previous_primary:
                logging.info(
                    "PRIMARY: %s",
                    "HEALTHY" if primary_ok else "FAILED"
                )
                previous_primary = primary_ok

            if secondary_ok != previous_secondary:
                logging.info(
                    "SECONDARY: %s",
                    "HEALTHY" if secondary_ok else "FAILED"
                )
                previous_secondary = secondary_ok

            if status is None:
                logging.warning("GATEWAY: UNREACHABLE")
            else:
                active_region = status.get("active_region")
                failures = status.get("primary_failures", 0)

                if active_region != previous_region:
                    logging.warning(
                        "ACTIVE REGION CHANGED: %s -> %s",
                        previous_region or "UNKNOWN",
                        active_region
                    )
                    previous_region = active_region

                if failures > 0:
                    logging.warning(
                        "PRIMARY FAILURE COUNT: %s/3",
                        failures
                    )

            time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        logging.info("Monitoring stopped")


if __name__ == "__main__":
    main()
