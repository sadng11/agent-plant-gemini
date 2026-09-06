import asyncio
import logging
import re
from typing import Any, Dict, List, Optional
import openai
from openai import AsyncOpenAI

from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential

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
- user_intent: نیت اصلی گفت‌وگو (یکی از مقادیر دقیق: UNSPECIFIED, FEEDING_CARE, DIAGNOSIS_SYMPTOM, GENERAL_CARE, RECOVERY_CONFIRMED)
  * UNSPECIFIED: کاربر فقط مشخصات گیاه، خاک یا صفت را معرفی کرده و هنوز سوال یا درخواست مشخصی نپرسیده است (مثل: «مونسترا ابلق در کوکوپیت»، «برگ‌انجیری دارم»، «کوکوپیت»، «ابلق است»).
  * FEEDING_CARE: کاربر صراحتاً درخواست برنامه کودی، دوز کود، جدول تغذیه، تقویت رشد یا خرید کود کرده است (مثل: «برنامه کودی می‌خوام»، «چه کودی بدم؟»، «کوددهی مونسترا»، «دریافت برنامه کودی و تغذیه تخصصی»).
  * DIAGNOSIS_SYMPTOM: کاربر از علائم بیماری، آفت، زردی برگ، لکه قهوه‌ای، سوختگی، قارچ، کنه یا شپشک صحبت می‌کند (مثل: «برگاش زرد شده»، «کنه زده چیکار کنم»، «عیب‌یابی زردی یا آفت»).
  * GENERAL_CARE: کاربر درباره نحوه آبیاری، میزان نور، رطوبت، دما، تعویض خاک/گلدان یا شرایط عمومی نگهداری سوال دارد (مثل: «چقدر آب بدم؟»، «نور مناسب مونسترا چقدره؟»، «شرایط نگهداری»، «راهنمای تعویض گلدان»).
  * RECOVERY_CONFIRMED: کاربر اعلام می‌کند که عارضه یا مشکل گیاه برطرف شده، درمان شده یا به حالت عادی و سلامت بازگشته است (مثل: «مشکل حل شد»، «به حالت عادی بازگشته و حالش کاملا خوبه»، «خوب شده»، «برگ جدید زده و سالمه»).
- health_status: وضعیت سلامت گیاه بر اساس پیام (یکی از مقادیر: HEALTHY, SICK_OR_SYMPTOMATIC, UNKNOWN)
- health_confirmed: تاییدیه صریح سلامت گیاه توسط کاربر:
  * true: اگر کاربر صریحاً اعلام کند گیاه کاملاً سالم، در حال رشد و بدون آفت/زردی است یا مشکل و عارضه گیاه حل شده و گیاه بهبود یافته است (مانند «کاملاً سالمه»، «مشکلی نداره»، «بدون آفت»، «مشکل حل شد»، «بهبود یافته»، «حالش خوبه»، «برگ جدید داده»)
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

    # Common popular indoor/outdoor plants not yet in KB YAML database
    POPULAR_UNSUPPORTED_SPECIES: Dict[str, str] = {
        "پتوس": "پتوس (Pothos)",
        "پوتوس": "پتوس (Pothos)",
        "pothos": "پتوس (Pothos)",
        "سانسوریا": "سانسوریا (Sansevieria)",
        "شمشیری": "سانسوریا (Sansevieria)",
        "sansevieria": "سانسوریا (Sansevieria)",
        "زاموفیلیا": "زاموفیلیا (ZZ Plant)",
        "زامفولیا": "زاموفیلیا (ZZ Plant)",
        "zz plant": "زاموفیلیا (ZZ Plant)",
        "شفلرا": "شفلرا (Schefflera)",
        "schefflera": "شفلرا (Schefflera)",
        "فیکوس": "فیکوس (Ficus)",
        "فیکوس الاستیکا": "فیکوس الاستیکا (Ficus elastica)",
        "بنجامین": "فیکوس بنجامین (Ficus benjamina)",
        "فیکوس لیراتا": "فیکوس لیراتا (Ficus lyrata)",
        "لیراتا": "فیکوس لیراتا (Ficus lyrata)",
        "آگلونما": "آگلونما (Aglaonema)",
        "اگلونما": "آگلونما (Aglaonema)",
        "aglaonema": "آگلونما (Aglaonema)",
        "اسپاتی فیلوم": "اسپاتی‌فیلوم (Spathiphyllum)",
        "اسپاتی‌فیلوم": "اسپاتی‌فیلوم (Spathiphyllum)",
        "اسپاتی": "اسپاتی‌فیلوم (Spathiphyllum)",
        "spathiphyllum": "اسپاتی‌فیلوم (Spathiphyllum)",
        "دیفن باخیا": "دیفن‌باخیا (Dieffenbachia)",
        "دیفن‌باخیا": "دیفن‌باخیا (Dieffenbachia)",
        "دیفن": "دیفن‌باخیا (Dieffenbachia)",
        "dieffenbachia": "دیفن‌باخیا (Dieffenbachia)",
        "یوکا": "یوکا (Yucca)",
        "yucca": "یوکا (Yucca)",
        "کروتون": "کروتون (Croton)",
        "croton": "کروتون (Croton)",
        "برگ بیدی": "برگ‌بیدی (Tradescantia)",
        "برگ‌بیدی": "برگ‌بیدی (Tradescantia)",
        "tradescantia": "برگ‌بیدی (Tradescantia)",
        "ارکیده": "ارکیده (Orchid)",
        "orchid": "ارکیده (Orchid)",
        "سینگونیوم": "سینگونیوم (Syngonium)",
        "syngonium": "سینگونیوم (Syngonium)",
        "پاپیتال": "پاپیتال (English Ivy)",
        "عشقه": "پاپیتال (English Ivy)",
        "ivy": "پاپیتال (English Ivy)",
        "گندمی": "گیاه گندمی (Spider Plant)",
        "سجافی": "گیاه گندمی (Spider Plant)",
        "spider plant": "گیاه گندمی (Spider Plant)",
        "کاکتوس": "کاکتوس (Cactus)",
        "cactus": "کاکتوس (Cactus)",
        "ساکولنت": "ساکولنت (Succulent)",
        "succulent": "ساکولنت (Succulent)",
        "نخل شامادورا": "نخل شامادورا (Chamaedorea)",
        "شامادورا": "نخل شامادورا (Chamaedorea)",
        "نخل اریکا": "نخل اریکا (Areca Palm)",
        "اریکا": "نخل اریکا (Areca Palm)",
        "بگونیا": "بگونیا (Begonia)",
        "begonia": "بگونیا (Begonia)",
        "پپرومیا": "پپرومیا (Peperomia)",
        "پیرومیا": "پپرومیا (Peperomia)",
        "peperomia": "پپرومیا (Peperomia)",
        "کالاتیا": "کالاته‌آ (Calathea)",
        "کالاته آ": "کالاته‌آ (Calathea)",
        "calathea": "کالاته‌آ (Calathea)",
        "فیلودندرون": "فیلودندرون (Philodendron)",
        "philodendron": "فیلودندرون (Philodendron)",
        "سرخس": "سرخس (Fern)",
        "fern": "سرخس (Fern)",
        "بونسای": "بونسای (Bonsai)",
        "bonsai": "بونسای (Bonsai)",
        "حسن یوسف": "حسن‌یوسف (Coleus)",
        "حسن‌یوسف": "حسن‌یوسف (Coleus)",
        "coleus": "حسن‌یوسف (Coleus)",
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
                timeout=60.0,
                max_retries=3,
            )
        else:
            self.client = None

    async def extract_entities_from_message(self, message: str) -> ExtractedPlantEntities:
        """
        Extracts structured plant entities from user message using LLM with automatic retries
        or rule-based fallback if retries fail.
        """
        if self.client and self.api_key:
            try:
                coro = self.client.beta.chat.completions.parse(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                        {"role": "user", "content": message},
                    ],
                    response_format=ExtractedPlantEntities,
                    temperature=0.0,
                )
                response = await asyncio.wait_for(coro, timeout=8.0)
                parsed = response.choices[0].message.parsed
                if parsed is not None:
                    if parsed.species_query:
                        is_supported = bool(self.resolve_species_id(parsed.species_query))
                        if not is_supported:
                            parsed.unsupported_species = parsed.species_query
                            if "species" in parsed.missing_critical_info:
                                parsed.missing_critical_info = [
                                    s for s in parsed.missing_critical_info if s != "species"
                                ]
                    return parsed
            except Exception as exc:
                logger.debug(
                    f"LLM structured output extraction bypassed ({exc}). Using deterministic botanical extractor."
                )

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

        # 1. Species Detection (Supported Knowledge Base Species First)
        for alias in sorted(self.SPECIES_MAP.keys(), key=len, reverse=True):
            if alias in msg:
                species_q = self.SPECIES_MAP[alias]
                break

        # 1b. Popular Unsupported Species Detection
        if not species_q:
            for alias in sorted(self.POPULAR_UNSUPPORTED_SPECIES.keys(), key=len, reverse=True):
                if alias in msg:
                    species_q = self.POPULAR_UNSUPPORTED_SPECIES[alias]
                    break

        # 1c. Generic Persian Plant Mention Regex Patterns
        if not species_q:
            persian_plant_patterns = [
                r"(?:یک\s+)?(?:گیاه|گلدان|درختچه|درخت|گل)\s+([آ-یa-zA-Z\s]+?)(?:\s+(?:دارم|داریم|هست|من|رو|خریدم|کاشتم|$))",
                r"(?:گیاه|گلدان|گل)\s+([آ-یa-zA-Z]+)",
            ]
            for pattern in persian_plant_patterns:
                match = re.search(pattern, msg)
                if match:
                    extracted_name = match.group(1).strip()
                    if extracted_name and len(extracted_name) > 2 and extracted_name not in ["من", "شما", "ما", "خانگی", "آپارتمانی"]:
                        species_q = extracted_name
                        break

        # Check if detected species is unsupported in KB
        unsupported_species = None
        if species_q:
            if not self.resolve_species_id(species_q):
                unsupported_species = species_q

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
        # Remove negated health and recovery phrases first so phrases like "مشکل حل شد" or "بدون آفت" do not trigger symptoms
        clean_msg_for_symptoms = msg
        for neg_term in [
            "مشکل حل شد", "مشکلش حل شد", "مشکل برطرف شد", "حل شد", "برطرف شد",
            "خطر رفع شد", "رفع شد", "درمان شد", "درمان شده", "بهبود پیدا کرده",
            "بهبود یافته", "بهبود یافت", "بهتر شده", "بهتر شد", "سالم شده", "سالم شد",
            "به حالت عادی بازگشته", "به حالت عادی برگشته", "حالش کاملا خوبه", "حالش کاملاً خوبه",
            "حالش خوبه", "حال گیاه خوب شده", "خوب شده", "خوب شد", "روبراه شد", "رو به راهه",
            "بدون آفت", "بدون لکه", "بدون بیماری", "بدون مشکل", "آفت نداره", "بیماری نداره",
            "لکه نداره", "مشکلی نداره", "مشکل نداره", "no pests", "no disease"
        ]:
            clean_msg_for_symptoms = clean_msg_for_symptoms.replace(neg_term, "")

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
            if kw in clean_msg_for_symptoms:
                symptoms.append(sym_label)

        # 6. User Goal Detection
        if any(term in msg for term in ["گل بده", "گلدهی", "میوه", "شکوفه", "flowering", "fruit", "باردهی", "میوه بیاره"]):
            user_goal = "induce_flowering"
        elif any(term in msg for term in ["تعویض گلدان", "تعویض خاک", "repotting", "repot"]):
            user_goal = "repotting"
        elif symptoms or any(term in clean_msg_for_symptoms for term in ["بیمار", "آفت", "قارچ", "کنه", "شپشک", "زرد", "سیاه", "سوخته", "پژمرده", "پوسیدگی", "لکه", "ریزش", "عیب‌یابی"]):
            user_goal = "disease_treatment"
        elif any(term in msg for term in ["کود", "کوددهی", "تقویت", "برنامه", "feeding", "fertilizer", "تغذیه"]):
            user_goal = "routine_care"
        else:
            user_goal = "general_consultation"

        # 7. Health Confirmation & Recovery Detection
        health_positive_terms = [
            "کاملا سالم", "کاملاً سالم", "سالم است", "سالمه", "مشکلی نداره",
            "مشکل نداره", "بدون آفت", "آفت نداره", "بیماری نداره",
            "هیچ علائمی نداره", "سرحاله", "سرحال است", "عالیه", "بدون مشکل",
            "healthy", "no pests", "کاملاً سالم و بدون آفت"
        ]
        recovery_positive_terms = [
            "مشکل حل شد", "مشکلش حل شد", "مشکل برطرف شد", "حل شد", "برطرف شد",
            "خطر رفع شد", "رفع شد", "درمان شد", "بهبود پیدا کرده", "بهبود یافته",
            "بهتر شده", "بهتر شد", "سالم شده", "سالم شد", "خوب شده", "خوب شد",
            "حالش خوبه", "حالش کاملا خوبه", "حالش کاملاً خوبه", "حالش بهتره",
            "حال گیاه خوب شده", "به حالت عادی بازگشته", "به حالت عادی برگشته",
            "برگ جدید زده", "برگ جدید داده", "جوانه زده", "ریشه جدید زده", "ریشه نو زده",
            "روبراه شد", "رو به راهه", "رو به راه شده", "سرحال شده",
            "دیگه مشکلی نداره", "دیگه زرد نمیشه", "دیگه لکه نداره"
        ]
        is_recovery = any(term in msg for term in recovery_positive_terms)
        is_health_confirmed = is_recovery or any(term in msg for term in health_positive_terms)

        # 8. Trait Confirmation Detection
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
        user_intent: str = "UNSPECIFIED"

        has_active_disease_terms = any(term in clean_msg_for_symptoms for term in ["بیمار", "آفت", "قارچ", "کنه", "شپشک", "زرد", "سیاه", "سوخته", "پژمرده", "پوسیدگی", "لکه", "ریزش", "عیب‌یابی"])

        if is_recovery and not has_active_disease_terms:
            symptoms = []
            health_status = "HEALTHY"
            health_confirmed = True
            user_goal = "routine_care"
            if any(term in msg for term in [
                "کود", "کوددهی", "کود دهی", "کود دهم", "کود بدم", "برنامه کودی", "برنامه کود",
                "تقویت", "جدول کودی", "تغذیه", "تغذیه تخصصی", "نسخه کودی", "npk",
                "fertilizer", "feeding", "چه کودی", "کود مناسب", "برنامه تغذیه", "تقویت رشد"
            ]):
                user_intent = "FEEDING_CARE"
            elif any(term in msg for term in ["آبیاری", "نور", "لوکس", "رطوبت", "دما", "نگهداری", "شرایط نگهداری", "تعویض گلدان", "تعویض خاک"]):
                user_intent = "GENERAL_CARE"
            else:
                user_intent = "RECOVERY_CONFIRMED"
        elif symptoms or has_active_disease_terms:
            user_intent = "DIAGNOSIS_SYMPTOM"
            health_status = "SICK_OR_SYMPTOMATIC"
            health_confirmed = False
        elif is_health_confirmed:
            health_status = "HEALTHY"
            health_confirmed = True
            if any(term in msg for term in [
                "کود", "کوددهی", "کود دهی", "کود دهم", "کود بدم", "برنامه کودی", "برنامه کود",
                "تقویت", "جدول کودی", "تغذیه", "تغذیه تخصصی", "نسخه کودی", "npk",
                "fertilizer", "feeding", "چه کودی", "کود مناسب", "برنامه تغذیه", "تقویت رشد",
                "دریافت برنامه کودی", "گل بده", "میوه بده", "میوه‌دهی", "شکوفه", "گلدهی", "flowering", "fruit"
            ]):
                user_intent = "FEEDING_CARE"
            elif any(term in msg for term in [
                "آبیاری", "آب بدم", "چقدر آب", "نور", "لوکس", "رطوبت", "دما", "نگهداری",
                "شرایط نگهداری", "تعویض خاک", "تعویض گلدان", "repot", "repotting", "هرس",
                "قلمه", "مراقبت", "راهنمای آبیاری", "راهنمای تعویض"
            ]):
                user_intent = "GENERAL_CARE"
            else:
                user_intent = "UNSPECIFIED"
        elif any(term in msg for term in [
            "کود", "کوددهی", "کود دهی", "کود دهم", "کود بدم", "برنامه کودی", "برنامه کود",
            "تقویت", "جدول کودی", "تغذیه", "تغذیه تخصصی", "نسخه کودی", "npk",
            "fertilizer", "feeding", "چه کودی", "کود مناسب", "برنامه تغذیه", "تقویت رشد",
            "دریافت برنامه کودی", "گل بده", "میوه بده", "میوه‌دهی", "شکوفه", "گلدهی", "flowering", "fruit"
        ]):
            user_intent = "FEEDING_CARE"
        elif any(term in msg for term in [
            "آبیاری", "آب بدم", "چقدر آب", "نور", "لوکس", "رطوبت", "دما", "نگهداری",
            "شرایط نگهداری", "تعویض خاک", "تعویض گلدان", "repot", "repotting", "هرس",
            "قلمه", "مراقبت", "راهنمای آبیاری", "راهنمای تعویض"
        ]):
            user_intent = "GENERAL_CARE"
        else:
            user_intent = "UNSPECIFIED"

        # 9. Missing Critical Info
        missing: List[str] = []
        if not species_q:
            missing.append("species")
        if user_intent == "FEEDING_CARE" and not substrate_q:
            missing.append("substrate")

        return ExtractedPlantEntities(
            species_query=species_q,
            substrate_query=substrate_q,
            traits_queries=traits_q,
            phase_query=phase_q,
            user_goal=user_goal,
            user_intent=user_intent,
            intent=user_intent,
            health_status=health_status,
            health_confirmed=health_confirmed,
            trait_confirmed=trait_confirmed,
            reported_symptoms=symptoms,
            unsupported_species=unsupported_species,
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
