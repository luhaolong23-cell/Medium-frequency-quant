class AlphaVantageClient:
    provider = "alphavantage"

    def quote_url(self, base_url: str, symbol: str) -> str:
        return f"{base_url}?function=GLOBAL_QUOTE&symbol={symbol}"
