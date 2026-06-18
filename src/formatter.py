import logging
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter

logger = logging.getLogger(__name__)

# ── Definição de colunas por tipo de formatação ────────────────────────────────

FII_MONEY_COLS   = ["PREÇO ATUAL (R$)", "LIQUIDEZ DIÁRIA (R$)", "PATRIMÔNIO LÍQUIDO", "VPA"]
FII_PCT_COLS     = [
    "DIVIDEND YIELD", "DY (3M) ACUMULADO", "DY (6M) ACUMULADO", "DY (12M) ACUMULADO",
    "DY (3M) MÉDIA", "DY (6M) MÉDIA", "DY (12M) MÉDIA", "DY ANO",
    "DY PATRIMONIAL", "VARIAÇÃO PREÇO", "RENTAB. PERÍODO", "RENTAB. ACUMULADA",
    "VARIAÇÃO PATRIMONIAL", "RENTAB. PATR. PERÍODO", "RENTAB. PATR. ACUMULADA",
]
FII_NUM_COLS     = ["P/VP", "P/VPA", "ÚLTIMO DIVIDENDO", "VOLATILIDADE"]

ACOES_MONEY_COLS = ["Preço", "Volume Diário Médio (3 meses)", "Market Cap Empresa"]
ACOES_PCT_COLS   = [
    "ROTanC", "ROInvC", "RPL", "ROA", "Margem Líquida", "Margem Bruta", "Margem EBIT",
    "Dividend Yield", "Alavancagem Financeira", "Passivo/Patrimônio Líquido",
]
ACOES_NUM_COLS   = [
    "Preço/Lucro", "Preço/VPA", "Preço/Receita Líquida", "Preço/FCO", "Preço/FCF",
    "Preço/EBIT", "Preço/NCAV", "Preço/Ativo Total", "Preço/Capital Giro",
    "EV/EBIT", "EV/EBITDA", "EV/Receita Líquida", "EV/FCF", "EV/FCO", "EV/Ativo Total",
    "Giro do Ativo Inicial", "ROTanC", "ROInvC",
]

# Formatos Excel
FMT_MONEY = 'R$ #.##0,00'
FMT_PCT   = '0,00%'
FMT_NUM   = '0,00'
FMT_INT   = '#.##0'

# Cores
COLOR_HEADER = "1F4E79"   # azul escuro
COLOR_HEADER_FONT = "FFFFFF"
COLOR_ALT_ROW = "EBF3FB"  # azul claro alternado


def _style_sheet(ws, money_cols, pct_cols, num_cols):
    """Aplica formatação visual e numérica numa aba."""
    # cabeçalho
    header_fill = PatternFill("solid", fgColor=COLOR_HEADER)
    header_font = Font(bold=True, color=COLOR_HEADER_FONT, size=10)
    alt_fill    = PatternFill("solid", fgColor=COLOR_ALT_ROW)
    center      = Alignment(horizontal="center", vertical="center")
    thin        = Side(style="thin", color="CCCCCC")
    border      = Border(left=thin, right=thin, top=thin, bottom=thin)

    # mapeia nome da coluna → índice (1-based)
    col_idx = {cell.value: cell.column for cell in ws[1]}

    for cell in ws[1]:
        cell.fill   = header_fill
        cell.font   = header_font
        cell.alignment = center
        cell.border = border

    # formata linhas de dados
    for row_idx, row in enumerate(ws.iter_rows(min_row=2), start=2):
        fill = alt_fill if row_idx % 2 == 0 else PatternFill()
        for cell in row:
            cell.fill      = fill
            cell.alignment = Alignment(vertical="center")
            cell.border    = border

    # aplica formato numérico por coluna
    for col_name, fmt in (
        [(c, FMT_MONEY) for c in money_cols] +
        [(c, FMT_PCT)   for c in pct_cols]   +
        [(c, FMT_NUM)   for c in num_cols]
    ):
        if col_name in col_idx:
            col_letter = get_column_letter(col_idx[col_name])
            for cell in ws[col_letter][1:]:
                cell.number_format = fmt

    # ajusta largura das colunas
    for col in ws.columns:
        max_len = max((len(str(c.value)) if c.value else 0) for c in col)
        ws.column_dimensions[get_column_letter(col[0].column)].width = min(max_len + 4, 40)

    # congela primeira linha
    ws.freeze_panes = "A2"


def _add_premissas(wb, cfg: dict, data_hoje: str, n_fiis: int, n_acoes: int):
    """Cria aba Premissas com fontes, filtros e data de atualização."""
    if "Premissas" in wb.sheetnames:
        del wb["Premissas"]
    ws = wb.create_sheet("Premissas", 0)  # primeira aba

    header_fill = PatternFill("solid", fgColor=COLOR_HEADER)
    header_font = Font(bold=True, color=COLOR_HEADER_FONT, size=11)
    bold        = Font(bold=True, size=10)
    normal      = Font(size=10)
    thin        = Side(style="thin", color="CCCCCC")
    border      = Border(left=thin, right=thin, top=thin, bottom=thin)

    rows = [
        ("STOCK SCREENER — PREMISSAS E METODOLOGIA", None),
        (None, None),
        ("Última atualização", data_hoje),
        ("FIIs selecionados", str(n_fiis)),
        ("Ações selecionadas", str(n_acoes)),
        (None, None),
        ("── FONTES ──", None),
        ("FIIs", "https://www.fundsexplorer.com.br/ranking"),
        ("Ações BR", "https://www.investsite.com.br/seleciona_acoes.php"),
        (None, None),
        ("── FILTROS FII ──", None),
        ("P/VP máximo",         str(cfg["filters"]["pvp_max"])),
        ("Dividend Yield mín.", f"{cfg['filters']['dy_min']*100:.2f}%"),
        ("Liquidez diária mín.", f"R$ {cfg['filters']['liquidez_min']:,.0f}".replace(",", ".")),
        ("Patrimônio mín.",      f"R$ {cfg['filters']['patrimonio_min']:,.0f}".replace(",", ".")),
        ("Volatilidade máx.",    str(cfg["filters"]["volatilidade_max"])),
        ("Top N selecionados",   str(cfg["filters"]["top_n"])),
        (None, None),
        ("── FILTROS AÇÕES ──", None),
        ("P/VPA máximo",         str(cfg["filters"]["acoes"]["pvpa_max"])),
        ("P/L máximo",           str(cfg["filters"]["acoes"]["pl_max"])),
        ("EV/EBIT máximo",       str(cfg["filters"]["acoes"]["ev_ebit_max"])),
        ("EV/EBITDA máximo",     str(cfg["filters"]["acoes"]["ev_ebitda_max"])),
        ("Margem Líquida mín.",  f"{cfg['filters']['acoes']['margem_min']*100:.0f}%"),
        ("ROA mín.",             f"{cfg['filters']['acoes']['roa_min']*100:.0f}%"),
        ("RPL mín.",             f"{cfg['filters']['acoes']['rpl_min']*100:.0f}%"),
        ("ROInvC mín.",          f"{cfg['filters']['acoes']['roinvc_min']*100:.0f}%"),
        ("Passivo/PL máx.",      str(cfg["filters"]["acoes"]["passivo_pl_max"])),
        ("Alavancagem máx.",     str(cfg["filters"]["acoes"]["alavancagem_max"])),
        ("DY mín.",              f"{cfg['filters']['acoes']['dy_min']*100:.0f}%"),
        ("Volume diário mín.",   f"R$ {cfg['filters']['acoes']['volume_min']:,.0f}".replace(",", ".")),
        ("Market Cap mín.",      f"R$ {cfg['filters']['acoes']['market_cap_min']:,.0f}".replace(",", ".")),
        ("Top N selecionados",   str(cfg["filters"]["acoes"]["top_n"])),
        (None, None),
        ("── ORDENAÇÃO ──", None),
        ("FIIs",    "Dividend Yield (desc) → P/VP (asc) → Liquidez (desc)"),
        ("Ações",   "P/VPA (asc) → Dividend Yield (desc)"),
    ]

    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 55

    for i, (label, value) in enumerate(rows, start=1):
        cell_a = ws.cell(row=i, column=1, value=label)
        cell_b = ws.cell(row=i, column=2, value=value)

        if i == 1:
            cell_a.font = header_font
            cell_a.fill = header_fill
            cell_b.fill = header_fill
        elif label and label.startswith("──"):
            cell_a.font = bold
        elif label:
            cell_a.font = bold
            cell_b.font = normal

        for cell in (cell_a, cell_b):
            cell.border = border
            cell.alignment = Alignment(vertical="center")


def format_workbook(snapshot_path: str, cfg: dict, data_hoje: str, n_fiis: int, n_acoes: int):
    """Carrega o Excel gerado, aplica formatação completa e salva."""
    logger.info("Aplicando formatação ao Excel...")
    wb = load_workbook(snapshot_path)

    if "FII" in wb.sheetnames:
        _style_sheet(wb["FII"], FII_MONEY_COLS, FII_PCT_COLS, FII_NUM_COLS)

    if "Ações BR" in wb.sheetnames:
        _style_sheet(wb["Ações BR"], ACOES_MONEY_COLS, ACOES_PCT_COLS, ACOES_NUM_COLS)

    _add_premissas(wb, cfg, data_hoje, n_fiis, n_acoes)

    # reordena abas: Premissas → FII → Ações BR
    order = ["Premissas", "FII", "Ações BR"]
    for i, name in enumerate(order):
        if name in wb.sheetnames:
            wb.move_sheet(name, offset=wb.sheetnames.index(name) - i)

    wb.save(snapshot_path)
    logger.info(f"Formatação concluída: {snapshot_path}")