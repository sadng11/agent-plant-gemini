from typing import Any, Dict, List, Optional, Tuple

from app.models.knowledge_base import (
    CompatibilityStatus,
    PhaseModel,
    SpeciesModel,
    SubstrateModel,
    TraitModel,
)


class AgronomyEngine:
    """
    Deterministic Agronomy and Nutrition Calculation Engine.
    Executes botanical rules, risk triage, phenology feasibility, and 4-week schedules.
    """

    @staticmethod
    def evaluate_substrate_risk(
        species: SpeciesModel,
        substrate_id: str,
    ) -> Tuple[str, Optional[str]]:
        """
        Evaluates substrate risk for the given species.
        Returns:
            (risk_level, message) where risk_level is one of:
            - "CRITICAL_BLOCKER"
            - "SUB_OPTIMAL"
            - "OPTIMAL"
        """
        rules = species.substrate_requirements.compatibility_rules
        rule = rules.get(substrate_id)

        if not rule:
            return "OPTIMAL", None

        if rule.status == CompatibilityStatus.DANGEROUS:
            msg = (
                f"هشدار بحرانی بستر: {rule.alert_message or 'بستر کشت برای این گونه به شدت نامناسب و خطرناک است.'} "
                f"اقدام الزامی: {rule.action_recommended or 'تعویض فوری بستر و گلدان (Repotting).'}"
            )
            if rule.interim_care_plan:
                msg += f" برنامه موقت: {rule.interim_care_plan}"
            return "CRITICAL_BLOCKER", msg

        if rule.status == CompatibilityStatus.ACCEPTABLE:
            return "SUB_OPTIMAL", rule.note or "بستر قابل قبول با رعایت احتیاط‌های مراقبتی."

        return "OPTIMAL", rule.note or "بستر ایده‌آل برای رشد گونه."

    @staticmethod
    def check_goal_feasibility(
        species: SpeciesModel,
        goal: Optional[str],
    ) -> Tuple[bool, Optional[str]]:
        """
        Validates whether the user's biological goal is feasible in indoor/apartment conditions.
        Returns:
            (is_feasible, explanation_message)
        """
        if not goal:
            return True, None

        g = goal.strip().lower()
        if any(term in g for term in ["flowering", "fruit", "شکوفه", "گل", "میوه"]):
            constraints = species.phenology_constraints
            if constraints and isinstance(constraints, dict) and "fruiting_and_flowering" in constraints:
                ff = constraints["fruiting_and_flowering"]
                if ff.indoor_feasibility in ["extremely_rare", "rare"]:
                    prereqs = ff.mandatory_prerequisites
                    prereq_parts = []
                    if prereqs and prereqs.plant_maturity_years:
                        prereq_parts.append(f"سن بلوغ حداقل {prereqs.plant_maturity_years} سال")
                    if prereqs and prereqs.minimum_climbing_height_meters:
                        prereq_parts.append(f"ارتفاع صعود حداقل {prereqs.minimum_climbing_height_meters} متر روی قیم مرطوب")
                    if prereqs and prereqs.light_requirement:
                        prereq_parts.append(f"نور: {prereqs.light_requirement}")
                    if prereqs and prereqs.ambient_humidity_min_pct:
                        prereq_parts.append(f"رطوبت محیطی حداقل {prereqs.ambient_humidity_min_pct}٪")

                    prereq_str = "، ".join(prereq_parts)
                    adv = ff.advisory_strategy
                    warning_text = adv.warning if adv and adv.warning else "مصرف بی‌رویه کودهای القایی بدون تأمین این شرایط، صرفاً باعث مسمومیت کودی ریشه خواهد شد."
                    msg = (
                        f"امکان‌سنجی هدف زیستی (گل‌دهی/میوه‌دهی): در محیط آپارتمان {ff.indoor_feasibility}. "
                        f"این فرایند نیازمند پیش‌نیازهای ساختاری زیستی است ({prereq_str}). "
                        f"{warning_text}"
                    )
                    return False, msg

        return True, None

    @classmethod
    def generate_4week_schedule(
        cls,
        species: SpeciesModel,
        substrate: SubstrateModel,
        traits: List[TraitModel],
        phase: Optional[PhaseModel] = None,
        goal: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generates a 4-week rotating precision fertilization and watering schedule.
        Combines species base feeding, substrate multipliers, trait overrides, and phase rules.
        """
        base_ratio = species.base_feeding.default_npk_ratio
        base_ec = species.base_feeding.standard_dose_ec
        base_freq = species.base_feeding.base_frequency_days

        dose_mult = substrate.dose_multiplier
        interval_mult = substrate.interval_multiplier

        # Collect supplements and banned fertilizers
        supplements_dict: Dict[str, Dict[str, Any]] = {}
        for supp in substrate.mandatory_supplements:
            supplements_dict[supp.id] = supp.model_dump()

        banned_items: List[str] = []
        env_adjustments: Dict[str, Any] = {}

        # Apply Trait Rules (e.g., Variegated foliage)
        for trait in traits:
            f_rules = trait.fertilizer_rules
            if f_rules:
                if f_rules.override_npk_ratio:
                    base_ratio = f_rules.override_npk_ratio
                if f_rules.banned_fertilizers:
                    banned_items.extend(f_rules.banned_fertilizers)
                if f_rules.mandatory_supplements:
                    for s in f_rules.mandatory_supplements:
                        supplements_dict[s.id] = s.model_dump()
            if trait.environmental_adjustments:
                env_dump = trait.environmental_adjustments.model_dump(exclude_none=True)
                env_adjustments.update(env_dump)

        # Apply Phase Rules (e.g., Flowering / Fruit Set)
        if phase and phase.fertilizer_rules:
            p_rules = phase.fertilizer_rules
            if p_rules.suppress_high_nitrogen:
                banned_items.append("کودهای نیتروژن بالا")
            if p_rules.override_npk_ratio and not any(t.fertilizer_rules.override_npk_ratio for t in traits if t.fertilizer_rules):
                base_ratio = p_rules.override_npk_ratio
            if p_rules.mandatory_supplements:
                for s in p_rules.mandatory_supplements:
                    supplements_dict[s.id] = s.model_dump()

        effective_ec = round(base_ec * dose_mult, 2)
        effective_interval = max(3, round(base_freq * interval_mult))
        target_ph = substrate.target_ph_range

        # Build rotating 4-week calendar
        week_1_supps = [
            f"{s['name']} ({s['dose']})"
            for s in supplements_dict.values()
            if s.get("id") in ["cal_mag"]
        ]
        week_2_supps = [
            f"{s['name']} ({s['dose']})"
            for s in supplements_dict.values()
            if s.get("id") in ["potassium_silicate", "fruit_set_combo", "hydro_micro"]
        ]
        week_3_supps = [
            f"{s['name']} ({s['dose']})"
            for s in supplements_dict.values()
            if s.get("id") in ["humic_acid"]
        ]

        weeks = [
            {
                "week_num": 1,
                "title": "نوبت اول تغذیه پایه (Primary Feeding)",
                "action": f"کوددهی با فرمول {base_ratio} (EC هدف: {effective_ec} mS/cm)",
                "dose_factor": f"{dose_mult} برابر دوز استاندارد",
                "supplements": week_1_supps,
                "target_ph": target_ph,
                "notes": f"آبیاری با فاصله حدود هر {effective_interval} روز",
            },
            {
                "week_num": 2,
                "title": "تغذیه تکمیلی / استحکام ساختاری (Structural / Biostimulant)",
                "action": "محلول‌پاشی یا آبیاری ریشه‌ای با مکمل‌های استحکام و محافظت",
                "dose_factor": "دوز درج‌شده در مکمل",
                "supplements": week_2_supps,
                "target_ph": target_ph,
                "notes": "در صورت حساسیت به کلر یا منع محلول‌پاشی، فقط به خاک داده شود.",
            },
            {
                "week_num": 3,
                "title": "اصلاح بستر / نوبت دوم تغذیه (Conditioning / Feeding II)",
                "action": f"کوددهی نوبت دوم با {base_ratio} همراه اصلاح‌کننده بستر",
                "dose_factor": f"{dose_mult} برابر دوز استاندارد",
                "supplements": week_3_supps,
                "target_ph": target_ph,
                "notes": "بهبود تهویه ریشه و جذب کاتیونی",
            },
            {
                "week_num": 4,
                "title": "آبشویی و فلاش بستر (Leaching & Flush)",
                "action": "آبشویی کامل بستر با آب تصفیه یا بدون کلر تا خروج ۲۰٪ زهاب",
                "dose_factor": "بدون کود شیمیایی (فقط آب خالص)",
                "supplements": [],
                "target_ph": target_ph,
                "notes": "تخلیه نمک‌های تجمع‌یافته و جلوگیری از مسمومیت ریشه",
            },
        ]

        return {
            "applied_npk_ratio": base_ratio,
            "standard_dose_ec": base_ec,
            "effective_dose_ec": effective_ec,
            "dose_multiplier": dose_mult,
            "interval_days": effective_interval,
            "target_ph_range": target_ph,
            "banned_fertilizers": list(set(banned_items)),
            "mandatory_supplements": list(supplements_dict.values()),
            "environmental_adjustments": env_adjustments,
            "weeks": weeks,
        }
