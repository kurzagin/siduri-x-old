import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import threading

from apps.orchestrator.src.siduri_orchestrator.server import Handler


class ChatCorsTests(unittest.TestCase):
    def test_options_chat_returns_cors_headers(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            connection = HTTPConnection("127.0.0.1", server.server_port)
            connection.request("OPTIONS", "/chat", headers={"Origin": "null", "Access-Control-Request-Method": "POST"})
            response = connection.getresponse()
            self.assertEqual(response.status, 204)
            self.assertEqual(response.getheader("Access-Control-Allow-Origin"), "*")
            self.assertIn("POST", response.getheader("Access-Control-Allow-Methods", ""))
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
