class EODHDClient:
    provider = "eodhd"

    def eod_url(self, base_url: str, symbol: str) -> str:
        return f"{base_url}/eod/{symbol}"
