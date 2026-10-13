import asyncio
import io
import json
import logging
import unittest

from lib.logging import JsonFormatter, log_context, set_log_context


class JsonLoggingTests(unittest.TestCase):
    def setUp(self):
        self.token = log_context.set({})
        self.stream = io.StringIO()
        self.logger = logging.Logger("test", logging.INFO)
        handler = logging.StreamHandler(self.stream)
        handler.setFormatter(JsonFormatter())
        self.logger.addHandler(handler)

    def tearDown(self):
        log_context.reset(self.token)

    def test_traceback_and_newlines_remain_one_json_line(self):
        try:
            raise ValueError("bad\nvalue")
        except ValueError:
            self.logger.exception("Failed %s", "read")
        lines = self.stream.getvalue().splitlines()
        self.assertEqual(len(lines), 1)
        record = json.loads(lines[0])
        self.assertEqual(record["severity"], "ERROR")
        self.assertIn("ValueError", record["exception"])
        self.assertEqual(record["message"], "Failed read")

    def test_numeric_payload_and_strict_json(self):
        self.logger.info("CPU", extra={"event": "telemetry.cpu", "data": {
            "usage": 45.5, "invalid": float("nan"), "timestamp": "2026-10-13T12:00:00Z",
        }})
        record = json.loads(self.stream.getvalue())
        self.assertEqual(record["data"]["usage"], 45.5)
        self.assertIsNone(record["data"]["invalid"])
        self.assertTrue(record["timestamp"].endswith("+00:00"))

    def test_async_servers_do_not_share_context(self):
        async def emit(name):
            set_log_context(server_name=name, host_name=name + "-host")
            await asyncio.sleep(0)
            self.logger.info("sample")
            set_log_context(host_name=None)
            self.logger.info("reconnecting")

        async def run():
            await asyncio.gather(emit("a"), emit("b"))

        asyncio.run(run())
        records = [json.loads(line) for line in self.stream.getvalue().splitlines()]
        for record in records:
            expected = record["server_name"] + "-host" if record["message"] == "sample" else None
            self.assertEqual(record["host_name"], expected)
        self.assertEqual({r["server_name"] for r in records}, {"a", "b"})
        self.assertEqual(log_context.get(), {})


if __name__ == "__main__":
    unittest.main()
