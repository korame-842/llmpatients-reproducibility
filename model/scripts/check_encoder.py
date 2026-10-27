#!/usr/bin/env python3
"""Verify the real cached MiniLM encoder on synthetic text without networking."""
import json
import os
import socket
import sys
from pathlib import Path
from unittest.mock import patch

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agent.core.encoder import ENCODER_MODEL_ID, ENCODER_REVISION, load_encoder

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"


def main():
    with patch.object(socket.socket, "connect", side_effect=RuntimeError("Offline encoder check forbids networking")), \
         patch.object(socket, "create_connection", side_effect=RuntimeError("Offline encoder check forbids networking")):
        import numpy as np
        model = load_encoder(device="cpu", local_files_only=True)
        texts = ["A wholly synthetic patient enjoys walking outdoors.",
                 "A fictional person likes a walk in the park.",
                 "The synthetic spaceship flies between planets."]
        vectors = model.encode(texts, normalize_embeddings=True)
        similarities = vectors @ vectors.T
        assert vectors.shape == (3, 384), vectors.shape
        assert np.isfinite(vectors).all(), "Encoder returned nonfinite values"
        assert similarities[0, 1] > similarities[0, 2], "Related texts did not rank first"
        print(json.dumps({"shape": list(vectors.shape), "finite": bool(np.isfinite(vectors).all()),
                          "related_similarity": float(similarities[0, 1]),
                          "unrelated_similarity": float(similarities[0, 2]),
                          "device": "cpu", "model_id": ENCODER_MODEL_ID,
                          "revision": ENCODER_REVISION,
                          "network": "disabled", "passed": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
