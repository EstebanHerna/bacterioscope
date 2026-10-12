"""Tests for provenance-preserving Ed33 labels derived from UZH zone rows."""

from bacterioscope.evaluation.derived_clsi_reference import (
    derive_uzh_clsi_reference_rows,
)


def test_derives_category_and_preserves_original_eucast_category() -> None:
    rows = derive_uzh_clsi_reference_rows(
        [{
            "source": "synthetic UZH fixture",
            "image_filename": "isolate-1.jpg",
            "antibiotic_code": "CIP",
            "antibiotic_name": "Ciprofloxacin",
            "zone_diameter_mm_ref": "26",
            "category_ref": "R",
            "standard": "EUCAST",
        }],
        [{"image_join_key": "isolate-1", "organism": "Escherichia coli"}],
    )

    assert len(rows) == 1
    assert rows[0]["source_category_eucast"] == "R"
    assert rows[0]["derived_category_clsi_ed33"] == "S"
    assert rows[0]["derivation_status"] == "derived_analytical_label"
    assert rows[0]["independent_ground_truth"] == "false"


def test_matches_uzh_original_image_suffix_to_isolate_label() -> None:
    rows = derive_uzh_clsi_reference_rows(
        [{
            "image_filename": "7.17.1 original.jpg",
            "antibiotic_code": "CIP",
            "zone_diameter_mm_ref": "26",
        }],
        [{"image_join_key": "7.17.1", "organism": "E. coli"}],
    )

    assert rows[0]["image_join_key"] == "7.17.1"
    assert rows[0]["organism"] == "E. coli"
    assert rows[0]["derived_category_clsi_ed33"] == "S"


def test_excludes_disk_content_mismatch_without_dropping_source_row() -> None:
    rows = derive_uzh_clsi_reference_rows(
        [
            {"image_filename": "isolate-1.jpg", "antibiotic_code": "CAZ",
             "zone_diameter_mm_ref": "24", "category_ref": "S", "standard": "EUCAST"},
            {"image_filename": "isolate-1.jpg", "antibiotic_code": "TPZ",
             "zone_diameter_mm_ref": "24", "category_ref": "S", "standard": "EUCAST"},
        ],
        [{"image_join_key": "isolate-1", "organism": "Escherichia coli"}],
    )

    assert len(rows) == 2
    assert all(row["derivation_status"] == "excluded" for row in rows)
    assert all(row["exclusion_reason"] == "eucast_and_clsi_disk_contents_differ" for row in rows)
    assert rows[0]["source_eucast_disk_content_ug"] == "10"
    assert rows[0]["clsi_ed33_disk_content_ug"] == "30"
    assert rows[1]["source_eucast_disk_content_ug"] == "30/6"
    assert rows[1]["clsi_ed33_disk_content_ug"] == "100/10"


def test_excludes_non_enterobacterales_and_unmapped_antibiotics() -> None:
    rows = derive_uzh_clsi_reference_rows(
        [
            {"image_filename": "acinetobacter.jpg", "antibiotic_code": "CIP",
             "zone_diameter_mm_ref": "24"},
            {"image_filename": "ecoli.jpg", "antibiotic_code": "FOX",
             "zone_diameter_mm_ref": "24"},
        ],
        [
            {"image_join_key": "acinetobacter", "organism": "Acinetobacter baumannii"},
            {"image_join_key": "ecoli", "organism": "E. coli"},
        ],
    )

    assert rows[0]["exclusion_reason"] == "organism_outside_classifier_group"
    assert rows[1]["exclusion_reason"] == "antibiotic_code_not_in_classifier_scope"
    assert not any(row["derived_category_clsi_ed33"] for row in rows)


def test_excludes_ambiguous_organism_join_and_invalid_zone() -> None:
    rows = derive_uzh_clsi_reference_rows(
        [
            {"image_filename": "ambiguous.jpg", "antibiotic_code": "CIP",
             "zone_diameter_mm_ref": "24"},
            {"image_filename": "bad-zone.jpg", "antibiotic_code": "CIP",
             "zone_diameter_mm_ref": "nan"},
        ],
        [
            {"image_join_key": "ambiguous", "organism": "E. coli"},
            {"image_join_key": "ambiguous", "organism": "Klebsiella pneumoniae"},
            {"image_join_key": "bad-zone", "organism": "E. coli"},
        ],
    )

    assert rows[0]["exclusion_reason"] == "ambiguous_organism_for_image"
    assert rows[1]["exclusion_reason"] == "classifier_returned_unknown"
