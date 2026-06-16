import io
import json

from loguru import logger

from server.core.logging_setup import _json_sink


def test_json_sink_writes_single_json_line_without_format_key_error():
    stream = io.StringIO()
    sink = _json_sink(stream)

    handler_id = logger.add(sink, level="INFO")
    try:
        logger.info("json logging smoke")
    finally:
        logger.remove(handler_id)

    payload = json.loads(stream.getvalue())
    assert payload["message"] == "json logging smoke"
    assert payload["level"] == "INFO"
    assert "ts" in payload
