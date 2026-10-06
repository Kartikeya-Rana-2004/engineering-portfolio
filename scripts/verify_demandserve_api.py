"""Real loopback HTTP smoke test; no external service requests."""
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from demandserve.api import handler_for


def main():
    model = json.loads((ROOT / "models/demandserve.json").read_text())
    payload = (ROOT / "examples/demandserve-request.json").read_bytes()
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(model))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with urllib.request.urlopen(base + "/health", timeout=5) as response:
            health = json.load(response)
        request = urllib.request.Request(base + "/predict", data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=5) as response:
            prediction = json.load(response)
        bad = urllib.request.Request(base + "/predict", data=b"{}", headers={"Content-Type": "application/json"})
        try:
            urllib.request.urlopen(bad, timeout=5)
            raise AssertionError("bad request unexpectedly accepted")
        except urllib.error.HTTPError as exc:
            rejected_status = exc.code
            exc.close()
        assert health["status"] == "ready" and prediction["predicted_count"] >= 0 and rejected_status == 400
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    evidence = {"execution": "real local loopback HTTP server; not hosted publicly", "health": health,
                "prediction": prediction, "invalid_request_status": rejected_status}
    (ROOT / "evidence/demandserve-api-verification.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
