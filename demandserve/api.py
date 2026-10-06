import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from .model import predict

ROOT = Path(__file__).resolve().parents[1]


def handler_for(model):
    class Handler(BaseHTTPRequestHandler):
        def send_json(self, code, payload):
            body = json.dumps(payload, allow_nan=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/health":
                self.send_json(200, {"status": "ready", "model_id": model["model_id"]})
            else:
                self.send_json(404, {"error": "not_found"})

        def do_POST(self):
            if self.path != "/predict":
                self.send_json(404, {"error": "not_found"})
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 65536:
                    self.send_json(413, {"error": "body_size_out_of_range"})
                    return
                payload = json.loads(self.rfile.read(size))
                result = predict(model, payload)
            except (ValueError, TypeError, KeyError):
                self.send_json(400, {"error": "invalid_prediction_request"})
                return
            self.send_json(200, result)

        def log_message(self, format, *args):
            # No request payload logging.
            return
    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, default=ROOT / "models/demandserve.json")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    model = json.loads(args.model.read_text())
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_for(model))
    print(f"DemandServe ready on http://127.0.0.1:{args.port}; model {model['model_id']}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
