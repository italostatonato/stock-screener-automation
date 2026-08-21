"""config.py — carregamento do config.yaml com caminhos portáveis.

O `config.yaml` é versionado e compartilhado, então não deve conter caminhos
de máquina de ninguém. Caminhos pessoais (destino local do Excel, arquivo de
entrada manual) entram por variável de ambiente usando a sintaxe `${VAR}`.

Variável não definida vira string vazia — as camadas consumidoras já tratam
destino vazio como "não configurado" e simplesmente pulam a etapa.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_ENV_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def expand_env(value: Any) -> Any:
    """Resolve `${VAR}` e `~` em strings, recursivamente em dicts e listas."""
    if isinstance(value, str):
        expanded = _ENV_VAR_RE.sub(
            lambda m: os.environ.get(m.group(1), ""),
            value,
        )
        return os.path.expanduser(expanded) if expanded else expanded

    if isinstance(value, dict):
        return {k: expand_env(v) for k, v in value.items()}

    if isinstance(value, list):
        return [expand_env(v) for v in value]

    return value


def load_config(path: str = "config.yaml") -> dict:
    """Carrega o config.yaml já com as variáveis de ambiente resolvidas."""
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    cfg["paths"] = expand_env(cfg.get("paths", {}))

    destino = cfg["paths"].get("onedrive_output_dir")
    if not destino:
        logger.info(
            "Destino local do Excel não configurado "
            "(defina SCREENER_EXCEL_OUTPUT_DIR para ativar a cópia)."
        )

    return cfg
