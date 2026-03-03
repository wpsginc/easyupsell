import csv
import pytest
from pathlib import Path
from unittest.mock import patch

from easyupsell.core.opportunities import (
    load_and_deduplicate_gaps,
    enrich_opportunities_batch,
)


def _make_catalog_gaps_csv(tmp_path: Path) -> Path:
    path = tmp_path / "catalog_gaps.csv"
    rows = [
        {"source_category": "Tactical Boots", "missing_product_type": "Socks"},
        {"source_category": "Firefighter Helmets", "missing_product_type": "Socks"},
        {"source_category": "EMS Suits", "missing_product_type": "Socks"},
        {"source_category": "Tactical Boots", "missing_product_type": "Hydration Pack"},
        {"source_category": "", "missing_product_type": ""},
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["source_category", "missing_product_type"]
        )
        writer.writeheader()
        writer.writerows(rows)
    return path


def _make_opportunities():
    return [
        {
            "product_type": "Socks",
            "source_categories": ["Tactical Boots", "Firefighter Helmets", "EMS Suits"],
            "category_count": 3,
            "description": "",
            "price_range_low": "",
            "price_range_high": "",
            "priority": "",
            "sourcing_notes": "",
        },
        {
            "product_type": "Hydration Pack",
            "source_categories": ["Tactical Boots"],
            "category_count": 1,
            "description": "",
            "price_range_low": "",
            "price_range_high": "",
            "priority": "",
            "sourcing_notes": "",
        },
    ]


def test_load_and_deduplicate_gaps_preserves_row_count_and_groups_categories(tmp_path):
    csv_path = _make_catalog_gaps_csv(tmp_path)

    unique_opps, detail_rows = load_and_deduplicate_gaps(csv_path)

    assert len(detail_rows) == 4
    assert len(unique_opps) == 2

    socks = next(item for item in unique_opps if item["product_type"] == "Socks")
    assert socks["category_count"] == 3
    assert socks["source_categories"] == [
        "EMS Suits",
        "Firefighter Helmets",
        "Tactical Boots",
    ]

    hydration = next(
        item for item in unique_opps if item["product_type"] == "Hydration Pack"
    )
    assert hydration["category_count"] == 1
    assert hydration["source_categories"] == ["Tactical Boots"]

    assert unique_opps[0]["product_type"] == "Socks"


def test_load_and_deduplicate_gaps_missing_file_is_deterministic(tmp_path):
    missing_csv = tmp_path / "missing_catalog_gaps.csv"

    with pytest.raises(FileNotFoundError, match="Catalog gaps file not found"):
        load_and_deduplicate_gaps(missing_csv)


@patch("easyupsell.core.opportunities.call_llm_generic")
def test_enrich_opportunities_batch_successful_enrichment_keeps_rows(mock_call_llm):
    opportunities = _make_opportunities()
    mock_call_llm.return_value = {
        "opportunities": [
            {
                "index": 1,
                "description": "Moisture-wicking sock pair",
                "price_range_low": 10.0,
                "price_range_high": 20.0,
                "priority": "High",
                "sourcing_notes": "Top-rated tactical brands",
            },
            {
                "index": 2,
                "description": "Tactical hydration reservoir",
                "price_range_low": 25.0,
                "price_range_high": 40.0,
                "priority": "Medium",
                "sourcing_notes": "Bulk packaging available",
            },
        ]
    }

    enriched = enrich_opportunities_batch(opportunities, batch_size=10)

    assert len(enriched) == 2
    assert [item["product_type"] for item in enriched] == ["Socks", "Hydration Pack"]
    assert enriched[0]["description"] == "Moisture-wicking sock pair"
    assert enriched[1]["description"] == "Tactical hydration reservoir"
    assert enriched[0]["priority"] == "High"
    assert enriched[1]["priority"] == "Medium"


@patch("easyupsell.core.opportunities.call_llm_generic")
def test_enrich_opportunities_batch_partial_match_keeps_all_rows_and_fallback_defaults(
    mock_call_llm,
):
    opportunities = _make_opportunities()
    mock_call_llm.return_value = {
        "opportunities": [
            {
                "index": 2,
                "description": "Fills hydration pack row only",
                "price_range_low": 25,
                "price_range_high": 40,
                "priority": "Low",
                "sourcing_notes": "Fallback pack source",
            },
            {"index": 3, "description": "Out of range should be ignored"},
        ]
    }

    enriched = enrich_opportunities_batch(opportunities, batch_size=10)

    assert len(enriched) == 2

    socks = next(item for item in enriched if item["product_type"] == "Socks")
    assert socks["description"] == ""
    assert socks["price_range_low"] == ""
    assert socks["price_range_high"] == ""
    assert socks["priority"] == ""
    assert socks["sourcing_notes"] == ""

    hydration = next(
        item for item in enriched if item["product_type"] == "Hydration Pack"
    )
    assert hydration["description"] == "Fills hydration pack row only"


@patch("easyupsell.core.opportunities.call_llm_generic")
def test_enrich_opportunities_batch_handles_malformed_indices_without_dropping_rows(
    mock_call_llm,
):
    opportunities = _make_opportunities() + [
        {
            "product_type": "Gloves",
            "source_categories": ["Rescue Gear"],
            "category_count": 1,
            "description": "",
            "price_range_low": "",
            "price_range_high": "",
            "priority": "",
            "sourcing_notes": "",
        }
    ]

    mock_call_llm.return_value = {
        "opportunities": [
            "not-a-dict",
            {
                "index": "2",
                "description": "Hydration from string index",
                "priority": "Low",
            },
            {"index": 99, "description": "Out of range should be ignored"},
            {"index": 1, "description": "Socks string index", "priority": "Critical"},
        ]
    }

    enriched = enrich_opportunities_batch(opportunities, batch_size=10)

    assert len(enriched) == 3

    socks = next(item for item in enriched if item["product_type"] == "Socks")
    assert socks["description"] == "Socks string index"
    assert socks["priority"] == "Unknown"

    hydration = next(
        item for item in enriched if item["product_type"] == "Hydration Pack"
    )
    assert hydration["description"] == "Hydration from string index"

    gloves = next(item for item in enriched if item["product_type"] == "Gloves")
    assert gloves["description"] == ""
    assert gloves["price_range_low"] == ""
    assert gloves["price_range_high"] == ""
    assert gloves["priority"] == ""
    assert gloves["sourcing_notes"] == ""


@patch("easyupsell.core.opportunities.call_llm_generic")
def test_enrich_opportunities_batch_exception_fallback_sets_unknown_priority(
    mock_call_llm,
):
    opportunities = _make_opportunities()
    mock_call_llm.side_effect = RuntimeError("provider down")

    enriched = enrich_opportunities_batch(opportunities, batch_size=2)

    assert len(enriched) == 2
    for row in enriched:
        assert row["priority"] == "Unknown"
        assert "LLM enrichment failed: provider down" in row["sourcing_notes"]
        assert row["description"] == ""
        assert row["price_range_low"] == ""
        assert row["price_range_high"] == ""


def test_enrich_opportunities_batch_invalid_batch_size_is_deterministic():
    opportunities = _make_opportunities()

    with pytest.raises(ValueError, match="batch_size must be a positive integer"):
        enrich_opportunities_batch(opportunities, batch_size=0)
