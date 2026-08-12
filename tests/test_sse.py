import queue
import unittest

from sse import SSEBroker, format_sse_event


class TestFormatSSEEvent(unittest.TestCase):
    def test_formats_single_line_event(self):
        out = format_sse_event("usage", '{"a": 1}')
        self.assertEqual(out, b'event: usage\ndata: {"a": 1}\n\n')

    def test_formats_multi_line_data(self):
        out = format_sse_event("usage", "line1\nline2")
        self.assertEqual(out, b"event: usage\ndata: line1\ndata: line2\n\n")


class TestSSEBroker(unittest.TestCase):
    def test_publish_delivers_to_all_subscribers(self):
        broker = SSEBroker()
        q1 = broker.subscribe()
        q2 = broker.subscribe()

        broker.publish("usage", '{"x": 1}')

        self.assertEqual(q1.get_nowait(), format_sse_event("usage", '{"x": 1}'))
        self.assertEqual(q2.get_nowait(), format_sse_event("usage", '{"x": 1}'))

    def test_unsubscribe_stops_delivery(self):
        broker = SSEBroker()
        q1 = broker.subscribe()
        broker.unsubscribe(q1)

        broker.publish("usage", "{}")

        with self.assertRaises(queue.Empty):
            q1.get_nowait()


if __name__ == "__main__":
    unittest.main()
