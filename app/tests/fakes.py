"""Cliente falso de la API de Claude: devuelve una respuesta fija y guarda los parámetros del pedido."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any


class FakeMessages:
    def __init__(self, datos: Any = None, stop_reason: str = "end_turn", error: Exception | None = None):
        self.datos = datos
        self.stop_reason = stop_reason
        self.error = error
        self.llamadas: list[dict[str, Any]] = []

    def create(self, **params: Any) -> SimpleNamespace:
        self.llamadas.append(params)
        if self.error:
            raise self.error
        texto = self.datos if isinstance(self.datos, str) else json.dumps(self.datos)
        return SimpleNamespace(model=params["model"], stop_reason=self.stop_reason,
                               content=[SimpleNamespace(type="text", text=texto)])


class FakeClient:
    def __init__(self, **kw: Any):
        self.beta = SimpleNamespace(messages=FakeMessages(**kw))

    @property
    def llamadas(self) -> list[dict[str, Any]]:
        return self.beta.messages.llamadas
