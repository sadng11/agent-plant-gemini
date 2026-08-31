import asyncio
import json
import logging
import re
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple
from langgraph.graph import END, START, StateGraph
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential

from app.core.agronomy_engine import AgronomyEngine
from app.core.kb_loader import KnowledgeBaseManager, default_kb_manager
from app.models.agent_state import ExtractedPlantEntities, PlantCareState
from app.models.knowledge_base import PhaseModel, SpeciesModel, SubstrateModel, TraitModel
from app.services.digital_twin_service import DigitalTwinService
from app.services.extractor_service import EntityExtractorService

logger = logging.getLogger(__name__)

SYNTHESIS_SYSTEM_PROMPT = """
شما «فیتو» (PhytoAgent) هستید؛ یک مشاور و متخصص ارشد گیاه‌پزشکی، باغبانی و اگرونومی علمی.
وظیفه شما این است که بر اساس آخرین وضعیت تحلیلی گیاه، پیامی جذاب، همدلانه، صمیمی، پویا و کاملاً علمی و شیوا به زبان فارسی برای کاربر بنویسید.

قوانین کلیدی شما:
۱. از جملات قالبی، خشک و کلیشه‌ای پرهیز کنید و متناسب با صحبت کاربر به صورت کاملاً طبیعی، هوشمند و صمیمی پاسخ دهید.
۲. ایمنی زیستی و سلامت گیاه اولویت مطلق است: در صورت وجود هرگونه آفت، بیماری یا بستر نامناسب، بر توقف فوری کوددهی شیمیایی تاکید کنید و علت علمی (مانند مسمومیت اسمزی و سوختگی ریشه‌ها) و راه‌حل درمانی/اصلاحی را با دلسوزی بیان کنید.
۳. در صورتی که برنامه کودی یا راهنمای شرایط نگهداری صادر شده، از داده‌های ارائه‌شده (NPK، EC، لوکس نور، رطوبت، دوره آبیاری) دقیقاً استفاده کرده و آن را با ساختاربندی خوانا و شکیل Markdown (شامل ایموجی‌های مناسب و بولت‌پوینت) بنویسید.
""".strip()


class PlantDiagnosticGraph:
    """
    Orchestrates the LangGraph multi-stage botanical diagnostic workflow.
    Adheres to clinical plant-pathology and validation gates:
    Gate 1: Species & Substrate verification.
    Gate 2: Trait Disambiguation (e.g. variegated foliage vs plain green for Monstera).
    Gate 3: Health Confirmation Gate (ensuring no pests, root rot, or chlorosis before fertilizing).
    Gate 4: Substrate Risk Triage (blocking dangerous substrates like heavy clay).
    """

    def __init__(
        self,
        kb_manager: Optional[KnowledgeBaseManager] = None,
        extractor: Optional[EntityExtractorService] = None,
        digital_twin_service: Optional[DigitalTwinService] = None,
    ):
        self.kb = kb_manager or default_kb_manager
        self.extractor = extractor or EntityExtractorService()
        self.digital_twin_service = digital_twin_service
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(PlantCareState)

        # Add Nodes
        workflow.add_node("extract_and_resolve", self.node_extract_and_resolve)
        workflow.add_node("sync_digital_twin", self.node_sync_digital_twin)
        workflow.add_node("risk_triage", self.node_risk_triage)
        workflow.add_node("goal_feasibility", self.node_goal_feasibility)
        workflow.add_node("compute_schedule", self.node_compute_schedule)
        workflow.add_node("synthesize_response", self.node_synthesize_response)

        # Connect Edges
        workflow.add_edge(START, "extract_and_resolve")
        workflow.add_edge("extract_and_resolve", "sync_digital_twin")
        workflow.add_edge("sync_digital_twin", "risk_triage")
        workflow.add_edge("risk_triage", "goal_feasibility")

        # Conditional Edge after Goal Feasibility
        workflow.add_conditional_edges(
            "goal_feasibility",
            self.route_after_feasibility,
            {
                "blocked_or_clarification": "synthesize_response",
                "proceed_schedule": "compute_schedule",
            },
        )

        workflow.add_edge("compute_schedule", "synthesize_response")
        workflow.add_edge("synthesize_response", END)

        return workflow.compile()

    # =========================================================================
    # Conditional Routing Logic
    # =========================================================================

    @staticmethod
    def route_after_feasibility(state: PlantCareState) -> str:
        """Route to synthesis if blocked by substrate risk, pathology, pending gate slots, or non-feeding intent."""
        risk_level = state.get("risk_level")
        user_intent = state.get("user_intent") or state.get("intent") or "UNSPECIFIED"
        health_status = state.get("health_status", "UNKNOWN")
        health_confirmed = state.get("health_confirmed")
        missing_slots = state.get("missing_slots", [])
        species_id = state.get("resolved_species_id")
        substrate_id = state.get("resolved_substrate_id")

        if not species_id or "species" in missing_slots:
            return "blocked_or_clarification"

        if not substrate_id or "substrate" in missing_slots:
            return "blocked_or_clarification"

        if "trait_disambiguation" in missing_slots:
            return "blocked_or_clarification"

        if user_intent != "FEEDING_CARE":
            return "blocked_or_clarification"

        if "health_verification" in missing_slots or health_confirmed is not True:
            return "blocked_or_clarification"

        if risk_level == "CRITICAL_BLOCKER":
            return "blocked_or_clarification"

        if health_status == "SICK_OR_SYMPTOMATIC" or health_confirmed is False or user_intent == "DIAGNOSIS_SYMPTOM":
            return "blocked_or_clarification"

        return "proceed_schedule"

    # =========================================================================
    # Node 1: Extract and Resolve Entities
    # =========================================================================

    async def node_extract_and_resolve(self, state: PlantCareState) -> Dict[str, Any]:
        user_message = state.get("user_message", "")
        msg_lower = user_message.lower()

        # 1. Extract entities using Extractor Service for incoming message
        new_extracted_obj = await self.extractor.extract_entities_from_message(user_message)

        # 2. Resolve IDs from new extraction
        new_species = self.extractor.resolve_species_id(new_extracted_obj.species_query)
        new_substrate = self.extractor.resolve_substrate_id(new_extracted_obj.substrate_query)
        new_traits = self.extractor.resolve_trait_ids(new_extracted_obj.traits_queries)
        new_phase = self.extractor.resolve_phase_id(new_extracted_obj.phase_query)

        # 3. Incremental State Merge
        species_id = new_species or state.get("resolved_species_id")
        substrate_id = new_substrate or state.get("resolved_substrate_id")

        # Trait confirmation handling
        plain_green_patterns = ["سبز ساده", "سبز معمولی", "سبز یکدست", "سبزه", "سبز است", "ابلق نیست", "ساده است", "معمولی است", "plain green"]
        variegated_patterns = ["ابلق", "واریگیتد", "سفید سبز", "دورنگ", "دو رنگ", "variegated"]

        prev_trait_confirmed = state.get("trait_confirmed")
        if any(v in msg_lower for v in variegated_patterns):
            trait_confirmed = True
        elif any(p in msg_lower for p in plain_green_patterns):
            trait_confirmed = False
        elif new_extracted_obj.trait_confirmed is not None:
            trait_confirmed = new_extracted_obj.trait_confirmed
        else:
            trait_confirmed = prev_trait_confirmed

        prev_traits = state.get("resolved_trait_ids") or []
        if trait_confirmed is False:
            trait_ids = [t for t in prev_traits if t != "variegated_foliage"]
        elif trait_confirmed is True or "variegated_foliage" in new_traits:
            trait_ids = list(dict.fromkeys(prev_traits + ["variegated_foliage"]))
            trait_confirmed = True
        else:
            trait_ids = prev_traits

        phase_id = new_phase or state.get("resolved_phase_id")

        # Health confirmation handling
        healthy_patterns = [
            "کاملا سالم", "کاملاً سالم", "سالم است", "سالمه", "مشکلی نداره",
            "مشکل نداره", "بدون آفت", "آفت نداره", "بیماری نداره",
            "هیچ علائمی نداره", "سرحاله", "سرحال است", "عالیه", "بدون مشکل",
            "healthy", "no pests"
        ]

        prev_health_confirmed = state.get("health_confirmed")
        prev_symptoms = state.get("reported_symptoms") or []
        reported_symptoms = list(dict.fromkeys(prev_symptoms + (new_extracted_obj.reported_symptoms or [])))

        if new_extracted_obj.health_status == "SICK_OR_SYMPTOMATIC" or reported_symptoms or new_extracted_obj.health_confirmed is False:
            health_confirmed = False
            health_status = "SICK_OR_SYMPTOMATIC"
        elif any(h in msg_lower for h in healthy_patterns):
            health_confirmed = True
            health_status = "HEALTHY"
        elif prev_health_confirmed is not None:
            health_confirmed = prev_health_confirmed
            health_status = state.get("health_status") or ("HEALTHY" if health_confirmed else "UNKNOWN")
        else:
            health_confirmed = None
            health_status = "UNKNOWN"

        # Intent resolution
        new_intent = new_extracted_obj.user_intent or new_extracted_obj.intent or "UNSPECIFIED"
        prev_intent = state.get("user_intent") or state.get("intent")

        if health_status == "SICK_OR_SYMPTOMATIC" or reported_symptoms or new_intent == "DIAGNOSIS_SYMPTOM":
            user_intent = "DIAGNOSIS_SYMPTOM"
        elif any(term in msg_lower for term in ["کود", "کوددهی", "برنامه کودی", "تغذیه", "تقویت", "npk", "feeding", "fertilizer", "دوز کودی"]):
            user_intent = "FEEDING_CARE"
        elif any(term in msg_lower for term in ["آبیاری", "نور", "لوکس", "رطوبت", "دما", "نگهداری", "شرایط نگهداری", "تعویض گلدان", "تعویض خاک", "repotting"]):
            user_intent = "GENERAL_CARE"
        elif new_intent in ["FEEDING_CARE", "GENERAL_CARE"]:
            user_intent = new_intent
        elif new_intent == "UNSPECIFIED":
            if prev_intent and prev_intent not in ["UNSPECIFIED", "GENERAL_INTRO"]:
                user_intent = prev_intent
            else:
                user_intent = "UNSPECIFIED"
        else:
            user_intent = prev_intent or "UNSPECIFIED"

        intent = user_intent

        # Resolve user goal with fallback
        prev_extracted = state.get("extracted_entities") or {}
        user_goal = new_extracted_obj.user_goal or prev_extracted.get("user_goal")
        if not user_goal and user_message:
            msg_lower = user_message.lower()
            if any(term in msg_lower for term in ["گل بده", "گلدهی", "میوه", "شکوفه", "flowering", "fruit", "باردهی", "میوه بیاره"]):
                user_goal = "induce_flowering"
            elif any(term in msg_lower for term in ["تعویض گلدان", "تعویض خاک", "repotting", "repot"]):
                user_goal = "repotting"

        # Merge raw extraction dictionaries for history
        merged_extracted = {
            "species_query": new_extracted_obj.species_query or prev_extracted.get("species_query"),
            "substrate_query": new_extracted_obj.substrate_query or prev_extracted.get("substrate_query"),
            "traits_queries": list(dict.fromkeys((prev_extracted.get("traits_queries") or []) + (new_extracted_obj.traits_queries or []))),
            "phase_query": new_extracted_obj.phase_query or prev_extracted.get("phase_query"),
            "user_goal": user_goal,
            "user_intent": user_intent,
            "intent": intent,
            "health_status": health_status,
            "health_confirmed": health_confirmed,
            "trait_confirmed": trait_confirmed,
            "reported_symptoms": reported_symptoms,
            "missing_critical_info": [],
        }

        # 4. Multi-Stage Clinical Gate Slot Filling
        missing_slots: List[str] = []

        if not species_id:
            missing_slots.append("species")
        elif not substrate_id:
            # Gate 1b: Substrate
            missing_slots.append("substrate")
        elif species_id == "monstera_deliciosa" and trait_confirmed is None:
            # Gate 2: Trait Disambiguation (For Monstera when trait is not yet confirmed)
            missing_slots.append("trait_disambiguation")
        elif user_intent == "DIAGNOSIS_SYMPTOM" or health_status == "SICK_OR_SYMPTOMATIC" or health_confirmed is False:
            # Sick plant needs pathology triage, no further feeding slot needed
            missing_slots = []
        elif user_intent == "GENERAL_CARE":
            # General care info requested, no further slot needed
            missing_slots = []
        elif user_intent == "UNSPECIFIED":
            # All basic parameters known, but user hasn't specified what help they need!
            missing_slots.append("user_intent")
        elif user_intent == "FEEDING_CARE":
            # Gate 3: Health Verification (Must confirm health before feeding schedule)
            if health_confirmed is not True:
                missing_slots.append("health_verification")

        merged_extracted["missing_critical_info"] = missing_slots

        # 5. Fetch Knowledge Base records if resolved
        species_data: Optional[Dict[str, Any]] = (
            state.get("species_data") if (species_id == state.get("resolved_species_id") and state.get("species_data")) else None
        )
        substrate_data: Optional[Dict[str, Any]] = (
            state.get("substrate_data") if (substrate_id == state.get("resolved_substrate_id") and state.get("substrate_data")) else None
        )
        traits_data: List[Dict[str, Any]] = list(state.get("traits_data") or [])
        phase_data: Optional[Dict[str, Any]] = (
            state.get("phase_data") if (phase_id == state.get("resolved_phase_id") and state.get("phase_data")) else None
        )

        if species_id and not species_data:
            try:
                sp_model = self.kb.get_species(species_id)
                species_data = sp_model.model_dump()
            except Exception as exc:
                logger.warning(f"Could not load species {species_id}: {exc}")
                if "species" not in missing_slots:
                    missing_slots.append("species")

        if substrate_id and not substrate_data:
            try:
                sub_model = self.kb.get_substrate(substrate_id)
                substrate_data = sub_model.model_dump()
            except Exception as exc:
                logger.warning(f"Could not load substrate {substrate_id}: {exc}")
                if "substrate" not in missing_slots:
                    missing_slots.append("substrate")

        # Re-sync traits_data list based on trait_ids
        if trait_ids:
            traits_data = []
            for t_id in trait_ids:
                try:
                    t_model = self.kb.get_trait(t_id)
                    traits_data.append(t_model.model_dump())
                except Exception as exc:
                    logger.warning(f"Could not load trait {t_id}: {exc}")
        elif trait_confirmed is False:
            traits_data = []

        if phase_id and not phase_data:
            try:
                ph_model = self.kb.get_phase(phase_id)
                phase_data = ph_model.model_dump()
            except Exception as exc:
                logger.warning(f"Could not load phase {phase_id}: {exc}")

        return {
            "extracted_entities": merged_extracted,
            "user_intent": user_intent,
            "intent": intent,
            "health_status": health_status,
            "health_confirmed": health_confirmed,
            "trait_confirmed": trait_confirmed,
            "reported_symptoms": reported_symptoms,
            "resolved_species_id": species_id,
            "resolved_substrate_id": substrate_id,
            "resolved_trait_ids": trait_ids,
            "resolved_phase_id": phase_id,
            "species_data": species_data,
            "substrate_data": substrate_data,
            "traits_data": traits_data,
            "phase_data": phase_data,
            "missing_slots": missing_slots,
        }

    # =========================================================================
    # Node 2: Sync Digital Twin (Database)
    # =========================================================================

    async def node_sync_digital_twin(self, state: PlantCareState) -> Dict[str, Any]:
        plant_id = state.get("plant_id")
        user_id = state.get("user_id")

        if not self.digital_twin_service:
            return {}

        try:
            species_id = state.get("resolved_species_id")
            substrate_id = state.get("resolved_substrate_id")
            trait_ids = state.get("resolved_trait_ids") or []
            phase_id = state.get("resolved_phase_id")
            health_status = state.get("health_status")
            health_confirmed = state.get("health_confirmed")
            trait_confirmed = state.get("trait_confirmed")

            species_data = state.get("species_data")
            substrate_data = state.get("substrate_data")
            traits_data = list(state.get("traits_data", []))
            phase_data = state.get("phase_data")

            # Load KB data if needed
            if species_id and not species_data:
                try:
                    species_data = self.kb.get_species(species_id).model_dump()
                except Exception as exc:
                    logger.warning(f"Could not load species {species_id}: {exc}")

            if substrate_id and not substrate_data:
                try:
                    substrate_data = self.kb.get_substrate(substrate_id).model_dump()
                except Exception as exc:
                    logger.warning(f"Could not load substrate {substrate_id}: {exc}")

            if trait_ids and not traits_data:
                for t_id in trait_ids:
                    try:
                        traits_data.append(self.kb.get_trait(t_id).model_dump())
                    except Exception as exc:
                        logger.warning(f"Could not load trait {t_id}: {exc}")

            if phase_id and not phase_data:
                try:
                    phase_data = self.kb.get_phase(phase_id).model_dump()
                except Exception as exc:
                    logger.warning(f"Could not load phase {phase_id}: {exc}")

            if health_confirmed is None and (not health_status or health_status == "UNKNOWN"):
                health_status = "HEALTHY"
                health_confirmed = True

            if trait_confirmed is None:
                trait_confirmed = bool(trait_ids)

            # Case 1: Existing plant in DB -> sync updates
            if plant_id:
                plant = await self.digital_twin_service.get_plant_by_id(plant_id, user_id=user_id)
                if plant:
                    updates: Dict[str, Any] = {}
                    species_id = species_id or plant.species_id
                    substrate_id = substrate_id or plant.substrate_type
                    trait_ids = trait_ids or (list(plant.traits) if plant.traits else [])
                    phase_id = phase_id or plant.current_phase

                    if state.get("resolved_substrate_id") and state["resolved_substrate_id"] != plant.substrate_type:
                        updates["substrate_type"] = state["resolved_substrate_id"]
                    if state.get("resolved_phase_id") and state["resolved_phase_id"] != plant.current_phase:
                        updates["current_phase"] = state["resolved_phase_id"]
                    if trait_ids and trait_ids != (list(plant.traits) if plant.traits else []):
                        updates["traits"] = trait_ids
                    if health_status and health_status != plant.health_status and health_status != "UNKNOWN":
                        updates["health_status"] = health_status

                    if updates:
                        await self.digital_twin_service.update_plant_state(plant.id, updates)

                    missing_slots = list(state.get("missing_slots", []))
                    if not species_id and "species" not in missing_slots:
                        missing_slots.append("species")
                    if not substrate_id and "substrate" not in missing_slots:
                        missing_slots.append("substrate")

                    return {
                        "plant_id": str(plant.id),
                        "nickname": plant.nickname,
                        "resolved_species_id": species_id,
                        "resolved_substrate_id": substrate_id,
                        "resolved_trait_ids": trait_ids,
                        "resolved_phase_id": phase_id,
                        "health_status": health_status,
                        "health_confirmed": health_confirmed,
                        "trait_confirmed": trait_confirmed,
                        "species_data": species_data,
                        "substrate_data": substrate_data,
                        "traits_data": traits_data,
                        "phase_data": phase_data,
                        "missing_slots": [s for s in missing_slots if (s != "species" or not species_id) and (s != "substrate" or not substrate_id)],
                    }

            # Case 2: No plant_id yet, but species and substrate are resolved and user_id is provided
            # Auto-register plant in Digital Garden
            elif species_id and substrate_id and user_id:
                persian_name = species_data.get("botanical_info", {}).get("persian_name") if species_data else None
                nickname = persian_name or species_id

                new_plant = await self.digital_twin_service.create_plant(
                    user_id=user_id,
                    nickname=nickname,
                    species_id=species_id,
                    substrate_type=substrate_id,
                    traits=trait_ids,
                    current_phase=phase_id or "active_vegetative",
                    health_status=health_status if (health_status and health_status != "UNKNOWN") else "HEALTHY",
                )

                # Log initial registration event
                await self.digital_twin_service.log_event(
                    plant_id=new_plant.id,
                    event_type="DISCOVERY",
                    details={
                        "source": "diagnostic_chat",
                        "registered_via": "PhytoAgent Consultation",
                    },
                )

                missing_slots = list(state.get("missing_slots", []))
                return {
                    "plant_id": str(new_plant.id),
                    "nickname": new_plant.nickname,
                    "resolved_species_id": species_id,
                    "resolved_substrate_id": substrate_id,
                    "resolved_trait_ids": trait_ids,
                    "resolved_phase_id": phase_id or "active_vegetative",
                    "health_status": new_plant.health_status,
                    "health_confirmed": health_confirmed,
                    "trait_confirmed": trait_confirmed,
                    "species_data": species_data,
                    "substrate_data": substrate_data,
                    "traits_data": traits_data,
                    "phase_data": phase_data,
                    "missing_slots": [s for s in missing_slots if (s != "species" or not species_id) and (s != "substrate" or not substrate_id)],
                }
        except Exception as exc:
            logger.warning(f"Error syncing digital twin: {exc}")

        return {}

    # =========================================================================
    # Node 3: Risk & Pathology Triage
    # =========================================================================

    async def node_risk_triage(self, state: PlantCareState) -> Dict[str, Any]:
        species_data = state.get("species_data")
        substrate_id = state.get("resolved_substrate_id")
        health_status = state.get("health_status", "UNKNOWN")
        health_confirmed = state.get("health_confirmed")
        reported_symptoms = state.get("reported_symptoms") or []
        intent = state.get("intent")

        # 1. Pathology / Disease / Pest Triage
        if health_status == "SICK_OR_SYMPTOMATIC" or health_confirmed is False or reported_symptoms or intent == "SYMPTOM_DIAGNOSIS":
            symptom_str = "، ".join(reported_symptoms) if reported_symptoms else "زردی برگ، علائم آفت یا تنش فیزیولوژیکی"
            return {
                "risk_level": "CRITICAL_BLOCKER",
                "risk_type": "PATHOLOGY",
                "risk_message": f"گیاه دارای علائم تنش/بیماری ({symptom_str}) است. به دلیل آسیب به بافت‌ها و ریشه‌های مویین، مصرف هرگونه کود شیمیایی تا زمان درمان کامل و احیای گیاه متوقف می‌شود.",
            }

        # 2. Substrate Risk Triage
        if species_data and substrate_id:
            species_model = SpeciesModel(**species_data)
            risk_level, risk_message = AgronomyEngine.evaluate_substrate_risk(species_model, substrate_id)
            return {
                "risk_level": risk_level,
                "risk_type": "SUBSTRATE" if risk_level == "CRITICAL_BLOCKER" else None,
                "risk_message": risk_message,
            }

        return {
            "risk_level": "OPTIMAL",
            "risk_type": None,
            "risk_message": None,
        }

    # =========================================================================
    # Node 4: Goal Feasibility Check
    # =========================================================================

    async def node_goal_feasibility(self, state: PlantCareState) -> Dict[str, Any]:
        species_data = state.get("species_data")
        extracted = state.get("extracted_entities") or {}
        user_goal = extracted.get("user_goal")

        if not species_data:
            return {"feasibility_status": "FEASIBLE", "feasibility_message": None}

        species_model = SpeciesModel(**species_data)
        is_feasible, feasibility_msg = AgronomyEngine.check_goal_feasibility(species_model, user_goal)

        return {
            "feasibility_status": "FEASIBLE" if is_feasible else "UNREALISTIC",
            "feasibility_message": feasibility_msg,
        }

    # =========================================================================
    # Node 5: Compute 4-Week Schedule
    # =========================================================================

    async def node_compute_schedule(self, state: PlantCareState) -> Dict[str, Any]:
        species_data = state.get("species_data")
        substrate_data = state.get("substrate_data")
        traits_data = state.get("traits_data", [])
        phase_data = state.get("phase_data")
        health_status = state.get("health_status", "UNKNOWN")
        health_confirmed = state.get("health_confirmed")
        risk_level = state.get("risk_level")
        user_intent = state.get("user_intent") or state.get("intent")

        # Golden Rule: Never compute fertilizer schedule for sick plants or without substrate/species or blocker or non-feeding intent
        if (
            not species_data
            or not substrate_data
            or risk_level == "CRITICAL_BLOCKER"
            or health_status == "SICK_OR_SYMPTOMATIC"
            or health_confirmed is not True
            or user_intent != "FEEDING_CARE"
        ):
            return {"calculated_schedule": None}

        species_model = SpeciesModel(**species_data)
        substrate_model = SubstrateModel(**substrate_data)
        traits_list = [TraitModel(**t) for t in traits_data]
        phase_model = PhaseModel(**phase_data) if phase_data else None

        schedule = AgronomyEngine.generate_4week_schedule(
            species=species_model,
            substrate=substrate_model,
            traits=traits_list,
            phase=phase_model,
        )

        return {"calculated_schedule": schedule}

    # =========================================================================
    # Node 6: Synthesize Expert Persian Response (LLM-Powered with Botanical Grounding)
    # =========================================================================

    async def _call_llm_synthesizer(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """
        Invokes the LLM to generate dynamic, natural, highly-engaging Persian responses
        grounded in the agronomic engine's analytical facts and clinical state with automatic retries.
        """
        if not self.extractor or not getattr(self.extractor, "client", None) or not getattr(self.extractor, "api_key", None):
            return None
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=1, max=4),
                reraise=True,
            ):
                with attempt:
                    coro = self.extractor.client.chat.completions.create(
                        model=self.extractor.model_name,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        temperature=0.4,
                    )
                    response = await asyncio.wait_for(coro, timeout=30.0)
                    content = response.choices[0].message.content
                    if content and content.strip():
                        return content.strip()
        except Exception as exc:
            logger.warning(f"LLM response synthesis failed after retries: {exc}. Using deterministic fallback.")
        return None

    def _prepare_synthesis_context(self, state: PlantCareState) -> Tuple[Optional[str], Optional[str], str]:
        missing_slots = state.get("missing_slots", [])
        risk_level = state.get("risk_level")
        risk_message = state.get("risk_message")
        risk_type = state.get("risk_type")
        feasibility_status = state.get("feasibility_status")
        feasibility_message = state.get("feasibility_message")
        schedule = state.get("calculated_schedule")
        species_data = state.get("species_data")
        substrate_data = state.get("substrate_data")
        user_intent = state.get("user_intent") or state.get("intent") or "UNSPECIFIED"
        health_status = state.get("health_status", "UNKNOWN")
        health_confirmed = state.get("health_confirmed")
        trait_confirmed = state.get("trait_confirmed")
        reported_symptoms = state.get("reported_symptoms") or []

        species_name = species_data.get("botanical_info", {}).get("persian_name", "گیاه شما") if species_data else "گیاه شما"
        trait_labels = [t.get("label") for t in (state.get("traits_data") or []) if t.get("label")]
        plant_desc = f"{species_name} {' '.join(trait_labels)}".strip() if trait_labels else species_name

        llm_instruction = ""
        clinical_data_summary: Dict[str, Any] = {}
        fallback_response = ""

        # Branch 1: Species is completely unknown (Initial Welcome)
        if "species" in missing_slots or not species_data:
            clinical_data_summary = {
                "situation": "گونه گیاه هنوز مشخص نیست.",
                "user_message": state.get("user_message", ""),
            }
            llm_instruction = (
                "به گرمی به کاربر سلام کنید، خود را به عنوان دستیار گیاه‌پزشکی فیتو معرفی کنید "
                "و با لحنی صمیمی و طبیعی بپرسید گیاه او چه نام دارد و در چه خاکی کاشته شده است تا بتوانید راهنمایی تخصصی ارائه دهید."
            )
            questions = [
                "۱. نام یا گونه گیاه شما چیست؟ (مثلاً برگ‌انجیری، درخت لیمو و...)",
                "۲. گیاه در چه نوع خاکی کاشته شده است؟ (مثلاً کوکوپیت و پرلیت، خاک سنگین و باغچه‌ای، بستر اروید یا هیدروپونیک)",
            ]
            fallback_response = (
                "سلام! من **فیتو**، متخصص گیاه‌پزشکی و اگرونومی شما هستم. 🌱\n\n"
                "برای اینکه بتوانم یک نسخه دقیق، علمی و بدون ریسک برای گیاه شما تجویز کنم، نیاز به تکمیل اطلاعات زیر دارم:\n\n"
                + "\n".join(questions)
                + "\n\nلطفاً این موارد را بفرمایید تا محاسبات دقیق تغذیه و سلامت گیاه انجام شود."
            )

        # Branch 2: Pathology Triage / Sick Plant with Symptoms (BLOCK FERTILIZER)
        elif health_status == "SICK_OR_SYMPTOMATIC" or health_confirmed is False or reported_symptoms or user_intent == "DIAGNOSIS_SYMPTOM":
            symptoms_str = "، ".join(reported_symptoms) if reported_symptoms else "علائم تنش زیستی یا آفت"
            clinical_data_summary = {
                "situation": "گیاه دارای علائم بیماری یا آفت است.",
                "plant": plant_desc,
                "symptoms": symptoms_str,
                "user_message": state.get("user_message", ""),
            }
            llm_instruction = (
                f"برای گیاه {plant_desc} گزارش تریاژ و آسیب‌شناسی گیاه‌پزشکی ارائه دهید. "
                f"به دلیل وجود علائم تنش/آفت ({symptoms_str})، تاکید قاطع و دلسوزانه کنید که «توقف کامل کوددهی» الزامی است و علل علمی آن را توضیح دهید. "
                "سپس اقدامات فوری درمان، ایزولاسیون، کنترل آبیاری و آفت‌کشی را به شکل مرتب و خوانا بیان کنید و بگویید پس از رویش برگ‌های جدید سالم برنامه کودی صادر خواهد شد."
            )
            fallback_response = (
                f"🩺 **گزارش تریاژ و آسیب‌شناسی گیاه‌پزشکی برای {plant_desc}**\n\n"
                f"🔍 **علائم شناسایی‌شده:** {symptoms_str}\n\n"
                f"⛔ **دستور اکید گیاه‌پزشکی (توقف کامل کوددهی):**\n"
                f"به دلیل وجود علائم تنش/آفت و آسیب‌دیدگی بافت‌های گیاه، **مصرف هرگونه کود شیمیایی تا زمان درمان کامل و احیای ریشه‌ها اکیداً ممنوع است.** "
                f"(کوددهی به گیاه بیمار باعث سوختگی ریشه‌های مویین، تشدید مسمومیت اسمزی و تغذیه عوامل بیماری‌زا می‌شود).\n\n"
                f"🛡️ **اقدامات درمانی و اصلاحی فوری:**\n"
                f"۱. **بررسی دقیق و ایزولاسیون:** پشت و روی برگ‌ها و طوقه را بررسی کرده و در صورت وجود آفت گیاه را از سایر گلدان‌ها جدا کنید.\n"
                f"۲. **تنظیم آبیاری و زهکش:** آبیاری را تا خشک شدن حداقل ۵۰ تا ۶۰ درصد عمق خاک متوقف کنید و از خروج آب مازاد از زهکش مطمئن شوید.\n"
                f"۳. **درمان تخصصی:** در صورت مشاهده آفت (کنه/شپشک) از صابون حشره‌کش یا روغن چریش استفاده کرده و در صورت لکه‌های قارچی، برگ‌های آلوده را جدا نمایید.\n\n"
                f"پس از مهار کامل علائم و آغاز رویش برگ‌های جدید و سالم، برنامه کودی برای گیاه صادر خواهد شد."
            )

        # Branch 3: Missing Substrate (Gate 1b)
        elif "substrate" in missing_slots or not substrate_data:
            clinical_data_summary = {
                "situation": "گونه گیاه مشخص شده اما بستر کشت نامشخص است.",
                "plant": plant_desc,
                "user_message": state.get("user_message", ""),
            }
            llm_instruction = (
                f"به طور کاملاً طبیعی، صمیمی و خوش‌برخورد از کاربر بپرسید گیاه {plant_desc} او در چه نوع خاک یا بستری کاشته شده است، "
                "و گزینه‌های متداول مناسب (مانند کوکوپیت-پرلیت، آروئید میکس، خاک باغچه‌ای یا هیدروپونیک) را به عنوان راهنمایی دوستانه مثال بزنید."
            )
            fallback_response = (
                f"متشکرم. برای گیاه **{plant_desc}** شما، لطفاً بفرمایید نوع خاک یا بستر کشت چیست؟\n\n"
                f"🌱 **گزینه‌های متداول:**\n"
                f"- بستر کوکوپیت و پرلیت (بدون خاک / Soilless)\n"
                f"- بستر متخلخل اروید میکس (پوسته درخت، پیت‌ماس و لکا)\n"
                f"- خاک سنگین، رسی یا باغچه‌ای\n"
                f"- سیستم هیدروپونیک یا سمی‌هیدرو (لکا/پون)"
            )

        # Branch 4: Substrate is Critical Blocker (e.g. heavy clay on Monstera)
        elif risk_level == "CRITICAL_BLOCKER":
            ideal_mix = species_data.get("substrate_requirements", {}).get("ideal_mix", {}).get("label", "بستر سبک و متخلخل") if species_data else "بستر سبک"
            ideal_comp = species_data.get("substrate_requirements", {}).get("ideal_mix", {}).get("recommended_composition", "") if species_data else ""
            clinical_data_summary = {
                "situation": "بستر انتخابی ریسک بحرانی خفگی ریشه دارد.",
                "plant": plant_desc,
                "risk_message": risk_message,
                "ideal_mix": ideal_mix,
                "ideal_comp": ideal_comp,
                "user_message": state.get("user_message", ""),
            }
            llm_instruction = (
                f"هشدار بحرانی تریاژ بستر برای {plant_desc} صادر کنید. خطر خفگی ریشه و پوسیدگی طوقه را با لحنی دلسوزانه توضیح دهید، "
                f"دستور توقف کوددهی را صادر کنید و دستورالعمل تعویض بستر با {ideal_mix} ({ideal_comp}) را همراه با اقدامات مراقبت اضطراری آموزش دهید."
            )
            fallback_response = (
                f"⛔ **هشدار بحرانی تریاژ بستر برای {plant_desc}**\n\n"
                f"{risk_message}\n\n"
                f"⚠️ **دستور توقف:** به دلیل ریسک بالای خفگی ریشه و پوسیدگی طوقه، **صدور هرگونه کود شیمیایی تا زمان اصلاح خاک متوقف می‌شود.**\n\n"
                f"📋 **دستورالعمل تعویض بستر (Repotting):**\n"
                f"- **بستر استاندارد:** {ideal_mix}\n"
                f"- **ترکیب پیشنهادی:** {ideal_comp}\n\n"
                f"🛡️ **برنامه مراقبت اضطراری تا زمان تعویض خاک:**\n"
                f"۱. آبیاری را فقط پس از خشک شدن حداقل ۷۰٪ عمق خاک انجام دهید.\n"
                f"۲. زهکش کف گلدان را بررسی کرده و زیرگلدانی را بلافاصله پس از خروج آب خالی کنید.\n"
                f"۳. در صورت نیاز به تقویت، فقط از هیومیک اسید با دوز ۵۰٪ جهت بهبود تهویه رس استفاده شود."
            )

        # Branch 5: Trait Disambiguation (Gate 2: Variegated vs Plain Green)
        elif "trait_disambiguation" in missing_slots:
            clinical_data_summary = {
                "situation": "ابهام در صفت ابلق بودن یا سبز ساده برای تنظیم فرمول کودی.",
                "plant": species_name,
                "user_message": state.get("user_message", ""),
            }
            llm_instruction = (
                f"از کاربر بپرسید آیا برگ‌های {species_name} سبز یکدست است یا ابلق (دارای بخش‌های سفید یا کرم‌رنگ)، و با لحنی دوستانه توضیح دهید که نیاز کودی گیاهان ابلق با نوع سبز تفاوت دارد."
            )
            fallback_response = (
                f"یک نکته مهم درباره **{species_name}**: آیا برگ‌های گیاه شما **سبز یکدست** است یا **ابلق (دارای بخش‌های سفید یا کرم‌رنگ)**؟\n\n"
                f"*(نوع تغذیه و نیاز کودی گیاهان ابلق با نوع سبز متفاوت است.)*"
            )

        # Branch 6: User Intent is UNSPECIFIED (Information registered, prompt user for goal)
        elif user_intent == "UNSPECIFIED" or "user_intent" in missing_slots:
            substrate_name = substrate_data.get("label", "") if substrate_data else ""
            sub_text = f" در بستر {substrate_name}" if substrate_name else ""
            clinical_data_summary = {
                "situation": "مشخصات گیاه ثبت شد و کاربر هنوز درخواستی مطرح نکرده است.",
                "plant": plant_desc,
                "substrate": substrate_name,
                "user_message": state.get("user_message", ""),
            }
            llm_instruction = (
                f"با بیانی گرم، دوستانه و پرانرژی اعلام کنید مشخصات گیاه ({plant_desc}{sub_text}) ثبت شد و بپرسید در حال حاضر چه کمکی از دست شما برمی‌آید "
                "(مانند دریافت برنامه کودی و تغذیه، عیب‌یابی بیماری و آفت، راهنمای شرایط نگهداری و نور/آبیاری، یا تعویض گلدان و بستر)."
            )
            sub_md = f" در بستر **{substrate_name}**" if substrate_name else ""
            fallback_response = (
                f"مشخصات گیاه شما ثبت شد: **{plant_desc}{sub_md}** 🌱\n\n"
                f"در حال حاضر چه کمکی می‌توانم به شما بکنم؟"
            )

        # Branch 7: General Care Guide (Light, Water, Temp, Humidity, Repotting)
        elif user_intent == "GENERAL_CARE":
            tolerances = species_data.get("tolerances", {}) if species_data else {}
            sub_req = species_data.get("substrate_requirements", {}) if species_data else {}
            clinical_data_summary = {
                "situation": "درخواست راهنمای جامع شرایط نگهداری و محیطی.",
                "plant": plant_desc,
                "tolerances": tolerances,
                "substrate_requirements": sub_req,
                "user_message": state.get("user_message", ""),
            }
            llm_instruction = (
                f"راهنمای جامع، جذاب و بسیار خوانای شرایط نگهداری برای {plant_desc} ارائه دهید. "
                "شامل بخش‌های نور ایده‌آل (با ارقام لوکس از داده‌ها)، آبیاری و رطوبت، دما و تهویه، و بستر مناسب."
            )
            light_lux = tolerances.get("light_lux", {})
            humidity_pct = tolerances.get("humidity_pct", {})
            temp_c = tolerances.get("temp_celsius", {})
            ideal_mix = sub_req.get("ideal_mix", {}).get("label", "بستر سبک و متخلخل")
            ideal_comp = sub_req.get("ideal_mix", {}).get("recommended_composition", "")
            fallback_response = (
                f"📘 **راهنمای جامع شرایط نگهداری و محیطی برای {plant_desc}**\n\n"
                f"☀️ **نور ایده‌آل:**\n"
                f"- شدت روشنایی: `{light_lux.get('optimal_min', 2000)} تا {light_lux.get('optimal_max', 5000)} لوکس` (نور فیلترشده و غیرمستقیم)\n"
                f"- آفتاب مستقیم مجاز: حداکثر `{light_lux.get('max_direct_sun_hours', 1)} ساعت` در روز\n\n"
                f"💧 **آبیاری و رطوبت:**\n"
                f"- رطوبت مطلوب: `{humidity_pct.get('optimal', 65)}٪` (حداقل مجاز: `{humidity_pct.get('min', 40)}٪`)\n"
                f"- زمان آبیاری: پس از خشک شدن ۵۰ تا ۶۰ درصد عمق خاک با خروج کامل آب از زهکش\n\n"
                f"🌡️ **دما و تهویه:**\n"
                f"- دمای ایده‌آل: `{temp_c.get('optimal', 22)} تا {temp_c.get('optimal', 25)} درجه سانتی‌گراد` (بازه مجاز: {temp_c.get('min', 15)} تا {temp_c.get('max', 30)} درجه)\n\n"
                f"🪴 **بستر مناسب:**\n"
                f"- نوع بستر: **{ideal_mix}**\n"
                f"{f'- ترکیب پیشنهادی: {ideal_comp}' if ideal_comp else ''}\n\n"
                f"در صورت نیاز به برنامه کودی، عیب‌یابی یا تعویض خاک می‌توانید در ادامه پیام دهید."
            )

        # Branch 8: Health Check Gate (for FEEDING_CARE before schedule computation)
        elif "health_verification" in missing_slots or (health_confirmed is not True):
            clinical_data_summary = {
                "situation": "کاربر درخواست برنامه کودی دارد اما سلامت ریشه/برگ تایید نشده است.",
                "plant": plant_desc,
                "user_message": state.get("user_message", ""),
            }
            llm_instruction = (
                f"قبل از تنظیم دوز و تقویم کودی برای {plant_desc}، توضیح دهید که چرا بررسی سلامت ریشه و برگ‌ها ضروری است "
                "و بپرسید آیا گیاه در حال حاضر کاملاً سالم، دارای رشد و بدون آفت یا زردی است یا خیر."
            )
            fallback_response = (
                f"قبل از تنظیم دوز و تقویم کودی برای **{plant_desc}**، لطفاً وضعیت سلامت ریشه و برگ‌ها را مشخص فرمایید:\n\n"
                f"آیا گیاه شما در حال حاضر **کاملاً سالم، دارای رشد و بدون آفت یا زردی** است؟\n\n"
                f"*(کوددهی به گیاه بیمار یا آفت‌زده باعث تشدید آسیب به ریشه می‌شود.)*"
            )

        # Branch 9: Healthy Plant + Compatible Substrate (4-Week Precision Schedule)
        else:
            substrate_name = substrate_data.get("label", "") if substrate_data else ""
            clinical_data_summary = {
                "situation": "نسخه کودی تخصصی ۴ هفته‌ای آماده است.",
                "plant": plant_desc,
                "substrate": substrate_name,
                "feasibility_status": feasibility_status,
                "feasibility_message": feasibility_message,
                "schedule": schedule,
                "user_message": state.get("user_message", ""),
            }
            llm_instruction = (
                f"نسخه تخصصی و تقویم تغذیه ۴ هفته‌ای برای {plant_desc} را بر اساس داده‌های جدول کودی (فرمول NPK مبنا، هدایت الکتریکی EC، دامنه pH، دوره تکرار آبیاری، موارد ممنوع، و برنامه اجرایی هفته‌های ۱ تا ۴ با مکمل‌ها) با فرمت‌بندی فوق‌العاده شیک Markdown بنویسید."
            )
            if feasibility_status == "UNREALISTIC" and feasibility_message:
                llm_instruction += f"\n📌 یادداشت مهم اگرونومی: حتماً به کاربر توضیح دهید که {feasibility_message}."

            lines = [
                f"🌿 **نسخه تخصصی و تقویم تغذیه ۴ هفته‌ای برای {plant_desc}**",
                f"- **بستر شناسایی‌شده:** {substrate_name}",
            ]
            if feasibility_status == "UNREALISTIC" and feasibility_message:
                lines.append(f"\n📌 **یادداشت اگرونومی:**\n{feasibility_message}\n")

            if schedule:
                lines.append(f"- **فرمول کودی مبنا:** `{schedule['applied_npk_ratio']}`")
                lines.append(f"- **هدایت الکتریکی هدف (EC):** `{schedule['effective_dose_ec']} mS/cm` (ضریب دوز: {schedule['dose_multiplier']}x)")
                lines.append(f"- **دامنه مجاز pH بستر:** `{schedule['target_ph_range'][0]} - {schedule['target_ph_range'][1]}`")
                lines.append(f"- **دوره تکرار آبیاری:** حدود هر `{schedule['interval_days']}` روز یک‌بار (بسته به رطوبت خاک)\n")

                if schedule["banned_fertilizers"]:
                    lines.append(f"🚫 **موارد اکیداً ممنوع:** {', '.join(schedule['banned_fertilizers'])}")

                lines.append("\n📅 **برنامه اجرایی ۴ هفته‌ای:**")
                persian_digits = {"1": "۱", "2": "۲", "3": "۳", "4": "۴"}
                for w in schedule["weeks"]:
                    p_num = persian_digits.get(str(w['week_num']), str(w['week_num']))
                    supp_text = f" | مکمل‌ها: {', '.join(w['supplements'])}" if w['supplements'] else ""
                    lines.append(
                        f"- **هفته {p_num} ({w['title']}):**\n"
                        f"  {w['action']}{supp_text}\n"
                        f"  💡 *نکته:* {w['notes']}"
                    )

            fallback_response = "\n".join(lines)

        user_prompt: Optional[str] = None
        system_prompt: Optional[str] = None
        if llm_instruction:
            user_prompt = (
                f"اطلاعات بالینی و تحلیلی گیاه:\n```json\n{json.dumps(clinical_data_summary, ensure_ascii=False, indent=2)}\n```\n\n"
                f"دستورالعمل تولید پاسخ:\n{llm_instruction}"
            )
            system_prompt = SYNTHESIS_SYSTEM_PROMPT

        return system_prompt, user_prompt, fallback_response

    async def node_synthesize_response(self, state: PlantCareState) -> Dict[str, Any]:
        system_prompt, user_prompt, fallback_response = self._prepare_synthesis_context(state)

        if system_prompt and user_prompt:
            llm_res = await self._call_llm_synthesizer(system_prompt, user_prompt)
            if llm_res:
                return {"final_response": llm_res}

        return {"final_response": fallback_response}

    async def astream_response_synthesis(self, state: PlantCareState) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Asynchronously streams the synthesized Persian response tokens in real-time.
        If the LLM client is active, it streams tokens from the LLM chat completion stream;
        otherwise it streams the deterministic botanical fallback smoothly.
        """
        system_prompt, user_prompt, fallback_response = self._prepare_synthesis_context(state)
        streamed_any = False

        if system_prompt and user_prompt and self.extractor and getattr(self.extractor, "client", None) and getattr(self.extractor, "api_key", None):
            try:
                response_stream = await self.extractor.client.chat.completions.create(
                    model=self.extractor.model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.4,
                    stream=True,
                )
                accumulated: List[str] = []
                async for chunk in response_stream:
                    if chunk.choices and len(chunk.choices) > 0:
                        delta = chunk.choices[0].delta.content
                        if delta:
                            streamed_any = True
                            accumulated.append(delta)
                            yield {"type": "token", "content": delta}

                if streamed_any:
                    full_text = "".join(accumulated).strip()
                    state["final_response"] = full_text
                    yield {"type": "done", "final_state": state}
                    return
            except Exception as exc:
                logger.warning(f"Streaming LLM synthesis failed: {exc}. Using deterministic fallback streaming.")

        if not streamed_any:
            # Stream deterministic fallback chunk by chunk
            words_and_spaces = re.split(r'(\s+)', fallback_response)
            for part in words_and_spaces:
                if part:
                    yield {"type": "token", "content": part}
                    await asyncio.sleep(0.012)
            state["final_response"] = fallback_response
            yield {"type": "done", "final_state": state}

    async def astream_diagnostic(self, initial_state: PlantCareState) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Executes the analytical diagnostic workflow nodes (extraction, digital twin sync,
        risk triage, feasibility, and schedule computation) and then streams the synthesized
        response tokens as an async generator.
        """
        state: Dict[str, Any] = dict(initial_state)

        try:
            # 1. Extraction & Botanical Entity Resolution
            ext_update = await self.node_extract_and_resolve(state)  # type: ignore
            state.update(ext_update)

            # 2. Digital Twin Sync
            dt_update = await self.node_sync_digital_twin(state)  # type: ignore
            state.update(dt_update)

            # 3. Botanical Risk Triage
            risk_update = await self.node_risk_triage(state)  # type: ignore
            state.update(risk_update)

            # 4. Biological Feasibility
            feas_update = await self.node_goal_feasibility(state)  # type: ignore
            state.update(feas_update)

            # 5. Routing & Schedule Computation
            route = self.route_after_feasibility(state)  # type: ignore
            if route == "proceed_schedule":
                sched_update = await self.node_compute_schedule(state)  # type: ignore
                state.update(sched_update)
        except Exception as exc:
            logger.error(f"Error executing diagnostic reasoning nodes during stream: {exc}", exc_info=True)
            err_msg = "متأسفانه به دلیل اختلال موقت در سرویس هوش مصنوعی، پردازش این پیام با مشکل مواجه شد. لطفاً مجدداً پیام خود را ارسال فرمایید."
            words = re.split(r'(\s+)', err_msg)
            for w in words:
                if w:
                    yield {"type": "token", "content": w}
                    await asyncio.sleep(0.012)
            state["final_response"] = err_msg
            state["missing_slots"] = []
            yield {"type": "done", "final_state": state}
            return

        # 6. Stream final response synthesis
        async for event in self.astream_response_synthesis(state):  # type: ignore
            yield event


def create_plant_care_graph(
    kb_manager: Optional[KnowledgeBaseManager] = None,
    extractor: Optional[EntityExtractorService] = None,
    digital_twin_service: Optional[DigitalTwinService] = None,
):
    """
    Factory function to instantiate and return the compiled LangGraph diagnostic workflow.
    """
    agent = PlantDiagnosticGraph(
        kb_manager=kb_manager,
        extractor=extractor,
        digital_twin_service=digital_twin_service,
    )
    return agent.graph
