"""The immutable encoder used by the patient runtime and its offline check."""

ENCODER_MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
ENCODER_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"


def load_encoder(*, device: str = "cpu", local_files_only: bool = False):
    """Load this revision only; cache or download failures must propagate."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(
        ENCODER_MODEL_ID,
        revision=ENCODER_REVISION,
        device=device,
        local_files_only=local_files_only,
    )
