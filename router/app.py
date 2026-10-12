
from flask import Flask, request, Response, jsonify
import requests
import threading
import time
from datetime import datetime

app = Flask(__name__)

REGIONS = {
    "primary": "http://region1:5000",
    "secondary": "http://region2:5000",
}

active_region = "primary"
primary_failures = 0
primary_recoveries = 0
failure_threshold = 3
recovery_threshold = 3
last_event = "System started"
failover_time = None
last_rto_seconds = None
primary_failure_started = None
recovery_started = None
last_recovery_seconds = None
lock = threading.Lock()


def check_health(url):
    try:
        response = requests.get(url + "/health", timeout=2)
        return response.status_code == 200
    except requests.RequestException:
        return False


def monitor_regions():
    global active_region, primary_failures
    global primary_recoveries, last_event, failover_time
    global last_rto_seconds, primary_failure_started
    global recovery_started, last_recovery_seconds

    while True:
        primary_ok = check_health(REGIONS["primary"])

        with lock:
            if active_region == "primary":
                if primary_ok:
                    primary_failures = 0
                    primary_failure_started = None
                else:
                    if primary_failures == 0:
                        primary_failure_started = time.perf_counter()

                    primary_failures += 1

                    if primary_failures >= failure_threshold:
                        now = time.perf_counter()

                        if primary_failure_started is not None:
                            last_rto_seconds = round(
                                now - primary_failure_started, 3
                            )

                        active_region = "secondary"
                        failover_time = time.time()
                        primary_recoveries = 0
                        recovery_started = None

                        last_event = (
                            f"Failover to secondary at "
                            f"{datetime.now().isoformat(timespec='seconds')}"
                        )
                        print(
                            f"{last_event}; "
                            f"failure-detection interval: {last_rto_seconds}s",
                            flush=True,
                        )
            
            else:
                if primary_ok:
                    if primary_recoveries == 0:
                        recovery_started = time.perf_counter()

                    primary_recoveries += 1

                    if primary_recoveries >= recovery_threshold:
                        if recovery_started is not None:
                            last_recovery_seconds = round(
                                time.perf_counter() - recovery_started, 3
                            )

                        active_region = "primary"
                        primary_failures = 0
                        primary_recoveries = 0
                        primary_failure_started = None
                        recovery_started = None

                        last_event = (
                            f"Primary restored at "
                            f"{datetime.now().isoformat(timespec='seconds')}"
                        )
                        print(
                            f"{last_event}; "
                            f"recovery-detection interval: "
                            f"{last_recovery_seconds}s",
                            flush=True,
                        )
                else:
                    primary_recoveries = 0
                    recovery_started = None

        time.sleep(2)


@app.route("/status")
def status():
    with lock:
        return jsonify(
            active_region=active_region,
            primary_failures=primary_failures,
            primary_recoveries=primary_recoveries,
            last_event=last_event,
            rto_seconds=last_rto_seconds,
            recovery_detection_seconds=last_recovery_seconds,
        )


@app.route("/", defaults={"path": ""}, methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
@app.route("/<path:path>", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
def route_request(path):
    with lock:
        selected_region = active_region

    target = REGIONS[selected_region]
    destination = f"{target}/{path}"

    # Save through the active region, then replicate to the other.
    if path == "write" and request.method == "POST":
        try:
            payload = request.get_json(silent=True) or {}

            saved = requests.post(
                destination,
                json=payload,
                timeout=5,
            )

            if not saved.ok:
                return Response(
                    saved.content,
                    status=saved.status_code,
                    content_type="application/json",
                )

            other_region = (
                "secondary" if selected_region == "primary" else "primary"
            )

            try:
                replicated = requests.post(
                    f"{REGIONS[other_region]}/replicate",
                    json=payload,
                    timeout=5,
                )

                if not replicated.ok:
                    return jsonify(
                        status="saved_but_replication_failed",
                        active_region=selected_region,
                        saved_record=saved.json(),
                        replication_region=other_region,
                        replication_error=replicated.text,
                    ), 503

            except requests.RequestException as exc:
                return jsonify(
                    status="saved_but_replication_failed",
                    active_region=selected_region,
                    saved_record=saved.json(),
                    replication_region=other_region,
                    replication_error=str(exc),
                ), 503

            return jsonify(
                status="saved_and_replicated",
                active_region=selected_region,
                saved_record=saved.json(),
                replicated_to=other_region,
            ), 201

        except requests.RequestException as exc:
            return jsonify(error=str(exc)), 502

    try:
        upstream = requests.request(
            method=request.method,
            url=destination,
            params=request.args,
            data=request.get_data(),
            headers={
                key: value
                for key, value in request.headers
                if key.lower() not in ("host", "content-length")
            },
            timeout=5,
        )

        headers = [
            (key, value)
            for key, value in upstream.headers.items()
            if key.lower() not in (
                "content-length", "transfer-encoding", "connection"
            )
        ]
        headers.append(("X-Active-Region", selected_region))

        return Response(
            upstream.content,
            status=upstream.status_code,
            headers=headers,
        )

    except requests.RequestException:
        return jsonify(
            error="Selected region is unreachable",
            selected_region=selected_region,
            message="The monitor will evaluate failover.",
        ), 502


threading.Thread(target=monitor_regions, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
