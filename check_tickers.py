import yfinance as yf
from datetime import datetime, timedelta

tickers = ['^BVSP', 'IFIX11.SA', 'BOVA11.SA', 'XFIX11.SA', 'IMOB11.SA', 'IFIX.SA', 'IMOB.SA']
start = (datetime.today() - timedelta(days=30)).strftime('%Y-%m-%d')
end = datetime.today().strftime('%Y-%m-%d')

for t in tickers:
    try:
        df = yf.download(t, start=start, end=end, progress=False, auto_adjust=True)
        if isinstance(df.columns, __import__('pandas').MultiIndex):
            df.columns = df.columns.droplevel(1)
        if not df.empty and 'Close' in df.columns:
            ultimo = round(float(df['Close'].iloc[-1]), 2)
            print('OK  ' + t + ': ' + str(len(df)) + ' pontos, ultimo=' + str(ultimo))
        else:
            print('ERR ' + t + ': vazio')
    except Exception as e:
        print('EXC ' + t + ': ' + str(e))
