import time
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd

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