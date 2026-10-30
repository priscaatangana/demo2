import json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
USER_AGENT = os.environ.get(
    "WEATHER_USER_AGENT",
    "WeatherDashboard/1.0 (local development)",
)


class WeatherHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        parsed_url = urlparse(self.path)
        if parsed_url.path != "/api/weather":
            return super().do_GET()

        params = parse_qs(parsed_url.query)
        try:
            latitude = float(params.get("lat", [""])[0])
            longitude = float(params.get("lon", [""])[0])
        except ValueError:
            self.send_json(400, {"error": "Breddegrad og lengdegrad må være tall."})
            return

        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            self.send_json(400, {"error": "Koordinatene er utenfor gyldig område."})
            return

        query = f"lat={latitude}&lon={longitude}"
        request = Request(
            f"https://api.met.no/weatherapi/locationforecast/2.0/compact?{query}",
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )
        try:
            with urlopen(request, timeout=15) as response:
                body = response.read()
                self.send_response(response.status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "public, max-age=600")
                self.end_headers()
                self.wfile.write(body)
        except HTTPError as error:
            self.send_json(error.code, {"error": f"MET Norway svarte med HTTP {error.code}."})
        except (TimeoutError, URLError) as error:
            self.send_json(502, {"error": f"Fikk ikke kontakt med MET Norway: {error}."})

    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8000), WeatherHandler)
    print("Værsiden kjører på http://127.0.0.1:8000")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nVærserveren stoppes.")
    finally:
        server.server_close()