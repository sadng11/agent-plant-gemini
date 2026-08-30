"""Unit tests for PhytoAgent Knowledge Base Loader and Pydantic V2 Models."""

import pytest
from pydantic import ValidationError

from app.core.kb_loader import (
    KBValidationError,
    KnowledgeBaseManager,
    PhaseNotFoundError,
    SpeciesNotFoundError,
    SubstrateNotFoundError,
    TraitNotFoundError,
    default_kb_manager,
)
from app.models.knowledge_base import (
    CompatibilityStatus,
    HumidityToleranceModel,
    LightToleranceModel,
    SpeciesModel,
    SubstrateModel,
    TempToleranceModel,
)


@pytest.fixture
def kb_manager():
    """Create a fresh KnowledgeBaseManager instance for testing."""
    manager = KnowledgeBaseManager()
    manager.clear_cache()
    return manager


# ============================================================================
# 1. Bulk Loading and Schema Integrity Tests
# ============================================================================


def test_load_all_kb(kb_manager: KnowledgeBaseManager):
    """Ensure all YAML files in the knowledge base load without validation errors."""
    kb_manager.load_all()

    species_list = kb_manager.list_species()
    assert "monstera_deliciosa" in species_list
    assert "citrus_limon" in species_list
    assert len(species_list) >= 2

    substrates_list = kb_manager.list_substrates()
    assert "inert_soilless" in substrates_list
    assert "hydro_and_semi_hydro" in substrates_list
    assert "mineral_heavy" in substrates_list
    assert len(substrates_list) >= 3

    traits_list = kb_manager.list_traits()
    assert "variegated_foliage" in traits_list
    assert len(traits_list) >= 1

    phases_list = kb_manager.list_phases()
    assert "flowering_and_fruit_set" in phases_list
    assert "active_vegetative" in phases_list
    assert len(phases_list) >= 2


# ============================================================================
# 2. Species Verification Tests
# ============================================================================


def test_monstera_deliciosa_profile(kb_manager: KnowledgeBaseManager):
    """Verify Monstera deliciosa parsed parameters."""
    monstera = kb_manager.get_species_strict("monstera_deliciosa")

    # Botanical Info
    assert monstera.species_id == "monstera_deliciosa"
    assert monstera.botanical_info.scientific_name == "Monstera deliciosa"
    assert monstera.botanical_info.family == "Araceae"
    assert "برگ‌انجیری" in monstera.botanical_info.persian_name

    # Tolerances
    assert monstera.tolerances.light_lux.min == 1500
    assert monstera.tolerances.light_lux.optimal_min == 2500
    assert monstera.tolerances.light_lux.optimal_max == 5000
    assert monstera.tolerances.humidity_pct.min == 40
    assert monstera.tolerances.humidity_pct.optimal == 65
    assert monstera.tolerances.temp_celsius.min == 16
    assert monstera.tolerances.temp_celsius.optimal == 24
    assert monstera.tolerances.temp_celsius.max == 30

    # Base Feeding
    assert "3-1-2" in monstera.base_feeding.default_npk_ratio
    assert monstera.base_feeding.standard_dose_ec == 1.2
    assert monstera.base_feeding.base_frequency_days == 14
    assert monstera.base_feeding.sensitive_to_chlorine is True

    # Substrate Requirements & Risk Triage
    sub_rules = monstera.substrate_requirements.compatibility_rules
    assert "mineral_heavy" in sub_rules
    assert sub_rules["mineral_heavy"].status == CompatibilityStatus.DANGEROUS
    assert "خفگی ریشه" in sub_rules["mineral_heavy"].alert_message
    assert sub_rules["inert_soilless"].status == CompatibilityStatus.ACCEPTABLE
    assert sub_rules["aroid_chunky_mix"].status == CompatibilityStatus.IDEAL

    # Phenology Constraints
    assert "fruiting_and_flowering" in monstera.phenology_constraints
    fc = monstera.phenology_constraints["fruiting_and_flowering"]
    assert fc.indoor_feasibility == "extremely_rare"
    assert fc.is_fertilizer_driven_only is False
    assert fc.mandatory_prerequisites.plant_maturity_years == 5
    assert fc.mandatory_prerequisites.minimum_climbing_height_meters == 3


def test_citrus_limon_profile(kb_manager: KnowledgeBaseManager):
    """Verify Citrus limon parsed parameters."""
    citrus = kb_manager.get_species_strict("citrus_limon")

    assert citrus.species_id == "citrus_limon"
    assert citrus.botanical_info.scientific_name == "Citrus limon"
    assert citrus.botanical_info.family == "Rutaceae"
    assert "لیمو" in citrus.botanical_info.persian_name

    # High light requirements for citrus
    assert citrus.tolerances.light_lux.min >= 4000
    assert citrus.tolerances.light_lux.optimal_max >= 15000

    # Feeding
    assert citrus.base_feeding.standard_dose_ec == 1.6
    assert citrus.base_feeding.base_frequency_days == 10

    # Compatibility
    sub_rules = citrus.substrate_requirements.compatibility_rules
    assert sub_rules["mineral_heavy"].status == CompatibilityStatus.DANGEROUS
    assert "کلروز" in sub_rules["mineral_heavy"].alert_message or "فیتوفتورا" in sub_rules["mineral_heavy"].alert_message


# ============================================================================
# 3. Global Substrates Tests
# ============================================================================


def test_global_substrates(kb_manager: KnowledgeBaseManager):
    """Verify global substrate profiles."""
    inert = kb_manager.get_substrate_strict("inert_soilless")
    assert inert.dose_multiplier == 0.7
    assert inert.interval_multiplier == 0.8
    assert inert.target_ph_range == [5.8, 6.3]
    assert any(s.id == "cal_mag" for s in inert.mandatory_supplements)

    hydro = kb_manager.get_substrate_strict("hydro_and_semi_hydro")
    assert hydro.is_liquid_system is True
    assert hydro.dose_multiplier == 0.6
    assert hydro.target_ph_range == [5.5, 6.2]
    assert any(s.id == "hydro_micro" for s in hydro.mandatory_supplements)

    clay = kb_manager.get_substrate_strict("mineral_heavy")
    assert clay.dose_multiplier == 0.5
    assert clay.interval_multiplier == 1.6
    assert clay.target_ph_range == [6.5, 7.5]
    assert any(s.id == "humic_acid" for s in clay.mandatory_supplements)


# ============================================================================
# 4. Global Traits Tests
# ============================================================================


def test_global_traits(kb_manager: KnowledgeBaseManager):
    """Verify global traits rules."""
    variegated = kb_manager.get_trait_strict("variegated_foliage")
    assert variegated.fertilizer_rules.max_nitrogen_cap_pct == 10.0
    assert "10-10-30" in variegated.fertilizer_rules.override_npk_ratio
    assert "اوره" in variegated.fertilizer_rules.banned_fertilizers
    assert any(s.id == "potassium_silicate" for s in variegated.fertilizer_rules.mandatory_supplements)
    assert variegated.environmental_adjustments.light_intensity_multiplier == 1.3
    assert variegated.environmental_adjustments.prohibit_foliar_spray is True

    # Test batch lookup
    batch = kb_manager.get_traits(["variegated_foliage", "non_existent_trait"])
    assert len(batch) == 1
    assert batch[0].label == variegated.label


# ============================================================================
# 5. Global Phases Tests
# ============================================================================


def test_global_phases(kb_manager: KnowledgeBaseManager):
    """Verify phenological growth phases."""
    flowering = kb_manager.get_phase_strict("flowering_and_fruit_set")
    assert flowering.fertilizer_rules.suppress_high_nitrogen is True
    assert "52" in flowering.fertilizer_rules.override_npk_ratio
    assert any(s.id == "fruit_set_combo" for s in flowering.fertilizer_rules.mandatory_supplements)
    assert flowering.watering_rules.stability_mode is True

    veg = kb_manager.get_phase_strict("active_vegetative")
    assert veg.fertilizer_rules.allow_high_nitrogen is True
    assert "20-20-20" in veg.fertilizer_rules.recommended_ratio


# ============================================================================
# 6. Caching and In-Memory Behavior Tests
# ============================================================================


def test_caching_mechanism(kb_manager: KnowledgeBaseManager):
    """Verify in-memory caching reuses parsed models without disk re-reading."""
    # First access loads from disk
    m1 = kb_manager.get_species("monstera_deliciosa")
    # Second access must return identical cached object reference
    m2 = kb_manager.get_species("monstera_deliciosa")
    assert m1 is m2

    # Global substrates caching
    s1 = kb_manager.get_substrate("inert_soilless")
    s2 = kb_manager.get_substrate("inert_soilless")
    assert s1 is s2

    # Clear cache test
    kb_manager.clear_cache()
    m3 = kb_manager.get_species("monstera_deliciosa")
    assert m3 is not None
    assert m3 is not m1  # New instance parsed after cache clear
    assert m3.species_id == m1.species_id


# ============================================================================
# 7. Error Handling & Edge Cases Tests
# ============================================================================


def test_missing_entities(kb_manager: KnowledgeBaseManager):
    """Verify behavior on non-existent entities."""
    assert kb_manager.get_species("unknown_plant_xyz") is None
    with pytest.raises(SpeciesNotFoundError):
        kb_manager.get_species_strict("unknown_plant_xyz")

    assert kb_manager.get_substrate("unknown_sub") is None
    with pytest.raises(SubstrateNotFoundError):
        kb_manager.get_substrate_strict("unknown_sub")

    assert kb_manager.get_trait("unknown_trait") is None
    with pytest.raises(TraitNotFoundError):
        kb_manager.get_trait_strict("unknown_trait")

    assert kb_manager.get_phase("unknown_phase") is None
    with pytest.raises(PhaseNotFoundError):
        kb_manager.get_phase_strict("unknown_phase")


# ============================================================================
# 8. Pydantic Model Strict Validation Tests
# ============================================================================


def test_light_tolerance_validation():
    """Verify LightToleranceModel validators."""
    # Valid
    lt = LightToleranceModel(min=1000, optimal_min=2000, optimal_max=4000)
    assert lt.min == 1000

    # optimal_min < min -> ValueError
    with pytest.raises(ValidationError):
        LightToleranceModel(min=3000, optimal_min=2000, optimal_max=4000)

    # optimal_max < optimal_min -> ValueError
    with pytest.raises(ValidationError):
        LightToleranceModel(min=1000, optimal_min=4000, optimal_max=3000)


def test_humidity_tolerance_validation():
    """Verify HumidityToleranceModel validators."""
    # optimal > 100 -> ValidationError
    with pytest.raises(ValidationError):
        HumidityToleranceModel(min=40, optimal=110)

    # optimal < min -> ValidationError
    with pytest.raises(ValidationError):
        HumidityToleranceModel(min=70, optimal=50)


def test_temp_tolerance_validation():
    """Verify TempToleranceModel validators."""
    # optimal < min -> ValidationError
    with pytest.raises(ValidationError):
        TempToleranceModel(min=20, optimal=15, max=30)

    # max < optimal -> ValidationError
    with pytest.raises(ValidationError):
        TempToleranceModel(min=15, optimal=25, max=20)


def test_substrate_ph_validation():
    """Verify SubstrateModel target_ph_range validators."""
    # Invalid length
    with pytest.raises(ValidationError):
        SubstrateModel(label="Test", target_ph_range=[6.0])

    # Min pH > Max pH
    with pytest.raises(ValidationError):
        SubstrateModel(label="Test", target_ph_range=[7.0, 5.5])

    # pH out of [0, 14]
    with pytest.raises(ValidationError):
        SubstrateModel(label="Test", target_ph_range=[-1.0, 7.0])
