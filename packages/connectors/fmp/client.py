class FMPClient:
    provider = "fmp"

    def available_exchanges_url(self, base_url: str) -> str:
        return f"{base_url}/available-exchanges"
