class TwelveDataClient:
    provider = "twelvedata"

    def time_series_url(self, base_url: str, symbol: str) -> str:
        return f"{base_url}/time_series?symbol={symbol}&interval=1day"
