import yaml

from src.config import expand_env, load_config


def test_expand_env_resolve_variavel_definida(monkeypatch):
    monkeypatch.setenv("SCREENER_TEST_DIR", "D:/Relatorios")
    assert expand_env("${SCREENER_TEST_DIR}") == "D:/Relatorios"


def test_expand_env_variavel_ausente_vira_vazio(monkeypatch):
    monkeypatch.delenv("SCREENER_TEST_DIR", raising=False)
    # String vazia é o contrato: as camadas de entrega tratam vazio como
    # "destino não configurado" e pulam a cópia.
    assert expand_env("${SCREENER_TEST_DIR}") == ""


def test_expand_env_preserva_valores_nao_string():
    assert expand_env(20) == 20
    assert expand_env(None) is None
    assert expand_env([1, "a"]) == [1, "a"]


def test_expand_env_recursivo(monkeypatch):
    monkeypatch.setenv("SCREENER_TEST_DIR", "/tmp/x")
    out = expand_env({"paths": {"out": "${SCREENER_TEST_DIR}", "keep": "data"}})
    assert out == {"paths": {"out": "/tmp/x", "keep": "data"}}


def test_load_config_expande_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("SCREENER_EXCEL_OUTPUT_DIR", "D:/Saida")
    monkeypatch.setenv("BRAPI_TOKEN", "token-de-teste")
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        'paths:\n'
        '  data_dir: "data"\n'
        '  onedrive_output_dir: "${SCREENER_EXCEL_OUTPUT_DIR}"\n'
        'scraper:\n'
        '  brapi_token: "${BRAPI_TOKEN}"\n'
        'filters:\n'
        '  top_n: 20\n',
        encoding="utf-8",
    )

    cfg = load_config(str(cfg_file))

    assert cfg["paths"]["onedrive_output_dir"] == "D:/Saida"
    assert cfg["paths"]["data_dir"] == "data"
    assert cfg["scraper"]["brapi_token"] == "token-de-teste"
    assert cfg["filters"]["top_n"] == 20


def test_config_versionado_nao_tem_caminho_pessoal():
    """O config.yaml é compartilhado: nada de caminho de máquina de alguém.

    Verifica o YAML cru de propósito — depois da expansão o valor legítimo
    de quem definiu SCREENER_EXCEL_OUTPUT_DIR seria absoluto.
    """
    with open("config.yaml", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    for key, value in raw["paths"].items():
        if not isinstance(value, str):
            continue
        absoluto = value.startswith("/") or value[1:2] == ":"
        assert not absoluto, f"paths.{key} tem caminho absoluto no repo: {value}"


def test_config_versionado_nao_tem_bloco_acoes_morto():
    """`acoes:` na raiz nunca foi lido — filters.py usa filters.acoes."""
    with open("config.yaml", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    assert "acoes" not in raw
    assert "acoes" in raw["filters"]
