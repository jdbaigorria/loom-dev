"""
Bloque 9 — tests/unit/test_mock_model.py

Cubre loom.testing:
  - MockModel: ciclo de respuestas, call_count, stream events, structured_output
  - mock_llm: context manager patches get_model, restaura al salir, yield model
"""

import asyncio

from loom.testing import MockModel, mock_llm

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _collect_stream(model, messages=None) -> list[dict]:
    """Run MockModel.stream() and return all emitted events as a list."""

    async def _run():
        events = []
        async for event in model.stream(messages or []):
            events.append(event)
        return events

    return asyncio.run(_run())


# ---------------------------------------------------------------------------
# MM-01 … MM-08  MockModel
# ---------------------------------------------------------------------------


class TestMockModel:
    def test_default_response(self):
        """MM-01: sin args usa 'Mock response'."""
        model = MockModel()
        assert model._responses == ["Mock response"]

    def test_custom_responses(self):
        """MM-02: acepta lista de respuestas custom."""
        model = MockModel(["Hola", "Adiós"])
        assert model._responses == ["Hola", "Adiós"]

    def test_call_count_starts_zero(self):
        """MM-03: call_count empieza en 0."""
        model = MockModel()
        assert model.call_count == 0

    def test_call_count_increments(self):
        """MM-04: call_count sube en 1 por cada stream call."""
        model = MockModel(["R1", "R2"])
        _collect_stream(model)
        assert model.call_count == 1
        _collect_stream(model)
        assert model.call_count == 2

    def test_responses_cycle(self):
        """MM-05: las respuestas ciclan cuando se agota la lista."""
        model = MockModel(["A", "B"])
        events_1 = _collect_stream(model)
        events_2 = _collect_stream(model)
        events_3 = _collect_stream(model)

        text_1 = next(
            e["contentBlockDelta"]["delta"]["text"] for e in events_1 if "contentBlockDelta" in e
        )
        text_2 = next(
            e["contentBlockDelta"]["delta"]["text"] for e in events_2 if "contentBlockDelta" in e
        )
        text_3 = next(
            e["contentBlockDelta"]["delta"]["text"] for e in events_3 if "contentBlockDelta" in e
        )

        assert text_1 == "A"
        assert text_2 == "B"
        assert text_3 == "A"  # cicla

    def test_stream_event_sequence(self):
        """MM-06: stream emite los 6 eventos en el orden correcto."""
        model = MockModel(["Hola mundo"])
        events = _collect_stream(model)

        keys = [list(e.keys())[0] for e in events]
        assert keys == [
            "messageStart",
            "contentBlockStart",
            "contentBlockDelta",
            "contentBlockStop",
            "messageStop",
            "metadata",
        ]

    def test_stream_message_start_role(self):
        """MM-07: messageStart tiene role='assistant'."""
        model = MockModel(["Hi"])
        events = _collect_stream(model)
        msg_start = next(e for e in events if "messageStart" in e)
        assert msg_start["messageStart"]["role"] == "assistant"

    def test_stream_metadata_tokens(self):
        """MM-08: metadata.usage tiene inputTokens=10 y totalTokens > 10."""
        model = MockModel(["one two three"])
        events = _collect_stream(model)
        meta = next(e for e in events if "metadata" in e)
        usage = meta["metadata"]["usage"]
        assert usage["inputTokens"] == 10
        assert usage["outputTokens"] == 3  # 3 palabras
        assert usage["totalTokens"] == 13

    def test_get_config(self):
        """MM-09: get_config retorna dict con provider='mock'."""
        model = MockModel(["X"])
        cfg = model.get_config()
        assert cfg["provider"] == "mock"
        assert cfg["responses"] == ["X"]

    def test_update_config_noop(self):
        """MM-10: update_config no lanza excepciones."""
        model = MockModel()
        model.update_config(temperature=0.9, model_id="anything")  # no-op

    def test_model_id_property(self):
        """MM-11: model_id retorna 'mock'."""
        assert MockModel().model_id == "mock"


# ---------------------------------------------------------------------------
# ML-01 … ML-04  mock_llm context manager
# ---------------------------------------------------------------------------


class TestMockLlm:
    def test_patches_get_model(self):
        """ML-01: dentro del contexto get_model está parcheado."""
        with mock_llm("Hola") as model:
            import loom.core.builder as builder_mod

            assert builder_mod.get_model is not None
            # el patch reemplaza get_model con una función que retorna model
            assert builder_mod.get_model("anything") is model

    def test_yields_mock_model(self):
        """ML-02: el context manager cede una instancia de MockModel."""
        with mock_llm("Test") as model:
            assert isinstance(model, MockModel)

    def test_responses_passed_through(self):
        """ML-03: las respuestas se pasan al MockModel."""
        with mock_llm("R1", "R2") as model:
            assert model._responses == ["R1", "R2"]

    def test_default_response_when_no_args(self):
        """ML-04: sin args el MockModel usa 'Mock response'."""
        with mock_llm() as model:
            assert model._responses == ["Mock response"]

    def test_restores_get_model_after_exit(self):
        """ML-05: al salir del contexto get_model se restaura."""
        import loom.core.builder as builder_mod

        original = builder_mod.get_model

        with mock_llm("X"):
            assert builder_mod.get_model is not original

        assert builder_mod.get_model is original
