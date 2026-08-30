"""Unit tests for PhytoAgent AgronomyEngine (Botanical calculations & rules)."""

import pytest

from app.core.agronomy_engine import AgronomyEngine
from app.core.kb_loader import KnowledgeBaseManager


@pytest.fixture
def kb():
    manager = KnowledgeBaseManager()
    manager.load_all()
    return manager


# ============================================================================
# 1. Substrate Risk Triage Tests
# ============================================================================


def test_monstera_heavy_clay_is_critical_blocker(kb: KnowledgeBaseManager):
    """Monstera in mineral heavy soil must trigger a critical blocker warning."""
    monstera = kb.get_species("monstera_deliciosa")
    risk_level, msg = AgronomyEngine.evaluate_substrate_risk(monstera, "mineral_heavy")

    assert risk_level == "CRITICAL_BLOCKER"
    assert msg is not None
    assert "پوسیدگی" in msg or "خفگی ریشه" in msg
    assert "تعویض" in msg


def test_monstera_soilless_is_sub_optimal(kb: KnowledgeBaseManager):
    """Monstera in inert soilless substrate is acceptable with supplements."""
    monstera = kb.get_species("monstera_deliciosa")
    risk_level, msg = AgronomyEngine.evaluate_substrate_risk(monstera, "inert_soilless")

    assert risk_level == "SUB_OPTIMAL"
    assert msg is not None
    assert "Cal-Mag" in msg


def test_monstera_aroid_mix_is_optimal(kb: KnowledgeBaseManager):
    """Monstera in chunky aroid mix is ideal."""
    monstera = kb.get_species("monstera_deliciosa")
    risk_level, msg = AgronomyEngine.evaluate_substrate_risk(monstera, "aroid_chunky_mix")

    assert risk_level == "OPTIMAL"
    assert msg is not None


# ============================================================================
# 2. Biological Goal Feasibility Tests
# ============================================================================


def test_monstera_indoor_flowering_is_unrealistic(kb: KnowledgeBaseManager):
    """Requesting Monstera indoor flowering must explain botanical prerequisites and warn against fertilizer."""
    monstera = kb.get_species("monstera_deliciosa")
    feasible, msg = AgronomyEngine.check_goal_feasibility(monstera, "induce_flowering")

    assert feasible is False
    assert msg is not None
    assert "سن بلوغ" in msg
    assert "قیم" in msg or "ارتفاع" in msg
    assert "فسفر" in msg or "مسمومیت" in msg


def test_citrus_flowering_is_feasible(kb: KnowledgeBaseManager):
    """Citrus flowering is generally feasible without extreme phenology blockers."""
    citrus = kb.get_species("citrus_limon")
    feasible, msg = AgronomyEngine.check_goal_feasibility(citrus, "flowering_and_fruit_set")

    assert feasible is True
    assert msg is None


# ============================================================================
# 3. 4-Week Schedule Generation Tests
# ============================================================================


def test_variegated_monstera_in_soilless_schedule(kb: KnowledgeBaseManager):
    """
    Variegated Monstera in Coco Coir (inert_soilless):
    - High Potassium NPK ratio (10-10-30 / 12-12-36)
    - Prohibit Urea / 30-10-10
    - Mandate Cal-Mag and Potassium Silicate
    - Dose multiplier 0.7x
    """
    monstera = kb.get_species("monstera_deliciosa")
    soilless = kb.get_substrate("inert_soilless")
    variegated = kb.get_trait("variegated_foliage")

    schedule = AgronomyEngine.generate_4week_schedule(
        species=monstera,
        substrate=soilless,
        traits=[variegated],
        phase=None,
    )

    assert "10-10-30" in schedule["applied_npk_ratio"] or "12-12-36" in schedule["applied_npk_ratio"]
    assert schedule["dose_multiplier"] == 0.7
    assert schedule["effective_dose_ec"] == round(1.2 * 0.7, 2)
    assert schedule["target_ph_range"] == [5.8, 6.3]

    # Banned fertilizers
    banned = schedule["banned_fertilizers"]
    assert any("30-10-10" in b for b in banned)
    assert any("اوره" in b for b in banned)

    # Mandatory supplements
    supp_ids = {s["id"] for s in schedule["mandatory_supplements"]}
    assert "cal_mag" in supp_ids
    assert "potassium_silicate" in supp_ids

    # 4 Weeks presence
    weeks = schedule["weeks"]
    assert len(weeks) == 4
    assert weeks[0]["week_num"] == 1
    assert weeks[3]["week_num"] == 4
    assert "فلاش" in weeks[3]["action"] or "آبشویی" in weeks[3]["action"]


def test_citrus_flowering_phase_schedule(kb: KnowledgeBaseManager):
    """
    Citrus Limon in flowering phase:
    - High Phosphorus NPK (10-52-10 or 0-52-34)
    - Suppress high nitrogen
    - Mandate fruit-set combo
    """
    citrus = kb.get_species("citrus_limon")
    soilless = kb.get_substrate("inert_soilless")
    flowering = kb.get_phase("flowering_and_fruit_set")

    schedule = AgronomyEngine.generate_4week_schedule(
        species=citrus,
        substrate=soilless,
        traits=[],
        phase=flowering,
    )

    assert "52" in schedule["applied_npk_ratio"]
    assert any("نیتروژن بالا" in b for b in schedule["banned_fertilizers"])
    supp_ids = {s["id"] for s in schedule["mandatory_supplements"]}
    assert "fruit_set_combo" in supp_ids
