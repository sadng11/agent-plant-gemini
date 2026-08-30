"""Knowledge Base Loader and In-Memory Cache Manager for PhytoAgent."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, Union
import yaml

from app.models.knowledge_base import (
    GlobalPhasesModel,
    GlobalSubstratesModel,
    GlobalTraitsModel,
    PhaseModel,
    SpeciesModel,
    SubstrateModel,
    TraitModel,
)

logger = logging.getLogger(__name__)


class KnowledgeBaseError(Exception):
    """Base exception for Knowledge Base errors."""


class SpeciesNotFoundError(KnowledgeBaseError):
    """Raised when a requested plant species cannot be found in the knowledge base."""


class SubstrateNotFoundError(KnowledgeBaseError):
    """Raised when a requested substrate cannot be found in global substrates."""


class TraitNotFoundError(KnowledgeBaseError):
    """Raised when a requested trait cannot be found in global traits."""


class PhaseNotFoundError(KnowledgeBaseError):
    """Raised when a requested phase cannot be found in global phases."""


class KBValidationError(KnowledgeBaseError):
    """Raised when a knowledge base YAML fails validation."""


class KnowledgeBaseManager:
    """Manager for loading, validating, and caching plant knowledge base files.
    
    Provides thread-safe in-memory caching to avoid repetitive disk I/O.
    """

    def __init__(self, base_path: Optional[Union[str, Path]] = None) -> None:
        """Initialize KB Manager with base directory path.
        
        Args:
            base_path: Root directory containing 'species/' and 'global/' directories.
                       If None, defaults to project_root / 'knowledge_base'.
        """
        if base_path is None:
            # Auto-detect relative to project root (2 levels up from app/core/)
            project_root = Path(__file__).resolve().parent.parent.parent
            self.base_path = project_root / "knowledge_base"
        else:
            self.base_path = Path(base_path)

        self.species_dir = self.base_path / "species"
        self.global_dir = self.base_path / "global"

        # In-Memory Caches
        self._species_cache: Dict[str, SpeciesModel] = {}
        self._substrates_cache: Optional[GlobalSubstratesModel] = None
        self._traits_cache: Optional[GlobalTraitsModel] = None
        self._phases_cache: Optional[GlobalPhasesModel] = None

    def _read_yaml(self, file_path: Path) -> dict:
        """Read and parse a YAML file."""
        if not file_path.exists():
            raise FileNotFoundError(f"YAML file not found: {file_path}")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = yaml.safe_load(f)
                return content or {}
        except yaml.YAMLError as e:
            raise KBValidationError(f"Invalid YAML format in {file_path}: {e}") from e

    # =========================================================================
    # Species Operations
    # =========================================================================

    def get_species(self, species_id: str) -> Optional[SpeciesModel]:
        """Retrieve a species profile by species_id with in-memory caching.
        
        Args:
            species_id: Unique slug of the species, e.g. 'monstera_deliciosa'.
            
        Returns:
            SpeciesModel if found, or None.
        """
        if species_id in self._species_cache:
            return self._species_cache[species_id]

        file_path = self.species_dir / f"{species_id}.yaml"
        if not file_path.exists():
            return None

        try:
            data = self._read_yaml(file_path)
            model = SpeciesModel.model_validate(data)
            self._species_cache[species_id] = model
            return model
        except Exception as e:
            raise KBValidationError(f"Failed to validate species '{species_id}': {e}") from e

    def get_species_strict(self, species_id: str) -> SpeciesModel:
        """Retrieve a species profile or raise SpeciesNotFoundError."""
        species = self.get_species(species_id)
        if species is None:
            raise SpeciesNotFoundError(
                f"Species '{species_id}' not found in knowledge base at {self.species_dir}"
            )
        return species

    def list_species(self) -> List[str]:
        """List all available species IDs from filesystem and cache."""
        if not self.species_dir.exists():
            return []
        species_ids = [
            f.stem for f in self.species_dir.glob("*.yaml") if f.is_file()
        ]
        return sorted(species_ids)

    def load_all_species(self) -> Dict[str, SpeciesModel]:
        """Load and validate all species files into cache."""
        for sp_id in self.list_species():
            self.get_species_strict(sp_id)
        return self._species_cache

    # =========================================================================
    # Global Substrates Operations
    # =========================================================================

    def _ensure_substrates_loaded(self) -> GlobalSubstratesModel:
        """Load and cache global substrates."""
        if self._substrates_cache is None:
            file_path = self.global_dir / "global_substrates.yaml"
            data = self._read_yaml(file_path)
            try:
                self._substrates_cache = GlobalSubstratesModel.model_validate(data)
            except Exception as e:
                raise KBValidationError(f"Failed to validate global_substrates.yaml: {e}") from e
        return self._substrates_cache

    def get_substrate(self, substrate_id: str) -> Optional[SubstrateModel]:
        """Retrieve a substrate specification by ID.
        
        Args:
            substrate_id: e.g. 'inert_soilless', 'mineral_heavy', 'hydro_and_semi_hydro'.
        """
        substrates_model = self._ensure_substrates_loaded()
        return substrates_model.substrates.get(substrate_id)

    def get_substrate_strict(self, substrate_id: str) -> SubstrateModel:
        """Retrieve a substrate specification or raise SubstrateNotFoundError."""
        substrate = self.get_substrate(substrate_id)
        if substrate is None:
            raise SubstrateNotFoundError(f"Substrate '{substrate_id}' not found in global substrates.")
        return substrate

    def list_substrates(self) -> List[str]:
        """List all defined global substrate IDs."""
        substrates_model = self._ensure_substrates_loaded()
        return sorted(list(substrates_model.substrates.keys()))

    # =========================================================================
    # Global Traits Operations
    # =========================================================================

    def _ensure_traits_loaded(self) -> GlobalTraitsModel:
        """Load and cache global traits."""
        if self._traits_cache is None:
            file_path = self.global_dir / "global_traits.yaml"
            data = self._read_yaml(file_path)
            try:
                self._traits_cache = GlobalTraitsModel.model_validate(data)
            except Exception as e:
                raise KBValidationError(f"Failed to validate global_traits.yaml: {e}") from e
        return self._traits_cache

    def get_trait(self, trait_id: str) -> Optional[TraitModel]:
        """Retrieve a trait by ID, e.g. 'variegated_foliage'."""
        traits_model = self._ensure_traits_loaded()
        return traits_model.traits.get(trait_id)

    def get_trait_strict(self, trait_id: str) -> TraitModel:
        """Retrieve a trait or raise TraitNotFoundError."""
        trait = self.get_trait(trait_id)
        if trait is None:
            raise TraitNotFoundError(f"Trait '{trait_id}' not found in global traits.")
        return trait

    def get_traits(self, trait_ids: List[str]) -> List[TraitModel]:
        """Batch retrieve multiple traits by IDs. Ignores unknown IDs."""
        traits_model = self._ensure_traits_loaded()
        results: List[TraitModel] = []
        for tid in trait_ids:
            t = traits_model.traits.get(tid)
            if t is not None:
                results.append(t)
        return results

    def list_traits(self) -> List[str]:
        """List all defined global trait IDs."""
        traits_model = self._ensure_traits_loaded()
        return sorted(list(traits_model.traits.keys()))

    # =========================================================================
    # Global Phases Operations
    # =========================================================================

    def _ensure_phases_loaded(self) -> GlobalPhasesModel:
        """Load and cache global phases."""
        if self._phases_cache is None:
            file_path = self.global_dir / "global_phases.yaml"
            data = self._read_yaml(file_path)
            try:
                self._phases_cache = GlobalPhasesModel.model_validate(data)
            except Exception as e:
                raise KBValidationError(f"Failed to validate global_phases.yaml: {e}") from e
        return self._phases_cache

    def get_phase(self, phase_id: str) -> Optional[PhaseModel]:
        """Retrieve a growth phase by ID, e.g. 'flowering_and_fruit_set'."""
        phases_model = self._ensure_phases_loaded()
        return phases_model.phases.get(phase_id)

    def get_phase_strict(self, phase_id: str) -> PhaseModel:
        """Retrieve a phase or raise PhaseNotFoundError."""
        phase = self.get_phase(phase_id)
        if phase is None:
            raise PhaseNotFoundError(f"Phase '{phase_id}' not found in global phases.")
        return phase

    def list_phases(self) -> List[str]:
        """List all defined global phase IDs."""
        phases_model = self._ensure_phases_loaded()
        return sorted(list(phases_model.phases.keys()))

    # =========================================================================
    # Bulk & Cache Control
    # =========================================================================

    def load_all(self) -> None:
        """Preload and validate the entire knowledge base into memory."""
        self.load_all_species()
        self._ensure_substrates_loaded()
        self._ensure_traits_loaded()
        self._ensure_phases_loaded()
        logger.info(
            f"KnowledgeBaseManager loaded: {len(self._species_cache)} species, "
            f"{len(self.list_substrates())} substrates, "
            f"{len(self.list_traits())} traits, "
            f"{len(self.list_phases())} phases."
        )

    def clear_cache(self) -> None:
        """Clear all in-memory caches."""
        self._species_cache.clear()
        self._substrates_cache = None
        self._traits_cache = None
        self._phases_cache = None

    def reload(self) -> None:
        """Clear caches and reload all knowledge base data from disk."""
        self.clear_cache()
        self.load_all()


# Singleton helper instance for easy application-wide import
default_kb_manager = KnowledgeBaseManager()
