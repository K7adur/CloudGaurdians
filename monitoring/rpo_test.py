
import csv
import subprocess
import time
import uuid
from datetime import datetime
from pathlib import Path

import requests

GATEWAY = "http://localhost:8080"
PRIMARY = "http://localhost:5001"
SECONDARY = "http://localhost:5002"
CONTAINER = "region1-primary"

LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_FILE = LOG_DIR / "rpo_results.csv"


def docker(*args):
    return subprocess.run(
        ["docker", *args],
        capture_output=True,
        text=True,
        check=True
    )


def get_json(url):
    response = requests.get(url, timeout=3)
    response.raise_for_status()
    return response.json()


def has_record(url, message):
    records = get_json(url + "/data")
    return any(record.get("message") == message for record in records)


def save_result(result):
    new_file = not RESULTS_FILE.exists()

    with RESULTS_FILE.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=result.keys())
        if new_file:
            writer.writeheader()
        writer.writerow(result)


def main():
    print("\nCLOUDGUARDIANS AUTOMATED RPO TEST\n")

    message = "RPO-TEST-" + uuid.uuid4().hex[:12]
    stopped = False

    result = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "test_record": message,
        "primary_verified": False,
        "secondary_verified": False,
        "failover_verified": False,
        "observed_data_loss": "",
        "result": "FAIL"
    }

    try:
        status = get_json(GATEWAY + "/status")

        if status.get("active_region") != "primary":
            raise RuntimeError("Primary region must be active")

        if docker(
            "inspect", "-f", "{{.State.Running}}", CONTAINER
        ).stdout.strip() != "true":
            raise RuntimeError("Primary container must be running")

        if get_json(SECONDARY + "/health").get("status") != "healthy":
            raise RuntimeError("Secondary must be healthy")

        print("1. Writing test record...")

        response = requests.post(
            GATEWAY + "/write",
            json={"message": message},
            timeout=10
        )
        response.raise_for_status()

        if response.json().get("status") != "saved_and_replicated":
            raise RuntimeError("Replication was not acknowledged")

        print("2. Checking both databases...")

        result["primary_verified"] = has_record(PRIMARY, message)
        result["secondary_verified"] = has_record(SECONDARY, message)

        if not (
            result["primary_verified"]
            and result["secondary_verified"]
        ):
            raise RuntimeError("Record missing before failover")

        print("3. Stopping primary application...")

        stopped = True
        docker("stop", "--time", "0", CONTAINER)

        print("4. Waiting for secondary takeover...")

        deadline = time.monotonic() + 90

        while time.monotonic() < deadline:
            try:
                status = get_json(GATEWAY + "/status")

                if status.get("active_region") == "secondary":
                    records = get_json(GATEWAY + "/data")
                    result["failover_verified"] = any(
                        record.get("message") == message
                        for record in records
                    )
                    if result["failover_verified"]:
                        break

            except requests.RequestException:
                pass

            time.sleep(0.5)

        if result["failover_verified"]:
            result["observed_data_loss"] = 0
            result["result"] = "PASS"
            print("\nRPO TEST PASSED!")
            print("Record available after failover.")
            print("Observed data loss: 0 test records")
        else:
            print("\nRPO TEST FAILED!")
            print("Record not confirmed after failover.")

    except (
        requests.RequestException,
        subprocess.CalledProcessError,
        OSError,
        RuntimeError
    ) as error:
        print(f"\nTEST ERROR: {error}")

    finally:
        if stopped:
            print("\nRestarting primary...")
            try:
                docker("start", CONTAINER)
                print("Primary container restarted.")
            except (subprocess.CalledProcessError, OSError) as error:
                print(f"Restart failed: {error}")

        save_result(result)
        print(f"Results saved to: {RESULTS_FILE}")


if __name__ == "__main__":
    main()
