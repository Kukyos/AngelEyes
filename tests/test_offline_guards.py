"""Failure cases that can be checked without a camera, model, or network."""

import os
import unittest
from unittest.mock import patch

from fastapi import HTTPException, Request

from angelseye import load_config
from angelseye.behaviours import Obs, Track
from angelseye.hub import Gate, host_only
from angelseye.rules import Watch, validate


def scope(client="127.0.0.1", forwarded=False, query=b""):
    return {"type": "http", "headers": [(b"x-forwarded-for", b"203.0.113.4")] if forwarded else [],
            "client": (client, 12345), "query_string": query, "method": "GET", "path": "/"}


class VisionRuleTests(unittest.TestCase):
    def setUp(self):
        self.watch = Watch(load_config())
        self.rule = {"id": "r1", "text": "holding a phone", "spec": validate(
            {"subject": "person", "vision": "Is this person holding a phone?"})}
        self.track = Track(7, calibrated=False)
        self.track.add(Obs(0, (0, 0, 50, 150)))

    def test_positive_answer_expires_without_new_model_reply(self):
        self.watch.vision_answer("r1", 7, True, 0.9, 0)
        self.watch.vision_answer("r1", 7, True, 0.9, 4)
        self.assertFalse(self.watch.step([self.track], 4, [self.rule]))
        self.assertTrue(self.watch.step([self.track], 5, [self.rule]))
        self.assertFalse(self.watch.step([self.track], 15, [self.rule]))
        self.assertNotIn(("r1", 7), self.watch.yes)
        self.watch.vision_answer("r1", 7, True, 0.9, 16)
        self.assertFalse(self.watch.step([self.track], 17, [self.rule]))

    def test_out_of_order_and_distant_answers_do_not_make_a_pair(self):
        self.watch.vision_answer("r1", 7, True, 0.9, 5)
        self.watch.vision_answer("r1", 7, True, 0.9, 4)
        self.assertEqual(self.watch.yes[("r1", 7)][0], 1)
        self.watch.vision_answer("r1", 7, True, 0.9, 20)
        self.assertEqual(self.watch.yes[("r1", 7)][0], 1)

    def test_vision_question_must_be_about_one_person(self):
        with self.assertRaisesRegex(ValueError, "one person"):
            validate({"subject": "person", "vision": "Are these two people fighting?"})


class HubGateTests(unittest.IsolatedAsyncioTestCase):
    async def check_gate(self, request_scope):
        delivered = []
        inner_called = []

        async def inner(_scope, _receive, send):
            inner_called.append(True)
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        async def send(message):
            delivered.append(message)

        with patch.dict(os.environ, {"HUB_TOKEN": "test-secret"}):
            await Gate(inner)(request_scope, None, send)
        return inner_called, delivered

    async def test_direct_lan_request_needs_token(self):
        called, messages = await self.check_gate(scope(client="192.168.1.50"))
        self.assertFalse(called)
        self.assertEqual(messages[0]["status"], 401)
        called, messages = await self.check_gate(scope(client="192.168.1.50", query=b"token=test-secret"))
        self.assertTrue(called)
        self.assertEqual(messages[0]["status"], 200)

    async def test_loopback_is_exempt_but_forwarded_requests_are_not(self):
        called, _ = await self.check_gate(scope())
        self.assertTrue(called)
        called, messages = await self.check_gate(scope(forwarded=True))
        self.assertFalse(called)
        self.assertEqual(messages[0]["status"], 401)

    def test_camera_source_requires_loopback(self):
        host_only(Request(scope()))
        for request_scope in (scope(client="192.168.1.50"), scope(forwarded=True)):
            with self.assertRaises(HTTPException) as failure:
                host_only(Request(request_scope))
            self.assertEqual(failure.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
