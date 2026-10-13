
import csv
import subprocess
import time
from datetime import datetime
from pathlib import Path

import requests

GATEWAY = "http://localhost:8080"
PRIMARY_CONTAINER = "region1-primary"
TIMEOUT_SECONDS = 90
POLL_INTERVAL = 0.25

LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_FILE = LOG_DIR / "failover_results.csv"


def docker(*args):
    return subprocess.run(
        ["docker", *args],
        capture_output=True,
        text=True,
        check=True
    )


def gateway_status():
    response = requests.get(f"{GATEWAY}/status", timeout=3)
    response.raise_for_status()
    return response.json()


def check_secondary_response():
    try:
        response = requests.get(GATEWAY, timeout=2)
        return (
            response.status_code == 200
            and response.headers.get("X-Active-Region") == "secondary"
        )
    except requests.RequestException:
        return False


def save_result(result):
    new_file = not RESULTS_FILE.exists()

    with RESULTS_FILE.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=result.keys())

        if new_file:
            writer.writeheader()

        writer.writerow(result)


def main():
    print("\nCLOUDGUARDIANS AUTOMATED FAILOVER TEST\n")

    status = gateway_status()

    if status.get("active_region") != "primary":
        print("Test cancelled: primary must be active before testing.")
        return

    if docker("inspect", "-f", "{{.State.Running}}",
              PRIMARY_CONTAINER).stdout.strip() != "true":
        print("Test cancelled: primary container is not running.")
        return

    test_time = datetime.now().isoformat(timespec="seconds")
    result = {
        "timestamp": test_time,
        "result": "FAIL",
        "rto_seconds": "",
        "active_region": "",
        "details": ""
    }

    primary_stopped = False

    try:
        print("Stopping primary container...")

        start = time.perf_counter()
        docker("stop", "--time", "0", PRIMARY_CONTAINER)
        primary_stopped = True

        print("Waiting for secondary takeover...")

        deadline = time.perf_counter() + TIMEOUT_SECONDS

        while time.perf_counter() < deadline:
            if check_secondary_response():
                elapsed = round(time.perf_counter() - start, 3)

                result.update({
                    "result": "PASS",
                    "rto_seconds": elapsed,
                    "active_region": "secondary",
                    "details": "Secondary returned HTTP 200 via gateway"
                })

                print(f"\nFAILOVER SUCCESSFUL!")
                print(f"Measured recovery time: {elapsed} seconds")
                break

            time.sleep(POLL_INTERVAL)

        if result["result"] != "PASS":
            result["details"] = "Secondary did not respond before timeout"
            print("\nFAILOVER TEST FAILED: Timeout exceeded.")

    except (subprocess.CalledProcessError, OSError,
            requests.RequestException) as error:
        result["details"] = str(error)
        print(f"\nTEST ERROR: {error}")

    finally:
        if primary_stopped:
            print("\nRestarting primary container...")
            try:
                docker("start", PRIMARY_CONTAINER)
                print("Primary container restarted.")
            except (subprocess.CalledProcessError, OSError) as error:
                print(f"WARNING: Could not restart primary: {error}")

        save_result(result)
        print(f"Test result saved to: {RESULTS_FILE}")


if __name__ == "__main__":
    main()
