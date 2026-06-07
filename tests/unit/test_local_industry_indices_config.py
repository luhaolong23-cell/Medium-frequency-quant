import unittest

from packages.shared.runtime import project_root
from packages.shared.settings import load_local_industry_indices_config
from packages.shared.container import AppContainer


class LocalIndustryIndicesConfigTests(unittest.TestCase):
    def test_loads_official_local_industry_catalog_for_us_cn_jp(self) -> None:
        config = load_local_industry_indices_config(project_root() / 'configs' / 'local_industry_indices.yaml')

        market_codes = [market.market_code for market in config.markets]
        self.assertEqual(market_codes, ['US_EQ', 'CN_EQ', 'JP_EQ'])

        us_market = config.markets[0]
        self.assertEqual(us_market.recommended_primary_family, 'SP500_SECTORS')
        self.assertEqual(us_market.families[0].indices[7].name, 'Information Technology Select Sector')

        cn_market = config.markets[1]
        self.assertEqual(cn_market.recommended_primary_family, 'CSI_ALL_SHARE_INDUSTRY_PRIORITY_L2')
        cn_codes = {index.official_code for family in cn_market.families for index in family.indices}
        self.assertIn('000993', cn_codes)
        self.assertIn('H30184', cn_codes)
        cn_proxy_symbols = {index.proxy_symbol for family in cn_market.families for index in family.indices if index.proxy_symbol}
        self.assertIn('512480.SS', cn_proxy_symbols)
        self.assertIn('512720.SS', cn_proxy_symbols)
        us_match_industries = us_market.families[1].indices[0].match_industries
        self.assertIn('semiconductors', us_match_industries)

        jp_market = config.markets[2]
        self.assertEqual(jp_market.recommended_primary_family, 'TOPIX_17')
        jp_names = {index.name for family in jp_market.families for index in family.indices}
        self.assertIn('TOPIX-17 ELECTRIC APPLIANCES & PRECISION INSTRUMENTS', jp_names)
        self.assertIn('Information & Communication', jp_names)

    def test_app_container_exposes_local_industry_catalog(self) -> None:
        container = AppContainer(provider_mode='mock')

        self.assertEqual(container.local_industry_indices_config.markets[0].market_code, 'US_EQ')
        self.assertEqual(container.local_industry_indices_config.markets[2].market_code, 'JP_EQ')


if __name__ == '__main__':
    unittest.main()
