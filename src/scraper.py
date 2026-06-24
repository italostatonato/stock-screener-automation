import time
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
import os

logger = logging.getLogger(__name__)


def scrape_fundsexplorer(cfg: dict) -> pd.DataFrame:
    url = cfg["url"]
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    logger.info(f"Iniciando scraping: {url}")
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), options=options
    )
    wait = WebDriverWait(driver, cfg["wait_timeout"])

    try:
        driver.get(url)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "tbody")))
        time.sleep(cfg["sleep_after_load"])

        # fecha banner de cookies se existir
        try:
            btn = driver.find_element(By.ID, cfg["cookie_button_id"])
            driver.execute_script("arguments[0].click();", btn)
            time.sleep(1)
            logger.debug("Banner de cookies fechado.")
        except Exception:
            pass

        # clica em "Selecionar Todos" para exibir todas as colunas
        try:
            select_all = wait.until(EC.presence_of_element_located(
                (By.ID, "colunas-ranking__todos")
            ))
            driver.execute_script("arguments[0].click();", select_all)
            time.sleep(2)
            logger.info("Todas as colunas selecionadas.")
        except Exception as e:
            logger.warning(f"Não foi possível clicar em 'Selecionar Todos': {e}")

        # aguarda tabela recarregar com todas as colunas
        time.sleep(3)

        headers = [
            th.text.strip()
            for th in driver.find_elements(By.XPATH, "//thead/tr/th")
        ]
        rows = []
        for tr in driver.find_elements(By.XPATH, "//tbody/tr"):
            cells = [td.text.strip() for td in tr.find_elements(By.TAG_NAME, "td")]
            if any(cells):
                rows.append(cells)

        if not rows:
            raise RuntimeError("Nenhuma linha extraída da tabela.")

        # garante alinhamento entre headers e colunas
        max_cols = max(len(r) for r in rows)
        if len(headers) < max_cols:
            headers += [f"col_{i}" for i in range(len(headers), max_cols)]

        df = pd.DataFrame(rows, columns=headers[:max_cols])
        logger.info(f"Scraping concluído: {df.shape[0]} linhas x {df.shape[1]} colunas")
        logger.info(f"Colunas coletadas: {df.columns.tolist()}")
        return df

    except Exception as e:
        logger.error(f"Erro no scraping: {e}")
        raise

    finally:
        driver.quit()


def clean_acoes_raw(df: pd.DataFrame) -> pd.DataFrame:
    """Remove rodapé/legenda que o Investsite inclui no Excel exportado."""
    if df.empty:
        return df

    df = df.dropna(how="all").copy()
    n_antes = len(df)

    for col in ("Ação", "Empresa"):
        if col in df.columns:
            mask_legenda = df[col].astype(str).str.strip().str.lower().eq("legenda")
            df = df[~mask_legenda]

    if "Preço" in df.columns:
        preco_num = pd.to_numeric(df["Preço"], errors="coerce")
        invalid = df["Preço"].notna() & preco_num.isna()
        df = df[~invalid]

    n_removidas = n_antes - len(df)
    if n_removidas:
        logger.info(
            f"Ações após limpeza de rodapé: {n_antes} → {len(df)} "
            f"({n_removidas} linhas removidas)"
        )

    return df.reset_index(drop=True)


def scrape_acoes_investsite(cfg: dict) -> pd.DataFrame:
    """Coleta ranking de ações do Investsite via Selenium (download de Excel).

    Args:
        cfg: dicionário com chaves 'acoes_url', 'wait_timeout', 'download_dir'

    Returns:
        DataFrame bruto com os dados de ações.
    """
    url = cfg.get("acoes_url", "https://www.investsite.com.br/seleciona_acoes.php")
    download_dir = os.path.abspath(cfg.get("download_dir", "data/input/acoes_download"))
    os.makedirs(download_dir, exist_ok=True)

    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    prefs = {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
    }
    options.add_experimental_option("prefs", prefs)

    logger.info(f"Iniciando scraping de ações: {url}")
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), options=options
    )
    wait = WebDriverWait(driver, cfg["wait_timeout"])

    try:
        driver.get(url)
        time.sleep(3)

        # clica em "Procurar Ações"
        btn_procurar = wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, "//button[contains(text(),'Procurar Ações')]")
            )
        )
        driver.execute_script("arguments[0].scrollIntoView(true);", btn_procurar)
        time.sleep(0.5)
        btn_procurar.click()
        logger.info("Botão 'Procurar Ações' clicado.")

        # clica em "Baixar Arquivo Excel"
        btn_excel = wait.until(
            EC.element_to_be_clickable((By.XPATH,
                "//input[contains(@value,'Baixar Arquivo Excel')] | "
                "//button[contains(text(),'Baixar Arquivo Excel')]"
            ))
        )
        driver.execute_script("arguments[0].scrollIntoView(true);", btn_excel)
        time.sleep(0.5)
        btn_excel.click()
        logger.info("Botão 'Baixar Arquivo Excel' clicado.")

        # aguarda download
        time.sleep(8)

        files = [
            os.path.join(download_dir, f)
            for f in os.listdir(download_dir)
            if f.lower().endswith((".xls", ".xlsx"))
        ]
        if not files:
            raise FileNotFoundError("Arquivo Excel de ações não encontrado após download.")

        latest = max(files, key=os.path.getctime)
        logger.info(f"Arquivo baixado: {latest}")

        df = pd.read_excel(latest, sheet_name=0, header=2)
        logger.info(f"Ações brutas: {df.shape[0]} linhas x {df.shape[1]} colunas")
        df = clean_acoes_raw(df)
        return df

    except Exception as e:
        logger.error(f"Erro no scraping de ações: {e}")
        raise

    finally:
        driver.quit()