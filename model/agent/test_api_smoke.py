"""API, real graph and questionnaire contracts with synthetic offline inputs.

The language model and encoder are deterministic fakes; these tests establish
runtime integration, persistence and response schemas, not generation quality.
"""

import json
import shutil
import socket
import tempfile
import unittest
from contextlib import ExitStack, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore

from agent.test_session_memory import api, builder
from agent.core import questionnaire_runner
from agent.core.memory_store import JsonlMemoryStore
from agent.core.patient_profile import PatientProfile


class SyntheticModel:
    def generate(self, prompt, **kwargs):
        if "You are a classifier" in prompt:
            return '{"topic_label": "unknown", "emotion_label": "SEEKING"}'
        if '"facts"' in prompt:
            return '{"facts": []}'
        return "I feel comfortable talking about an ordinary walk."


class TestAPISmoke(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.patients = self.root / "data" / "patients"
        self.runs = self.root / "tests" / "runs"
        self.memory = self.root / "data" / "memory"
        self.patients.mkdir(parents=True)
        self.runs.mkdir(parents=True)
        self.store = JsonlMemoryStore(self.memory)
        encoder = Mock()
        encoder.encode.side_effect = lambda texts, **kw: [[1.0, 0.0, 0.0] for _ in texts]
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for target, values in (
            (api, {"PATIENTS_DIR": self.patients, "RUNS_DIR": self.runs,
                   "MEMORY_DIR": self.memory, "ROOT_DIR": self.root,
                   "session_loggers": {}, "EXPORT_TOKEN": None}),
            (builder, {"ROOT_DIR": self.root, "MEMORY_STORE": self.store,
                       "PROFILE_CACHE": {}, "MEMORY_CACHE_LOADED": {},
                       "LATEST_SUMMARY_CACHE": {}, "LATEST_REFLECTION_CACHE": {},
                       "EPISODE_TASKS": {}, "llm_runner": SyntheticModel(),
                       "st_model": encoder,
                       "LONG_TERM_STORE": InMemoryStore(index={
                           "dims": 3, "embed": lambda texts: [[1.0, 0.0, 0.0] for _ in texts],
                           "fields": ["text"],
                       })}),
        ):
            for name, value in values.items():
                self.stack.enter_context(patch.object(target, name, value))
        from agent.utils import run_logger
        self.stack.enter_context(patch.object(run_logger, "RUNS_BASE_DIR", self.runs))
        self.stack.enter_context(patch.object(api, "graph", builder.build_graph(MemorySaver())))
        self.stack.enter_context(patch.object(socket.socket, "connect", side_effect=AssertionError("Network forbidden")))
        self.client = self.stack.enter_context(TestClient(api.app))
        self.patient_payload = {
            "id": "synthetic_001", "name": "Synthetic Patient", "age": 30,
            "gender": "non-binary", "diagnosis": "Fictional training example",
            "difficulty_level": 1, "psychological_profile": "Calm and reflective.",
            "background": "A wholly synthetic software test fixture.",
            "therapy_goals": ["Practice ordinary conversation"], "session_id": "intake",
        }

    def test_plural_and_legacy_initialization_share_the_same_patient(self):
        first = self.client.post("/patients", json=self.patient_payload)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["code"], "PATIENT_CREATED")
        second = self.client.post("/patient", json=self.patient_payload)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["code"], "PATIENT_EXISTS")
        self.assertEqual(len(list(self.patients.glob("*.yaml"))), 1)

    def test_distributed_profiles_are_reused_by_their_declared_identifiers(self):
        source = Path(__file__).resolve().parents[1] / "data" / "patients"
        original = {}
        for path in source.glob("*.yaml"):
            target = self.patients / path.name
            shutil.copyfile(path, target)
            original[target.name] = target.read_bytes()
        self.assertEqual(len(original), 10)
        for name in sorted(original):
            profile = PatientProfile.from_file(str(self.patients / name))
            payload = {**self.patient_payload, "id": profile.patient_id}
            with self.subTest(profile=name):
                for endpoint in ("/patients", "/patient"):
                    response = self.client.post(endpoint, json=payload)
                    self.assertEqual(response.status_code, 200, response.text)
                    self.assertEqual(response.json()["status"], "exists")
                    self.assertEqual(response.json()["external_patient_id"], Path(name).stem)
        self.assertEqual({path.name: path.read_bytes() for path in self.patients.glob("*.yaml")}, original)

    def test_declared_legacy_identifier_uses_the_original_profile_for_chat(self):
        source = Path(__file__).resolve().parents[1] / "data" / "patients" / "jason_smith_001.yaml"
        target = self.patients / source.name
        shutil.copyfile(source, target)
        original = target.read_bytes()
        created = self.client.post("/patients", json={**self.patient_payload, "id": "Jason_001"})
        self.assertEqual(created.status_code, 200, created.text)
        self.assertEqual(created.json()["status"], "exists")
        self.assertEqual(created.json()["external_patient_id"], "jason_smith_001")
        response = self.client.post("/chat-response", json={
            "external_patient_id": created.json()["external_patient_id"],
            "therapist_id": "offline-therapist", "session_id": "legacy-profile",
            "step_id": 1, "user_message": "How are you feeling today?",
        })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["patient_name"], "Jason Smith")
        self.assertEqual(target.read_bytes(), original)
        self.assertEqual(len(list(self.patients.glob("*.yaml"))), 1)

    def test_real_graph_chat_finalization_and_next_session(self):
        self.client.post("/patients", json=self.patient_payload).raise_for_status()
        payload = {"external_patient_id": "synthetic_001", "therapist_id": "synthetic_therapist",
                   "session_id": "first", "step_id": 1,
                   "user_message": "How do you feel about taking a short walk?"}
        response = self.client.post("/chat-response", json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertIn("ordinary walk", body["message"])
        self.assertEqual(body["patient_name"], "Synthetic Patient")
        self.assertEqual(len(body["emotion_timeline"]), 1)
        self.assertTrue(all(0 <= value <= 1 for value in body["emotion_snapshot"]["vector"].values()))
        close = {key: payload[key] for key in ("external_patient_id", "therapist_id", "session_id")}
        ended = self.client.post("/session-end", json=close)
        self.assertEqual(ended.status_code, 200, ended.text)
        self.assertEqual(ended.json()["status"], "finalized")
        self.assertEqual(ended.json()["memory_status"], "complete")
        records = list(self.store.iter_records("synthetic_001", "synthetic_therapist"))
        self.assertEqual({r["type"] for r in records}, {
            "conversation_turn", "fact_batch", "session_reflection", "long_term_summary",
        })
        self.assertEqual(self.client.post("/session-end", json=close).json()["status"], "not_found")
        next_turn = self.client.post("/chat-response", json={**payload, "session_id": "second"})
        self.assertEqual(next_turn.status_code, 200, next_turn.text)
        key = ("synthetic_therapist", "synthetic_001", "second")
        self.assertIn("ordinary walk", api.session_loggers[key]["latest_state"]["summary"])

    def test_questionnaire_scores_and_persists_in_temporary_directory(self):
        self.client.post("/patients", json=self.patient_payload).raise_for_status()
        fake = Mock()
        fake.generate.return_value = "1"
        with patch.object(questionnaire_runner, "ROOT_DIR", self.root), \
             patch.object(questionnaire_runner, "RESULTS_DIR", self.root / "results"), \
             patch.object(questionnaire_runner, "create_llm_runner", return_value=fake), \
             patch.object(questionnaire_runner, "questionnaire_inter_batch_delay_seconds", return_value=0), \
             redirect_stdout(StringIO()):
            runner = questionnaire_runner.QuestionnaireRunner("phq9", "synthetic_001")
            result = runner.run()
            self.assertEqual(len(result["answers"]), 10)
            self.assertEqual(result["scores"]["total"], 9)
            self.assertTrue(runner.result_path.exists())
            self.assertFalse(runner.partial_path.exists())
            self.assertEqual(json.loads(runner.result_path.read_text()), result)


if __name__ == "__main__":
    unittest.main()
