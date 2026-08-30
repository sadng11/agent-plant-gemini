import logging
from typing import Any, Dict, List, Optional
from langgraph.graph import END, START, StateGraph

from app.core.agronomy_engine import AgronomyEngine
from app.core.kb_loader import KnowledgeBaseManager, default_kb_manager
from app.models.agent_state import ExtractedPlantEntities, PlantCareState
from app.models.knowledge_base import PhaseModel, SpeciesModel, SubstrateModel, TraitModel
from app.services.digital_twin_service import DigitalTwinService
from app.services.extractor_service import EntityExtractorService

logger = logging.getLogger(__name__)


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
        """Route to synthesis if blocked by substrate risk, pathology, or pending gate slots."""
        risk_level = state.get("risk_level")
        intent = state.get("intent")
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

        if "health_verification" in missing_slots or health_confirmed is not True:
            return "blocked_or_clarification"

        if risk_level == "CRITICAL_BLOCKER":
            return "blocked_or_clarification"

        if health_status == "SICK_OR_SYMPTOMATIC" or health_confirmed is False or intent == "SYMPTOM_DIAGNOSIS":
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

        if new_extracted_obj.health_status == "SICK_OR_SYMPTOMATIC" or reported_symptoms:
            health_confirmed = False
            health_status = "SICK_OR_SYMPTOMATIC"
        elif any(h in msg_lower for h in healthy_patterns):
            health_confirmed = True
            health_status = "HEALTHY"
        elif new_extracted_obj.health_confirmed is not None:
            health_confirmed = new_extracted_obj.health_confirmed
            health_status = "HEALTHY" if health_confirmed else "SICK_OR_SYMPTOMATIC"
        elif prev_health_confirmed is not None:
            health_confirmed = prev_health_confirmed
            health_status = state.get("health_status") or ("HEALTHY" if health_confirmed else "UNKNOWN")
        else:
            health_confirmed = None
            health_status = state.get("health_status") or "UNKNOWN"

        # Intent resolution
        new_intent = new_extracted_obj.intent
        prev_intent = state.get("intent")
        if health_status == "SICK_OR_SYMPTOMATIC" or reported_symptoms or new_intent == "SYMPTOM_DIAGNOSIS":
            intent = "SYMPTOM_DIAGNOSIS"
        elif new_intent in ["FERTILIZER_REQUEST", "HEALTH_CONFIRMATION", "REPOTTING_INQUIRY", "CARE_INQUIRY"]:
            intent = new_intent
        elif prev_intent and prev_intent != "GENERAL_INTRO":
            intent = prev_intent
        else:
            intent = new_intent or prev_intent or "GENERAL_INTRO"

        # Merge raw extraction dictionaries for history
        prev_extracted = state.get("extracted_entities") or {}
        merged_extracted = {
            "species_query": new_extracted_obj.species_query or prev_extracted.get("species_query"),
            "substrate_query": new_extracted_obj.substrate_query or prev_extracted.get("substrate_query"),
            "traits_queries": list(dict.fromkeys((prev_extracted.get("traits_queries") or []) + (new_extracted_obj.traits_queries or []))),
            "phase_query": new_extracted_obj.phase_query or prev_extracted.get("phase_query"),
            "user_goal": new_extracted_obj.user_goal or prev_extracted.get("user_goal"),
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
        elif intent == "SYMPTOM_DIAGNOSIS" or health_status == "SICK_OR_SYMPTOMATIC" or health_confirmed is False:
            # Sick plant needs pathology triage, no further feeding slot needed
            missing_slots = []
        else:
            # Plant feeding flow gates:
            # Gate 1: Substrate
            if not substrate_id:
                missing_slots.append("substrate")
            # Gate 2: Trait Disambiguation (For Monstera when trait is not yet confirmed)
            elif species_id == "monstera_deliciosa" and trait_confirmed is None:
                missing_slots.append("trait_disambiguation")
            # Gate 3: Health Verification (Must confirm health before feeding schedule)
            elif health_confirmed is not True:
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

        if not self.digital_twin_service or not plant_id:
            return {}

        try:
            plant = await self.digital_twin_service.get_plant_by_id(plant_id, user_id=user_id)
            if plant:
                updates: Dict[str, Any] = {}
                species_id = state.get("resolved_species_id") or plant.species_id
                substrate_id = state.get("resolved_substrate_id") or plant.substrate_type
                trait_ids = state.get("resolved_trait_ids") or (list(plant.traits) if plant.traits else [])
                phase_id = state.get("resolved_phase_id") or plant.current_phase

                if state.get("resolved_substrate_id") and state["resolved_substrate_id"] != plant.substrate_type:
                    updates["substrate_type"] = state["resolved_substrate_id"]
                if state.get("resolved_phase_id") and state["resolved_phase_id"] != plant.current_phase:
                    updates["current_phase"] = state["resolved_phase_id"]

                if updates:
                    await self.digital_twin_service.update_plant_state(plant.id, updates)

                missing_slots = list(state.get("missing_slots", []))
                if not species_id and "species" not in missing_slots:
                    missing_slots.append("species")
                if not substrate_id and "substrate" not in missing_slots:
                    missing_slots.append("substrate")

                species_data = state.get("species_data")
                substrate_data = state.get("substrate_data")
                traits_data = list(state.get("traits_data", []))
                phase_data = state.get("phase_data")

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

                health_status = state.get("health_status")
                health_confirmed = state.get("health_confirmed")
                if health_confirmed is None and (not health_status or health_status == "UNKNOWN"):
                    health_status = "HEALTHY"
                    health_confirmed = True

                trait_confirmed = state.get("trait_confirmed")
                if trait_confirmed is None:
                    trait_confirmed = bool(trait_ids)

                return {
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

        # Golden Rule: Never compute fertilizer schedule for sick plants or without substrate/species or blocker
        if not species_data or not substrate_data or risk_level == "CRITICAL_BLOCKER" or health_status == "SICK_OR_SYMPTOMATIC" or health_confirmed is not True:
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
    # Node 6: Synthesize Expert Persian Response
    # =========================================================================

    async def node_synthesize_response(self, state: PlantCareState) -> Dict[str, Any]:
        missing_slots = state.get("missing_slots", [])
        risk_level = state.get("risk_level")
        risk_message = state.get("risk_message")
        feasibility_status = state.get("feasibility_status")
        feasibility_message = state.get("feasibility_message")
        schedule = state.get("calculated_schedule")
        species_data = state.get("species_data")
        substrate_data = state.get("substrate_data")
        intent = state.get("intent")
        health_status = state.get("health_status", "UNKNOWN")
        health_confirmed = state.get("health_confirmed")
        trait_confirmed = state.get("trait_confirmed")
        reported_symptoms = state.get("reported_symptoms") or []

        species_name = species_data.get("botanical_info", {}).get("persian_name", "گیاه شما") if species_data else "گیاه شما"
        trait_labels = [t.get("label") for t in (state.get("traits_data") or []) if t.get("label")]
        plant_desc = f"{species_name} {' '.join(trait_labels)}".strip() if trait_labels else species_name

        # ---------------------------------------------------------------------
        # Branch 1: Species is completely unknown (Initial Welcome)
        # ---------------------------------------------------------------------
        if "species" in missing_slots or not species_data:
            questions = [
                "۱. نام یا گونه گیاه شما چیست؟ (مثلاً برگ‌انجیری، درخت لیمو و...)",
                "۲. گیاه در چه نوع خاکی کاشته شده است؟ (مثلاً کوکوپیت و پرلیت، خاک سنگین و باغچه‌ای، بستر اروید یا هیدروپونیک)",
            ]
            response = (
                "سلام! من **فیتوایجنت**، متخصص گیاه‌پزشکی و اگرونومی شما هستم. 🌱\n\n"
                "برای اینکه بتوانم یک نسخه دقیق، علمی و بدون ریسک برای گیاه شما تجویز کنم، نیاز به تکمیل اطلاعات زیر دارم:\n\n"
                + "\n".join(questions)
                + "\n\nلطفاً این موارد را بفرمایید تا محاسبات دقیق تغذیه و سلامت گیاه انجام شود."
            )
            return {"final_response": response}

        # ---------------------------------------------------------------------
        # Branch 2: Pathology Triage / Sick Plant with Symptoms (BLOCK FERTILIZER)
        # ---------------------------------------------------------------------
        if health_status == "SICK_OR_SYMPTOMATIC" or health_confirmed is False or reported_symptoms or intent == "SYMPTOM_DIAGNOSIS":
            symptoms_str = "، ".join(reported_symptoms) if reported_symptoms else "علائم تنش زیستی"
            response = (
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
            return {"final_response": response}

        # ---------------------------------------------------------------------
        # Branch 3: Substrate is Critical Blocker (e.g. heavy clay on Monstera)
        # ---------------------------------------------------------------------
        if risk_level == "CRITICAL_BLOCKER":
            ideal_mix = species_data.get("substrate_requirements", {}).get("ideal_mix", {}).get("label", "بستر سبک و متخلخل") if species_data else "بستر سبک"
            ideal_comp = species_data.get("substrate_requirements", {}).get("ideal_mix", {}).get("recommended_composition", "") if species_data else ""

            response = (
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
            return {"final_response": response}

        # ---------------------------------------------------------------------
        # Branch 4: Missing Substrate (Gate 1b)
        # ---------------------------------------------------------------------
        if "substrate" in missing_slots or not substrate_data:
            response = (
                f"متشکرم. برای گیاه **{plant_desc}** شما، لطفاً بفرمایید نوع خاک یا بستر کشت چیست؟\n\n"
                f"🌱 **گزینه‌های متداول:**\n"
                f"- بستر کوکوپیت و پرلیت (بدون خاک / Soilless)\n"
                f"- بستر متخلخل اروید میکس (پوسته درخت، پیت‌ماس و لکا)\n"
                f"- خاک سنگین، رسی یا باغچه‌ای\n"
                f"- سیستم هیدروپونیک یا سمی‌هیدرو (لکا/پون)"
            )
            return {"final_response": response}

        # ---------------------------------------------------------------------
        # Branch 5: Trait Disambiguation (Gate 2: Variegated vs Plain Green)
        # ---------------------------------------------------------------------
        if "trait_disambiguation" in missing_slots:
            response = (
                f"یک نکته مهم درباره **{species_name}**: آیا برگ‌های گیاه شما **سبز یکدست** است یا **ابلق (دارای بخش‌های سفید یا کرم‌رنگ)**؟\n\n"
                f"*(نوع تغذیه و نیاز کودی گیاهان ابلق با نوع سبز متفاوت است.)*"
            )
            return {"final_response": response}

        # ---------------------------------------------------------------------
        # Branch 6: Health Check Gate (Gate 3: Must confirm health before schedule)
        # ---------------------------------------------------------------------
        if "health_verification" in missing_slots or (health_confirmed is not True):
            response = (
                f"قبل از تنظیم دوز و تقویم کودی برای **{plant_desc}**، لطفاً وضعیت سلامت ریشه و برگ‌ها را مشخص فرمایید:\n\n"
                f"آیا گیاه شما در حال حاضر **کاملاً سالم، دارای رشد و بدون آفت یا زردی** است؟\n\n"
                f"*(کوددهی به گیاه بیمار یا آفت‌زده باعث تشدید آسیب به ریشه می‌شود.)*"
            )
            return {"final_response": response}

        # ---------------------------------------------------------------------
        # Branch 7: Healthy Plant + Compatible Substrate (4-Week Precision Schedule)
        # ---------------------------------------------------------------------
        substrate_name = substrate_data.get("label", "") if substrate_data else ""

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

        response = "\n".join(lines)
        return {"final_response": response}


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
