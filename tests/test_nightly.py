"""Tests for loading the model bundle used by the nightly Build Lead tool."""
import pathlib
import sys

import joblib
import pytest
from sklearn.dummy import DummyClassifier
from sklearn.preprocessing import FunctionTransformer

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))
import features  # noqa: E402
import nightly  # noqa: E402


def _fitted_predictor():
    predictor = DummyClassifier(strategy="prior")
    predictor.fit([[0], [1]], [0, 1])
    return predictor


def test_loads_current_fitted_predictor_bundle(tmp_path):
    artifact = {
        "method": "test model",
        "feature_columns": features.MODEL_FEATURES,
        "buffer": {"kind": "rooms", "value": 4},
        "predictor": _fitted_predictor(),
    }
    path = tmp_path / "current.joblib"
    joblib.dump(artifact, path)

    predictor, columns, buffer, method = nightly._load_bundle(path)

    assert callable(predictor.predict_proba)
    assert columns == features.MODEL_FEATURES
    assert buffer == {"kind": "rooms", "value": 4.0}
    assert method == "test model"


def test_loads_committed_legacy_preprocessor_estimator_bundle(tmp_path):
    artifact = {
        "method": "test model",
        "feature_columns": features.MODEL_FEATURES,
        "buffer": 4,
        "buffer_definition": nightly.LEGACY_ROOM_BUFFER_DESCRIPTION,
        "preprocessor": FunctionTransformer(),
        "estimator": _fitted_predictor(),
    }
    path = tmp_path / "legacy.joblib"
    joblib.dump(artifact, path)

    predictor, columns, buffer, method = nightly._load_bundle(path)

    assert callable(predictor.predict_proba)
    assert columns == features.MODEL_FEATURES
    assert buffer == {"kind": "rooms", "value": 4.0}
    assert method == "test model"


def test_rejects_numeric_buffer_without_unit_metadata(tmp_path):
    artifact = {
        "method": "test model",
        "feature_columns": features.MODEL_FEATURES,
        "buffer": 4,
        "predictor": _fitted_predictor(),
    }
    path = tmp_path / "ambiguous-buffer.joblib"
    joblib.dump(artifact, path)

    with pytest.raises(ValueError, match="buffer_definition"):
        nightly._load_bundle(path)
