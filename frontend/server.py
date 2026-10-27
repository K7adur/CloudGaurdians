import subprocess
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from pathlib import Path
import json

PORT = 3000
GATEWAY = "http://127.0.0.1:8080"
STATIC_DIR = Path(__file__).parent / "static"


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/api/"):
            endpoint = self.path[4:]

            if endpoint not in ["/status", "/data"]:
                self.send_json({"error": "Unknown endpoint"}, 404)
                return

            try:
                with urlopen(GATEWAY + endpoint, timeout=5) as response:
                    data = json.loads(response.read().decode("utf-8"))
                    self.send_json(data)
            except (URLError, HTTPError, TimeoutError) as error:
                self.send_json(
                    {"error": "Gateway unavailable", "details": str(error)},
                    502
                )
            except (ValueError, UnicodeError) as error:
                self.send_json({"error": str(error)}, 502)
            return

        super().do_GET()
    
    def run_chaos_action(self):
        if self.client_address[0] not in ("127.0.0.1", "::1"):
            self.send_json({"error": "Local access only"}, 403)
            return

        actions = {
            "/api/chaos/fail-primary": ["docker", "stop", "region1-primary"],
            "/api/chaos/restore-primary": ["docker", "start", "region1-primary"]
        }

        command = actions.get(self.path)

        if command is None:
            self.send_json({"error": "Unknown chaos action"}, 404)
            return

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=45,
                check=True
            )

            self.send_json({
                "success": True,
                "action": self.path,
                "container": result.stdout.strip(),
                "message": "Docker command completed. Wait for the gateway to detect the change."
            })

        except subprocess.TimeoutExpired:
            self.send_json({"error": "Docker command timed out"}, 504)
        except (subprocess.CalledProcessError, OSError) as error:
            self.send_json({"error": str(error)}, 500)

        def do_POST(self):
            if self.path in (
                "/api/chaos/fail-primary",
                "/api/chaos/restore-primary"
        ):
                self.run_chaos_action()
                return

        if self.path != "/api/write":
            self.send_json({"error": "Unknown endpoint"}, 404)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 10000:
                self.send_json({"error": "Request too large"}, 413)
                return

            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                self.send_json({"error": "Expected JSON object"}, 400)
                return

            message = payload.get("message")
            if not isinstance(message, str) or not message.strip():
                self.send_json({"error": "Message is required"}, 400)
                return

            body = json.dumps({"message": message}).encode("utf-8")
            request = Request(
                GATEWAY + "/write",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST"
            )

            with urlopen(request, timeout=10) as response:
                result = json.loads(response.read().decode("utf-8"))
                self.send_json(result, response.status)

        except HTTPError as error:
            self.send_json(
                {"error": error.read().decode("utf-8", errors="replace")},
                error.code
            )
        except (URLError, TimeoutError) as error:
            self.send_json({"error": str(error)}, 502)
        except (ValueError, UnicodeError) as error:
            self.send_json({"error": str(error)}, 400)


if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", PORT), DashboardHandler)
    print(f"CloudGuardians frontend: http://localhost:{PORT}")
    print("Press Ctrl+C to stop the frontend server.")
    server.serve_forever()
