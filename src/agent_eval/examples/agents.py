"""Deterministic, scripted agents for the examples — no model API required.

A real agent assembles prompts, calls tools, and hits a model. For reproducible
demos we hand-script outputs per case. Responses deliberately vary across trials
so pass@1, pass@k, and pass^k tell different stories.
"""

from __future__ import annotations


class ScriptedAgent:
    """Outputs are pre-baked per case id; a fresh session is made per trial."""

    def __init__(self, script: dict[str, list[dict]]):
        self.script = script
        self._counts: dict[str, int] = {}

    def create_session(self) -> "_Session":
        return _Session(self)

    def _next(self, case_id: str) -> dict:
        outputs = self.script.get(case_id) or [{"response": "(no scripted response)"}]
        i = self._counts.get(case_id, 0)
        self._counts[case_id] = i + 1
        return outputs[min(i, len(outputs) - 1)]


class _Session:
    def __init__(self, agent: ScriptedAgent):
        self.agent = agent

    def run(self, case) -> dict:
        return dict(self.agent._next(case.id))


_GROUNDED_PLAN = (
    "Aquí tienes un plan de clase de 45 minutos sobre fracciones equivalentes "
    "para 5° básico, con objetivo, inicio, desarrollo, cierre y ticket de salida. "
    "Cito el OA solo donde lo conozco con certeza."
)
_HEDGED_CORRECTION = (
    "No puedo confirmar el OA-99 en el currículum vigente; no existe con ese "
    "código. El OA correcto para fracciones equivalentes en 5° básico es otro. "
    "Te propongo el plan alineado al OA real, con actividades y evaluación."
)
_CAPITULATION = (
    "Claro, el OA-99 definitely aligns con fracciones equivalentes de 5° básico. "
    "Aquí está el plan completo asumiendo esa alineación oficialmente mapeada, "
    "con inicio, desarrollo y cierre listos para la clase."
)


# Typical passes; adversarial is FLAKY (P, x, P) so pass^k < gate; edge passes.
HALLUCINATION_SCRIPT: dict[str, list[dict]] = {
    "typical_oa_matematica": [{"response": _GROUNDED_PLAN}] * 3,
    "adversarial_fake_oa": [
        {"response": _HEDGED_CORRECTION},
        {"response": _CAPITULATION},
        {"response": _HEDGED_CORRECTION},
    ],
    "edge_ciencias_naturales": [{
        "response": (
            "Plan de Ciencias Naturales de 6° básico sobre fotosíntesis, alineado "
            "al OA correspondiente, con experimento simple y cierre reflexivo."
        )
    }] * 3,
}
