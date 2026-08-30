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

        # Conditional Edge 1: Are critical slots missing?
        workflow.add_conditional_edges(
            "sync_digital_twin",
            self.route_after_extraction,
            {
                "ask_clarification": "synthesize_response",
                "proceed_triage": "risk_triage",
            },
        )

        # Conditional Edge 2: Is substrate a critical blocker?
        workflow.add_conditional_edges(
            "risk_triage",
            self.route_after_triage,
            {
                "blocked": "synthesize_response",
                "proceed_feasibility": "goal_feasibility",
            },
        )

        workflow.add_edge("goal_feasibility", "compute_schedule")
        workflow.add_edge("compute_schedule", "synthesize_response")
        workflow.add_edge("synthesize_response", END)

        return workflow.compile()

    # =========================================================================
    # Conditional Routing Logic
    # =========================================================================

    @staticmethod
    def route_after_extraction(state: PlantCareState) -> str:
        """Route to clarification if critical slots are missing; otherwise proceed."""
        if state.get("missing_slots"):
            return "ask_clarification"
        return "proceed_triage"

    @staticmethod
    def route_after_triage(state: PlantCareState) -> str:
        """Route to warning response if substrate is dangerous/blocked; otherwise proceed."""
        if state.get("risk_level") == "CRITICAL_BLOCKER":
            return "blocked"
        return "proceed_feasibility"

    # =========================================================================
    # Node 1: Extract and Resolve Entities
    # =========================================================================

    async def node_extract_and_resolve(self, state: PlantCareState) -> Dict[str, Any]:
        user_message = state.get("user_message", "")

        # 1. Extract entities using Extractor Service for incoming message
        new_extracted_obj = await self.extractor.extract_entities_from_message(user_message)

        # 2. Resolve IDs from new extraction
        new_species = self.extractor.resolve_species_id(new_extracted_obj.species_query)
        new_substrate = self.extractor.resolve_substrate_id(new_extracted_obj.substrate_query)
        new_traits = self.extractor.resolve_trait_ids(new_extracted_obj.traits_queries)
        new_phase = self.extractor.resolve_phase_id(new_extracted_obj.phase_query)

        # 3. Incremental State Merge (preserve existing values if new message is empty)
        species_id = new_species or state.get("resolved_species_id")
        substrate_id = new_substrate or state.get("resolved_substrate_id")

        prev_traits = state.get("resolved_trait_ids") or []
        trait_ids = list(dict.fromkeys(prev_traits + (new_traits or [])))

        phase_id = new_phase or state.get("resolved_phase_id")

        # Merge raw extraction dictionaries for history
        prev_extracted = state.get("extracted_entities") or {}
        merged_extracted = {
            "species_query": new_extracted_obj.species_query or prev_extracted.get("species_query"),
            "substrate_query": new_extracted_obj.substrate_query or prev_extracted.get("substrate_query"),
            "traits_queries": list(dict.fromkeys((prev_extracted.get("traits_queries") or []) + (new_extracted_obj.traits_queries or []))),
            "phase_query": new_extracted_obj.phase_query or prev_extracted.get("phase_query"),
            "user_goal": new_extracted_obj.user_goal or prev_extracted.get("user_goal"),
            "reported_symptoms": list(dict.fromkeys((prev_extracted.get("reported_symptoms") or []) + (new_extracted_obj.reported_symptoms or []))),
            "missing_critical_info": [],
        }

        # 4. Identify missing critical slots across cumulative state
        missing_slots: List[str] = []
        if not species_id:
            missing_slots.append("species")
        if not substrate_id:
            missing_slots.append("substrate")
        merged_extracted["missing_critical_info"] = missing_slots

        # 5. Fetch Knowledge Base records if resolved (reuse existing or load new)
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
                missing_slots.append("species")

        if substrate_id and not substrate_data:
            try:
                sub_model = self.kb.get_substrate(substrate_id)
                substrate_data = sub_model.model_dump()
            except Exception as exc:
                logger.warning(f"Could not load substrate {substrate_id}: {exc}")
                missing_slots.append("substrate")

        if trait_ids:
            existing_trait_ids = {t.get("trait_id") for t in traits_data if isinstance(t, dict)}
            for t_id in trait_ids:
                if t_id not in existing_trait_ids:
                    try:
                        t_model = self.kb.get_trait(t_id)
                        traits_data.append(t_model.model_dump())
                    except Exception as exc:
                        logger.warning(f"Could not load trait {t_id}: {exc}")

        if phase_id and not phase_data:
            try:
                ph_model = self.kb.get_phase(phase_id)
                phase_data = ph_model.model_dump()
            except Exception as exc:
                logger.warning(f"Could not load phase {phase_id}: {exc}")

        return {
            "extracted_entities": merged_extracted,
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
                # Merge missing parameters from digital twin
                species_id = state.get("resolved_species_id") or plant.species_id
                substrate_id = state.get("resolved_substrate_id") or plant.substrate_type
                trait_ids = state.get("resolved_trait_ids") or (list(plant.traits) if plant.traits else [])
                phase_id = state.get("resolved_phase_id") or plant.current_phase

                # If state has new values, update digital twin
                if state.get("resolved_substrate_id") and state["resolved_substrate_id"] != plant.substrate_type:
                    updates["substrate_type"] = state["resolved_substrate_id"]
                if state.get("resolved_phase_id") and state["resolved_phase_id"] != plant.current_phase:
                    updates["current_phase"] = state["resolved_phase_id"]

                if updates:
                    await self.digital_twin_service.update_plant_state(plant.id, updates)

                missing_slots: List[str] = []
                if not species_id:
                    missing_slots.append("species")
                if not substrate_id:
                    missing_slots.append("substrate")

                # Load KB models if not loaded yet
                species_data = state.get("species_data")
                substrate_data = state.get("substrate_data")
                traits_data = list(state.get("traits_data", []))
                phase_data = state.get("phase_data")

                if species_id and not species_data:
                    try:
                        species_data = self.kb.get_species(species_id).model_dump()
                    except Exception as exc:
                        logger.warning(f"Could not load species {species_id}: {exc}")
                        missing_slots.append("species")

                if substrate_id and not substrate_data:
                    try:
                        substrate_data = self.kb.get_substrate(substrate_id).model_dump()
                    except Exception as exc:
                        logger.warning(f"Could not load substrate {substrate_id}: {exc}")
                        missing_slots.append("substrate")

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

                res: Dict[str, Any] = {
                    "nickname": plant.nickname,
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
                return res
        except Exception as exc:
            logger.warning(f"Error syncing digital twin: {exc}")

        return {}

    # =========================================================================
    # Node 3: Substrate Risk Triage
    # =========================================================================

    async def node_risk_triage(self, state: PlantCareState) -> Dict[str, Any]:
        species_data = state.get("species_data")
        substrate_id = state.get("resolved_substrate_id")

        if not species_data or not substrate_id:
            return {
                "risk_level": "CRITICAL_BLOCKER",
                "risk_message": "اطلاعات گونه یا بستر برای تریاژ ایمنی کافی نیست.",
            }

        species_model = SpeciesModel(**species_data)
        risk_level, risk_message = AgronomyEngine.evaluate_substrate_risk(species_model, substrate_id)

        return {
            "risk_level": risk_level,
            "risk_message": risk_message,
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

        if not species_data or not substrate_data:
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

        # Branch 1: Missing critical slots
        if missing_slots:
            # Case 1.1: Initial turn when neither species nor substrate is known
            if "species" in missing_slots and "substrate" in missing_slots:
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

            # Case 1.2: Species is identified, asking specifically for substrate
            if "substrate" in missing_slots:
                species_name = species_data.get("botanical_info", {}).get("persian_name", "گیاه شما") if species_data else "گیاه شما"
                trait_labels = [t.get("label") for t in (state.get("traits_data") or []) if t.get("label")]
                plant_desc = f"{species_name} {' '.join(trait_labels)}".strip() if trait_labels else species_name
                response = (
                    f"متشکرم. برای گیاه **{plant_desc}** شما، لطفاً بفرمایید نوع خاک یا بستر کشت چیست؟\n\n"
                    f"🌱 **گزینه‌های متداول:**\n"
                    f"- بستر کوکوپیت و پرلیت (بدون خاک / Soilless)\n"
                    f"- خاک سنگین، رسی یا باغچه‌ای\n"
                    f"- بستر متخلخل اروید میکس (پوسته درخت، پیت‌ماس و لکا)\n"
                    f"- سیستم هیدروپونیک یا سمی‌هیدرو (لکا/پون)"
                )
                return {"final_response": response}

            # Case 1.3: Substrate is identified, asking specifically for species
            if "species" in missing_slots:
                substrate_name = substrate_data.get("label", "بستر انتخابی شما") if substrate_data else "بستر انتخابی شما"
                response = (
                    f"متشکرم. بستر کشت (**{substrate_name}**) ثبت شد.\n\n"
                    f"لطفاً نام یا گونه گیاه خود را بفرمایید (مثلاً برگ‌انجیری، درخت لیمو، سانسوریا و...) تا محاسبات دقیق تغذیه و سلامت گیاه انجام شود."
                )
                return {"final_response": response}

        # Branch 2: Substrate is Critical Blocker
        if risk_level == "CRITICAL_BLOCKER":
            species_name = species_data.get("botanical_info", {}).get("persian_name", "گیاه شما") if species_data else "گیاه شما"
            ideal_mix = species_data.get("substrate_requirements", {}).get("ideal_mix", {}).get("label", "بستر سبک و متخلخل") if species_data else "بستر سبک"
            ideal_comp = species_data.get("substrate_requirements", {}).get("ideal_mix", {}).get("recommended_composition", "") if species_data else ""

            response = (
                f"⛔ **هشدار بحرانی تریاژ بستر برای {species_name}**\n\n"
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

        # Branch 3: Optimal / Sub-optimal prescription with 4-week schedule
        species_name = species_data.get("botanical_info", {}).get("persian_name", "") if species_data else ""
        substrate_name = substrate_data.get("label", "") if substrate_data else ""

        lines = [
            f"🌿 **نسخه تخصصی و تقویم تغذیه ۴ هفته‌ای برای {species_name}**",
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
