from __future__ import annotations

from pathlib import Path

import pytest

from afilia.politica import Politica, cargar_politica

RAIZ = Path(__file__).resolve().parents[2]
POLITICA_DIR = RAIZ / "politica"
CASOS = RAIZ / "casos" / "casos-de-referencia.yaml"


@pytest.fixture(scope="session")
def politica() -> Politica:
    return cargar_politica(POLITICA_DIR)
