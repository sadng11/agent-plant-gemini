import logging
import re
from typing import Any, Dict, List, Optional
import openai
from openai import AsyncOpenAI

from app.core.config import settings
from app.models.agent_state import ExtractedPlantEntities

logger = logging.getLogger(__name__)

EXTRACTION_SYSTEM_PROMPT = """
شما یک دستیار هوشمند و سیستم استخراج موجودیت‌های گیاهی برای ایجنت PhytoAgent هستید.
وظیفه شما بررسی دقیق پیام کاربر و استخراج اطلاعات زیر در قالب داده‌های ساختاریافته است:
- species_query: نام گونه گیاهی (مانند برگ‌انجیری، مونسترا، درخت لیمو، Citrus)
- substrate_query: نوع خاک یا بستر کشت (مانند کوکوپیت، پرلیت، خاک رسی، خاک باغچه، هیدروپونیک، بستر اروید)
- traits_queries: صفات و ویژگی‌های خاص مورفولوژیکی (مانند ابلق، دورنگ، مینیاتوری، variegated)
- phase_query: فاز زیستی یا فنولوژیکی جاری (مانند رشد رویشی، گل‌دهی، تشکیل میوه، خواب زمستانه)
- user_goal: هدف یا خواسته کاربر (مانند routine_care, disease_treatment, induce_flowering, repotting, general_consultation)
- intent: نیت اصلی گفت‌وگو (یکی از مقادیر: GENERAL_INTRO, SYMPTOM_DIAGNOSIS, FERTILIZER_REQUEST, CARE_INQUIRY, HEALTH_CONFIRMATION, REPOTTING_INQUIRY)
  * GENERAL_INTRO: معرفی ساده گیاه بدون درخواست صریح کود یا علائم بیماری (مثل «من یک گیاه مونسترا دارم»)
  * SYMPTOM_DIAGNOSIS: ذکر علائم بیماری، آفت، زردی، پژمردگی، لکه برگی و پوسیدگی
  * FERTILIZER_REQUEST: درخواست برنامه کودی، دوز کود، تقویت‌کننده یا راهنمایی تغذیه
  * HEALTH_CONFIRMATION: اعلام سالم و بی‌مشکل بودن گیاه در پاسخ به پرسش ایجنت (مثل «کاملاً سالمه»، «آفت نداره»)
  * CARE_INQUIRY: پرسش درباره آبیاری، نور، دما یا شرایط محیطی
  * REPOTTING_INQUIRY: پرسش درباره زمان و روش تعویض گلدان و خاک
- health_status: وضعیت سلامت گیاه بر اساس پیام (یکی از مقادیر: HEALTHY, SICK_OR_SYMPTOMATIC, UNKNOWN)
- health_confirmed: تاییدیه صریح سلامت گیاه توسط کاربر:
  * true: اگر کاربر صریحاً اعلام کند گیاه کاملاً سالم، در حال رشد و بدون آفت/زردی است (مانند «کاملاً سالمه»، «مشکلی نداره»)
  * false: اگر گیاه دارای آفت، زردی، پوسیدگی یا بیماری باشد
  * null: اگر کاربر صحبتی از سلامت نکرده باشد
- trait_confirmed: تاییدیه وضعیت ابلق بودن یا سبز ساده بودن گیاه:
  * true: اگر گیاه ابلق یا دارای لکه‌های سفید/کرم باشد (مانند «ابلق است»، «واریگیتد»)
  * false: اگر گیاه سبز ساده یا معمولی و یکدست باشد (مانند «سبز ساده است»، «ابلق نیست»)
  * null: اگر کاربر مشخص نکرده باشد
- reported_symptoms: علائم ظاهری یا آفات ذکر شده توسط کاربر (مانند زردی برگ، لکه قهوه‌ای، کنه، شپشک، پوسیدگی، سوختگی نوک برگ)
- missing_critical_info: متغیرهای حیاتی نامشخص

در صورت عدم وجود هر یک از موارد، مقدار null یا لیست خالی بگذارید.

""".strip()



class EntityExtractorService:
    """
    Service for extracting structured plant parameters using OpenAI Structured Outputs
    with a deterministic Persian/English rule-based resolution layer.
    """

    # Exact and fuzzy mapping dictionaries for knowledge-base entity resolution
    SPECIES_MAP: Dict[str, str] = {
        "monstera_deliciosa": "monstera_deliciosa",
        "monstera": "monstera_deliciosa",
        "مونسترا": "monstera_deliciosa",
        "برگ‌انجیری": "monstera_deliciosa",
        "برگ انجیری": "monstera_deliciosa",
        "برگانجیری": "monstera_deliciosa",
        "برگ‌انجیری ابلق": "monstera_deliciosa",
        "دلیسیوسا": "monstera_deliciosa",
        "citrus_limon": "citrus_limon",
        "citrus": "citrus_limon",
        "lemon": "citrus_limon",
        "لیمو": "citrus_limon",
        "لیموترش": "citrus_limon",
        "لیمو ترش": "citrus_limon",
        "درخت لیمو": "citrus_limon",
        "مرکبات": "citrus_limon",
    }

    SUBSTRATE_MAP: Dict[str, str] = {
        "inert_soilless": "inert_soilless",
        "کوکوپیت": "inert_soilless",
        "کوکو پیت": "inert_soilless",
        "پرلیت": "inert_soilless",
        "پیت ماس": "inert_soilless",
        "پیت‌ماس": "inert_soilless",
        "کوکوپیت و پرلیت": "inert_soilless",
        "بدون خاک": "inert_soilless",
        "سوئیل لس": "inert_soilless",
        "soilless": "inert_soilless",
        "coco": "inert_soilless",
        "perlite": "inert_soilless",
        "mineral_heavy": "mineral_heavy",
        "خاک سنگین": "mineral_heavy",
        "خاک رس": "mineral_heavy",
        "خاک رسی": "mineral_heavy",
        "خاک باغچه": "mineral_heavy",
        "خاک باغچه‌ای": "mineral_heavy",
        "رس": "mineral_heavy",
        "رسی": "mineral_heavy",
        "heavy clay": "mineral_heavy",
        "mineral": "mineral_heavy",
        "hydro_and_semi_hydro": "hydro_and_semi_hydro",
        "هیدروپونیک": "hydro_and_semi_hydro",
        "سمی هیدرو": "hydro_and_semi_hydro",
        "سمی‌هیدرو": "hydro_and_semi_hydro",
        "لکا": "hydro_and_semi_hydro",
        "پون": "hydro_and_semi_hydro",
        "leca": "hydro_and_semi_hydro",
        "pon": "hydro_and_semi_hydro",
        "dwc": "hydro_and_semi_hydro",
        "aroid_chunky_mix": "aroid_chunky_mix",
        "اروید": "aroid_chunky_mix",
        "آروید": "aroid_chunky_mix",
        "اروید میکس": "aroid_chunky_mix",
        "بستر سبک": "aroid_chunky_mix",
        "پوست درخت": "aroid_chunky_mix",
        "aroid": "aroid_chunky_mix",
    }

    TRAITS_MAP: Dict[str, str] = {
        "variegated_foliage": "variegated_foliage",
        "ابلق": "variegated_foliage",
        "دورنگ": "variegated_foliage",
        "دو رنگ": "variegated_foliage",
        "واریگیتد": "variegated_foliage",
        "سفید سبز": "variegated_foliage",
        "variegated": "variegated_foliage",
    }

    PHASE_MAP: Dict[str, str] = {
        "flowering_and_fruit_set": "flowering_and_fruit_set",
        "گلدهی": "flowering_and_fruit_set",
        "گل‌دهی": "flowering_and_fruit_set",
        "گل": "flowering_and_fruit_set",
        "میوه": "flowering_and_fruit_set",
        "میوه‌دهی": "flowering_and_fruit_set",
        "میوه دهی": "flowering_and_fruit_set",
        "تشکیل میوه": "flowering_and_fruit_set",
        "شکوفه": "flowering_and_fruit_set",
        "flowering": "flowering_and_fruit_set",
        "fruiting": "flowering_and_fruit_set",
        "active_vegetative": "active_vegetative",
        "رشد": "active_vegetative",
        "رویشی": "active_vegetative",
        "رشد رویشی": "active_vegetative",
        "برگ جدید": "active_vegetative",
        "پاجوش": "active_vegetative",
        "vegetative": "active_vegetative",
    }

    def __init__(
        self,
        client: Optional[AsyncOpenAI] = None,
        model_name: Optional[str] = None,
    ):
        self.model_name = model_name or settings.OPENAI_MODEL_NAME
        self.api_key = settings.OPENAI_API_KEY
        if client:
            self.client = client
        elif self.api_key:
            self.client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=settings.OPENAI_BASE_URL,
            )
        else:
            self.client = None

    async def extract_entities_from_message(self, message: str) -> ExtractedPlantEntities:
        """
        Extracts structured plant entities from user message using LLM or rule-based fallback.
        """
        if self.client and self.api_key:
            try:
                response = await self.client.beta.chat.completions.parse(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                        {"role": "user", "content": message},
                    ],
                    response_format=ExtractedPlantEntities,
                    temperature=0.0,
                )
                parsed = response.choices[0].message.parsed
                if parsed is not None:
                    return parsed
            except Exception as exc:
                logger.warning(f"OpenAI structured output failed: {exc}. Falling back to rule-based extraction.")

        return self._rule_based_extract(message)

    def _rule_based_extract(self, message: str) -> ExtractedPlantEntities:
        """
        Deterministic regex/keyword extraction when LLM API is unavailable.
        """
        msg = message.lower()
        species_q: Optional[str] = None
        substrate_q: Optional[str] = None
        traits_q: List[str] = []
        phase_q: Optional[str] = None
        user_goal: Optional[str] = None
        symptoms: List[str] = []
        intent: Optional[str] = None
        health_status: str = "UNKNOWN"

        # 1. Species Detection
        for alias in sorted(self.SPECIES_MAP.keys(), key=len, reverse=True):
            if alias in msg:
                species_q = self.SPECIES_MAP[alias]
                break

        # 2. Substrate Detection
        for alias in sorted(self.SUBSTRATE_MAP.keys(), key=len, reverse=True):
            if alias in msg:
                substrate_q = self.SUBSTRATE_MAP[alias]
                break

        # 3. Traits Detection
        for alias, trait_id in self.TRAITS_MAP.items():
            if alias in msg and trait_id not in traits_q:
                traits_q.append(trait_id)

        # 4. Phase Detection
        for alias in sorted(self.PHASE_MAP.keys(), key=len, reverse=True):
            if alias in msg:
                phase_q = self.PHASE_MAP[alias]
                break

        # 5. Symptoms & Pathology Detection
        symptom_keywords = {
            "زرد": "زردی برگ (Chlorosis)",
            "سیاه": "سیاه شدن ساقه/برگ (Necrosis)",
            "سوخته": "سوختگی نوک یا حاشیه برگ",
            "پژمرده": "پژمردگی و افتادگی ساقه",
            "پوسیدگی": "پوسیدگی ریشه یا طوقه (Root Rot)",
            "لکه": "لکه‌های برگی (قارچی/باکتریایی)",
            "کنه": "کنه تارعنکبوتی (Spider Mites)",
            "شپشک": "شپشک آردآلود (Mealybugs)",
            "پشه": "پشه سیاه خاک (Fungus Gnats)",
            "سفیدک": "سفیدک پودری (Powdery Mildew)",
            "آفت": "مشاهده آفت و حشرات مضر",
            "قارچ": "عفونت قارچی",
            "ریزش": "ریزش غیرعادی برگ‌ها",
            "شل": "شل شدن و له‌شدگی بافت",
        }
        for kw, sym_label in symptom_keywords.items():
            if kw in msg:
                symptoms.append(sym_label)

        # 6. Health Confirmation Detection
        health_positive_terms = [
            "کاملا سالم", "کاملاً سالم", "سالم است", "سالمه", "مشکلی نداره",
            "مشکل نداره", "بدون آفت", "آفت نداره", "بیماری نداره",
            "هیچ علائمی نداره", "سرحاله", "سرحال است", "عالیه", "بدون مشکل",
            "healthy", "no pests", "کاملاً سالم و بدون آفت"
        ]
        is_health_confirmed = any(term in msg for term in health_positive_terms)

        # 7. Trait Confirmation Detection
        trait_plain_terms = [
            "سبز ساده", "سبز معمولی", "سبز یکدست", "سبز است", "سبزه",
            "ابلق نیست", "ساده است", "معمولی است", "plain green", "green"
        ]
        is_plain_green = any(term in msg for term in trait_plain_terms)
        is_variegated = any(alias in msg for alias in self.TRAITS_MAP.keys())

        trait_confirmed: Optional[bool] = None
        if is_variegated:
            trait_confirmed = True
            if "variegated_foliage" not in traits_q:
                traits_q.append("variegated_foliage")
        elif is_plain_green:
            trait_confirmed = False

        health_confirmed: Optional[bool] = None
        if symptoms:
            intent = "SYMPTOM_DIAGNOSIS"
            health_status = "SICK_OR_SYMPTOMATIC"
            health_confirmed = False
            user_goal = "disease_treatment"
        elif is_health_confirmed:
            health_status = "HEALTHY"
            health_confirmed = True
            if any(term in msg for term in ["کود", "کوددهی", "تقویت", "برنامه", "feeding", "fertilizer", "جدول", "تغذیه"]):
                intent = "FERTILIZER_REQUEST"
                user_goal = "routine_care"
            else:
                intent = "HEALTH_CONFIRMATION"
                user_goal = "routine_care"
        elif any(term in msg for term in ["گل بده", "میوه بده", "میوه‌دهی", "شکوفه", "گلدهی", "flowering", "fruit"]):
            intent = "FERTILIZER_REQUEST"
            user_goal = "induce_flowering"
        elif any(term in msg for term in ["تعویض خاک", "تعویض گلدان", "repotting"]):
            intent = "REPOTTING_INQUIRY"
            user_goal = "repotting"
        elif any(term in msg for term in ["کود", "کوددهی", "تقویت", "برنامه کودی", "برنامه کود", "برنامه", "چه کودی", "تغذیه", "feeding", "fertilizer", "جدول"]):
            intent = "FERTILIZER_REQUEST"
            user_goal = "routine_care"
        elif any(term in msg for term in ["آبیاری", "چقدر آب", "نور", "رطوبت", "دما", "نگهداری"]):
            intent = "CARE_INQUIRY"
            user_goal = "general_consultation"
        else:
            intent = "GENERAL_INTRO"
            user_goal = "general_consultation"

        # 8. Missing Critical Info
        missing: List[str] = []
        if not species_q:
            missing.append("species")
        if intent == "FERTILIZER_REQUEST" and not substrate_q:
            missing.append("substrate")

        return ExtractedPlantEntities(
            species_query=species_q,
            substrate_query=substrate_q,
            traits_queries=traits_q,
            phase_query=phase_q,
            user_goal=user_goal,
            intent=intent,
            health_status=health_status,
            health_confirmed=health_confirmed,
            trait_confirmed=trait_confirmed,
            reported_symptoms=symptoms,
            missing_critical_info=missing,
        )



    def resolve_species_id(self, query: Optional[str]) -> Optional[str]:
        """Resolves raw query to standard species_id."""
        if not query:
            return None
        q = query.strip().lower()
        if q in self.SPECIES_MAP:
            return self.SPECIES_MAP[q]
        for key, val in self.SPECIES_MAP.items():
            if key in q or q in key:
                return val
        return None

    def resolve_substrate_id(self, query: Optional[str]) -> Optional[str]:
        """Resolves raw query to standard substrate_id."""
        if not query:
            return None
        q = query.strip().lower()
        if q in self.SUBSTRATE_MAP:
            return self.SUBSTRATE_MAP[q]
        for key, val in self.SUBSTRATE_MAP.items():
            if key in q or q in key:
                return val
        return None

    def resolve_trait_ids(self, queries: List[str]) -> List[str]:
        """Resolves a list of trait queries to unique standard trait_ids."""
        resolved: List[str] = []
        for query in queries:
            q = query.strip().lower()
            if q in self.TRAITS_MAP:
                t_id = self.TRAITS_MAP[q]
                if t_id not in resolved:
                    resolved.append(t_id)
            else:
                for key, val in self.TRAITS_MAP.items():
                    if key in q and val not in resolved:
                        resolved.append(val)
        return resolved

    def resolve_phase_id(self, query: Optional[str]) -> Optional[str]:
        """Resolves raw query to standard phase_id."""
        if not query:
            return None
        q = query.strip().lower()
        if q in self.PHASE_MAP:
            return self.PHASE_MAP[q]
        for key, val in self.PHASE_MAP.items():
            if key in q or q in key:
                return val
        return None
