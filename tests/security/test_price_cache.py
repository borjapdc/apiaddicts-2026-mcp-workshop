from datetime import UTC, datetime, timedelta

from scripts.lib import workshop


def test_only_recent_same_region_verified_prices_are_reused(tmp_path, monkeypatch):
    monkeypatch.setattr(workshop, "LOCAL", tmp_path)
    cached = {
        "source": "https://prices.azure.com/api/retail/prices",
        "checked_at_utc": datetime.now(UTC).isoformat(),
        "meters": [{"armRegionName": "swedencentral", "currencyCode": "USD"}] * 5,
        "indicative_max_active_daily_usd": 5.2848,
    }
    workshop.write_json(tmp_path / "costs.json", cached)
    monkeypatch.setattr(workshop, "fresh_prices", lambda region: {"fresh": region})
    assert workshop.prices("swedencentral")["indicative_max_active_daily_usd"] == 5.2848
    assert workshop.prices("northeurope") == {"fresh": "northeurope"}
    cached["checked_at_utc"] = (datetime.now(UTC) - timedelta(hours=7)).isoformat()
    workshop.write_json(tmp_path / "costs.json", cached)
    assert workshop.prices("swedencentral") == {"fresh": "swedencentral"}