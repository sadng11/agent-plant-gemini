# مستند معماری و پیاده‌سازی: ایجنت تخصصی و هوشمند گیاه‌پزشک (PhytoAgent)

این مستند فنی شامل معماری کامل، ساختار داده‌ها، پایگاه دانش لایه‌ای، مدل وضعیت (State Machine) در **LangGraph**، اسکیماهای دیتابیس **PostgreSQL** و منطق محاسباتی تغذیه و سلامت گیاه است. این سند به عنوان راهنمای جامع برای پیاده‌سازی سیستم مورد استفاده قرار می‌گیرد.

---

## ۱. اصول طراحی و بیانیه مأموریت (Core Principles)

1. **رفتار در سطح متخصص (Expert-Level Diagnostic):** سیستم مانند یک گیاه‌پزشک عمل می‌کند؛ قبل از صدور نسخه، پارامترهای حیاتی محیطی را استخراج کرده و در صورت شرایط بحرانی (مانند بستر نامناسب) صدور کود را متوقف و دستور اصلاح صادر می‌کند.
2. **عدم توهم و عدم پاسخ عمومی (Strictly Grounded):** تولید پاسخ منحصراً بر اساس ادغام فایل‌های مرجع (YAML) و متغیرهای ریاضی انجام می‌شود و از توصیه‌های کلیشه‌ای و عمومی پرهیز می‌گردد.
3. **معماری لایه‌ای تفکیک‌شده (Decoupled Engine):** جداسازی شناسنامه گونه، قوانین فیزیکی بسترها، صفات مورفولوژیکی و فازهای فنولوژیکی جهت مقیاس‌پذیری بالا.
4. **حافظه موجودیت‌محور و باغچه دیجیتال (Entity-Centric Digital Twin):** ذخیره تدریجی مشخصات هر گیاه در دیتابیس جهت مراجعات بعدی و پایش روند رشد.

---

## ۲. پشته فناوری (Tech Stack)

* **زبان و فریم‌ورک‌ها:** Python 3.11+، FastAPI، LangChain، LangGraph
* **اعتبارسنجی داده‌ها:** Pydantic V2، PyYAML
* **پایگاه داده و Checkpointer:** PostgreSQL با افزونه `pgvector` (در صورت نیاز به RAG معنایی) و `PostgresSaver` برای LangGraph
* **مدل‌های زبانی:** مدل‌های با قابلیت Function Calling و Reasoning قوی (مانند GPT-4o یا Claude 3.5 Sonnet) همراه با ابزارهای Vision

---

## ۳. معماری پایگاه دانش چندلایه‌ای (Knowledge Base Structure)

پایگاه دانش به ۴ دسته فایل مجزا تقسیم می‌شود:

```
knowledge_base/
├── species/
│   ├── monstera_deliciosa.yaml
│   └── citrus_limon.yaml
└── global/
    ├── global_substrates.yaml
    ├── global_traits.yaml
    └── global_phases.yaml

```

### ۳.۱. فایل شناسنامه گونه (`species/monstera_deliciosa.yaml`)

```yaml
species_id: "monstera_deliciosa"
botanical_info:
  scientific_name: "Monstera deliciosa"
  persian_name: "برگ‌انجیری (مونسترا)"
  family: "Araceae"
  growth_rate: "moderate_to_fast"

tolerances:
  light_lux:
    min: 1500
    optimal_min: 2500
    optimal_max: 5000
    max_direct_sun_hours: 1
  humidity_pct:
    min: 40
    optimal: 65
  temp_celsius:
    min: 16
    optimal: 24
    max: 30

base_feeding:
  default_npk_ratio: "3-1-2 یا 20-20-20"
  standard_dose_ec: 1.2
  base_frequency_days: 14
  foliar_spray_compatible: true
  sensitive_to_chlorine: true

substrate_requirements:
  ideal_mix:
    label: "بستر سبک، هوادهی بالا و متخلخل (Aroid Mix)"
    recommended_composition: "پوست درخت ۴۰٪ + پیت‌ماس/کوکو ۳۰٪ + پرلیت درشت ۲۰٪ + زغال ۱۰٪"
  compatibility_rules:
    mineral_heavy:
      status: "dangerous"
      alert_message: "خاک سنگین و رسی باعث خفگی ریشه و پوسیدگی حتمی طوقه می‌شود."
      action_recommended: "تعویض گلدان و بستر (Repotting) در اولین فرصت."
      interim_care_plan: "آبیاری پس از خشک شدن ۷۰٪ خاک، کاهش دوز کود به ۵۰٪ همراه هیومیک اسید."
    inert_soilless:
      status: "acceptable"
      note: "مناسب با الزام مصرف مداوم Cal-Mag."
    aroid_chunky_mix:
      status: "ideal"
      note: "بهترین شرایط برای رشد و توسعه ریشه‌های هوایی."

phenology_constraints:
  fruiting_and_flowering:
    indoor_feasibility: "extremely_rare"
    is_fertilizer_driven_only: false
    mandatory_prerequisites:
      plant_maturity_years: 5
      minimum_climbing_height_meters: 3
      light_requirement: "نور فیلترشده بسیار قوی بالای ۵۰۰۰ لوکس"
      ambient_humidity_min_pct: 75
    advisory_strategy:
      action: "explain_prerequisites_first"
      warning: "مصرف بی‌رویه کود فسفر بالا در آپارتمان فقط باعث شوری بستر و سوختگی ریشه می‌شود."

```

### ۳.۲. موتور عمومی بسترها (`global/global_substrates.yaml`)

```yaml
substrates:
  inert_soilless:
    label: "بستر خنثی و بدون خاک (کوکوپیت / پرلیت / پیت بدون ماده غذایی)"
    dose_multiplier: 0.7
    interval_multiplier: 0.8
    target_ph_range: [5.8, 6.3]
    mandatory_supplements:
      - id: "cal_mag"
        name: "کلسیم-منیزیم (Cal-Mag)"
        dose: "۱ میلی‌لیتر در لیتر"
        frequency: "در تمام نوبت‌های کوددهی"
        reason: "کوکوپیت یون‌های کلسیم و منیزیم را بلوکه می‌کند."
    runoff_drain_target_pct: 20

  hydro_and_semi_hydro:
    label: "هیدروپونیک و سمی‌هیدرو (LECA / Pon / DWC)"
    is_liquid_system: true
    target_ph_range: [5.5, 6.2]
    dose_multiplier: 0.6
    mandatory_supplements:
      - id: "hydro_micro"
        name: "میکروالمنت کلاته‌شده پایدار"
        dose: "طبق دستور کود هیدروپونیک"
    actions:
      - "enforce_reservoir_flush_days: 14"
      - "prohibit_thick_organic_extracts: true"

  mineral_heavy:
    label: "خاک سنگین، رسی یا باغچه‌ای فشرده"
    dose_multiplier: 0.5
    interval_multiplier: 1.6
    target_ph_range: [6.5, 7.5]
    mandatory_supplements:
      - id: "humic_acid"
        name: "هیومیک اسید"
        dose: "۱ گرم در لیتر"
        frequency: "هر ۳۰ تا ۴۵ روز"
        reason: "بهبود تهویه و شکستن فشردگی رس."
    warnings:
      - "ریسک خفگی ریشه؛ نیاز به خشک شدن حداقل ۶۰٪ عمق خاک قبل از آبیاری مجدد."

```

### ۳.۳. موتور عمومی صفات (`global/global_traits.yaml`)

```yaml
traits:
  variegated_foliage:
    label: "برگ‌های ابلق / دورنگ"
    fertilizer_rules:
      max_nitrogen_cap_pct: 10
      override_npk_ratio: "10-10-30 یا 12-12-36 (پتاسیم بالا)"
      banned_fertilizers: ["کودهای 30-10-10", "اوره", "نیتروژن خالص"]
      mandatory_supplements:
        - id: "potassium_silicate"
          name: "سیلیکا (سیلیکات پتاسیم)"
          dose: "۰.۵ میلی‌لیتر در لیتر"
          reason: "استحکام دیواره سلولی بخش‌های سفید برگ و جلوگیری از لکه قهوه‌ای."
    environmental_adjustments:
      light_intensity_multiplier: 1.3
      prohibit_foliar_spray: true

```

### ۳.۴. موتور عمومی فازهای زیستی (`global/global_phases.yaml`)

```yaml
phases:
  flowering_and_fruit_set:
    label: "فاز گل‌دهی و تشکیل میوه"
    fertilizer_rules:
      suppress_high_nitrogen: true
      override_npk_ratio: "10-52-10 (فسفر بالا) یا 0-52-34 (MKP)"
      mandatory_supplements:
        - id: "fruit_set_combo"
          name: "فروت‌ست (کلسیم-بور + روی)"
          dose: "۱ میلی‌لیتر در لیتر"
          frequency: "شروع باز شدن گل‌ها تا فندقی شدن میوه"
          reason: "تثبیت دانه گرده و ممانعت از تشکیل لایه جداکننده دمگل."
    watering_rules:
      stability_mode: true
      warning: "نوسان در آبیاری باعث ریزش قطعی گل‌ها می‌شود."

  active_vegetative:
    label: "رشد رویشی فعال"
    fertilizer_rules:
      allow_high_nitrogen: true
      recommended_ratio: "20-20-20 یا 3-1-2"
      supplements: ["جلبک دریایی"]

```

---

## ۴. ساختار پایگاه داده (PostgreSQL Schema)

```sql
-- ۱. جدول مشخصات زنده و دوقلوی دیجیتال گیاه کاربر
CREATE TABLE user_plants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(64) NOT NULL,
    nickname VARCHAR(100) NOT NULL,
    species_id VARCHAR(100) NOT NULL,

    -- متغیرهای فیزیکی و محیطی
    substrate_type VARCHAR(50) NOT NULL, -- e.g., 'inert_soilless', 'mineral_heavy'
    pot_type_and_size VARCHAR(50),
    light_condition VARCHAR(100),
    ambient_humidity NUMERIC(5,2),

    -- آرایه‌ای از صفات و فازها
    traits JSONB DEFAULT '[]'::jsonb, -- e.g., ["variegated_foliage"]
    current_phase VARCHAR(50) DEFAULT 'active_vegetative',

    -- وضعیت سلامت
    health_status VARCHAR(50) DEFAULT 'HEALTHY', -- 'HEALTHY', 'ROOT_ROT_RISK', 'PEST'

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ۲. تاریخچه رویدادها و اقدامات کاربر
CREATE TABLE plant_events_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plant_id UUID REFERENCES user_plants(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL, -- 'WATERING', 'FERTILIZING', 'REPOTTING', 'PRUNING'
    details JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ایندکس‌گذاری برای جستجوی سریع در حافظه مکالمه
CREATE INDEX idx_user_plants_user ON user_plants(user_id);
CREATE INDEX idx_plant_events_plant ON plant_events_log(plant_id);

```

---

## ۵. مدل وضعیت و ماشین حالت در LangGraph

### ۵.۱. ساختار State

```python
from typing import TypedDict, Optional, List, Dict, Any

class PlantCareState(TypedDict):
    user_id: str
    session_id: str
    user_message: str

    # شناسه گیاه و ارجاع داده
    plant_id: Optional[str]
    species_id: Optional[str]
    nickname: Optional[str]

    # متغیرهای استخراج‌شده
    substrate_type: Optional[str]
    traits: List[str]
    current_phase: Optional[str]
    user_goal: Optional[str] # e.g., 'induce_flowering', 'routine_care'

    # اشیای داده بارگذاری‌شده از YAML
    species_data: Optional[Dict[str, Any]]
    substrate_data: Optional[Dict[str, Any]]
    traits_data: List[Dict[str, Any]]
    phase_data: Optional[Dict[str, Any]]

    # وضعیت‌های کنترلی
    missing_slots: List[str]
    risk_level: str # 'OPTIMAL', 'SUB_OPTIMAL', 'CRITICAL_BLOCKER'
    feasibility_status: Optional[str] # 'FEASIBLE', 'UNREALISTIC'

    # خروجی نهایی
    advisory_response: Optional[str]
    fertilization_schedule: Optional[Dict[str, Any]]

```

### ۵.۲. دیاگرام جریان گراف (Graph Workflow)

```
                       [User Message]
                             │
                             ▼
                   ┌───────────────────┐
                   │  Slot_Extraction  │
                   └───────────────────┘
                             │
                             ▼
                   ┌───────────────────┐
                   │ Load_Digital_Twin │
                   └───────────────────┘
                             │
                             ▼
              /─────────────────────────────\
             <  Are Critical Slots Missing?  >
              \─────────────────────────────/
                    │                     │
              [Yes] │                     │ [No]
                    ▼                     ▼
        ┌──────────────────────┐ ┌────────────────────────┐
        │ Ask_Targeted_Slot_Q  │ │   Load_All_YAML_Data   │
        └──────────────────────┘ └────────────────────────┘
                    │                     │
                    ▼                     ▼
             [Output to User]    ┌────────────────────────┐
                                 │ Substrate_Risk_Triage  │
                                 └────────────────────────┘
                                          │
                    /─────────────────────────────────────────\
                   <   Is Substrate CRITICAL_BLOCKER Risk?     >
                    \─────────────────────────────────────────/
                         │                               │
                   [Yes] │                               │ [No]
                         ▼                               ▼
             ┌─────────────────────────┐     ┌────────────────────────┐
             │ Block_Fertilization_And │     │ Feasibility_Goal_Check │
             │ Issue_Repotting_Warning │     └────────────────────────┘
             └─────────────────────────┘                 │
                         │                               ▼
                         │                   ┌────────────────────────┐
                         │                   │ Generate_4Week_Dynamic │
                         │                   │        Schedule        │
                         │                   └────────────────────────┘
                         │                               │
                         └───────────────┬───────────────┘
                                         ▼
                             ┌───────────────────────┐
                             │  Upsert_Digital_Twin  │
                             └───────────────────────┘
                                         │
                                         ▼
                                  [Final Response]

```

---

## ۶. خط لوله محاسبات اگرونومی و تولید برنامه (Calculation Engine)

برای تولید نسخه ۴ هفته‌ای نهایی، خط لوله محاسباتی زیر به ترتیب اجرا می‌شود:

```python
def compute_fertilization_schedule(
    species_data: dict,
    substrate_data: dict,
    traits_data: list,
    phase_data: dict,
    goal: str
) -> dict:
    # ۱. مقداردهی اولیه بر اساس نیاز پایه گونه
    base_ratio = species_data["base_feeding"]["default_npk_ratio"]
    dose_mult = substrate_data.get("dose_multiplier", 1.0)
    interval_mult = substrate_data.get("interval_multiplier", 1.0)

    supplements = list(substrate_data.get("mandatory_supplements", []))
    banned_items = []

    # ۲. اعمال تغییرات صفات (مثل ابلق بودن)
    for trait in traits_data:
        rules = trait.get("fertilizer_rules", {})
        if "override_npk_ratio" in rules:
            base_ratio = rules["override_npk_ratio"]
        if "banned_fertilizers" in rules:
            banned_items.extend(rules["banned_fertilizers"])
        if "mandatory_supplements" in rules:
            supplements.extend(rules["mandatory_supplements"])

    # ۳. اعمال تغییرات فاز زیستی (مثل گل‌دهی / فروت‌ست)
    if phase_data:
        phase_rules = phase_data.get("fertilizer_rules", {})
        if phase_rules.get("suppress_high_nitrogen"):
            banned_items.append("نیتروژن بالا")
        if "override_npk_ratio" in phase_rules:
            base_ratio = phase_rules["override_npk_ratio"]
        if "mandatory_supplements" in phase_rules:
            supplements.extend(phase_rules["mandatory_supplements"])

    # ۴. ساخت برنامه ۴ هفته‌ای چرخشی
    schedule = {
        "applied_ratio": base_ratio,
        "banned_elements": list(set(banned_items)),
        "weeks": [
            {
                "week_num": 1,
                "action": f"تغذیه اصلی با فرمول {base_ratio}",
                "dose_factor": f"{dose_mult} برابر دوز استاندارد",
                "supplements": [s["name"] for s in supplements if s.get("id") == "cal_mag"]
            },
            {
                "week_num": 2,
                "action": "تغذیه تکمیلی / محرک زیستی یا آبیاری خالص",
                "supplements": [s["name"] for s in supplements if s.get("id") in ["potassium_silicate", "fruit_set_combo"]]
            },
            {
                "week_num": 3,
                "action": "اصلاح‌کننده بستر یا نوبت دوم تغذیه اصلی",
                "supplements": [s["name"] for s in supplements if s.get("id") == "humic_acid"]
            },
            {
                "week_num": 4,
                "action": "فلاش و آبشویی بستر (Leaching/Flush) با آب بدون کلر",
                "supplements": []
            }
        ]
    }
    return schedule

```

---

## ۷. ساختار گاردریل‌ها و پرامپت سیستم (System Prompt & Guardrails)

```markdown
شما «فیتوایجنت»، یک متخصص گیاه‌پزشکی و اگرونومی ارشد هستید. رفتار شما باید صددرصد علمی، دقیق و مبتنی بر داده باشد.

قوانین حیاتی که هرگز نباید نقض شوند:
۱. تریاژ بستر قبل از نسخه: اگر بستر گیاه با گونه ناسازگار باشد (مانند خاک رسی برای مونسترا)، اکیداً حق تجویز کود ندارید. باید خطر پوسیدگی ریشه را توضیح داده و اولویت را روی تعویض خاک بگذارید.
۲. سنجش واقع‌گرایی اهداف: اگر کاربر در محیط آپارتمانی درخواست گل/میوه برای گیاهانی مثل مونسترا دارد، توضیح دهید این امر به سن بلوغ (بالای ۵ سال)، قیم خزه‌ای مرتفع و رطوبت جنگلی وابسته است و صرفاً با کود فسفر بالا به دست نمی‌آید.
۳. اعمال محدودیت ابلق: برای گیاهان ابلق، مصرف کودهای نیتروژن‌بالا ممنوع است و باید مصرف سیلیکا و کودهای پتاسیم‌بالا را تجویز کنید.
۴. بستر کوکوپیت: در هر بستر بدون خاک خنثی، مصرف مداوم Cal-Mag الزامی است.
۵. قالب پاسخ: پاسخ‌ها باید ساختاریافته، مرحله‌به‌مرحله و شامل مقادیر دقیق (میلی‌لیتر/گرم در لیتر، دور آبیاری و EC/pH) باشند. از به کار بردن جملات کلی مانند «به گیاه کود مناسب بدهید» خودداری کنید.

```

---

## ۸. نقشه راه پیاده‌سازی گام‌به‌گام (Implementation Roadmap)

1. **گام ۱ (Data Layer):** ایجاد دایرکتوری `knowledge_base/` و افزودن فایل‌های YAML طبق نمونه‌های بالا + ایجاد کلاس‌های Pydantic برای Parse و اعتبارسنجی فایل‌ها.
2. **گام ۲ (Database Layer):** ایجاد جداول `user_plants` و `plant_events_log` در PostgreSQL و اتصال `PostgresSaver` برای مدیریت مکالمات.
3. **گام ۳ (Diagnostic Gating & State):** پیاده‌سازی گراف LangGraph با قابلیت Slot-Filling، گره تریاژ ریسک بستر (`Substrate_Risk_Triage`) و بررسی امکان‌پذیری هدف (`Feasibility_Goal_Check`).
4. **گام ۴ (Calculation Pipeline):** پیاده‌سازی تابع پایتونی ترکیب ضرایب و تولید تقویم کودی ۴ هفته‌ای چرخشی.
5. **گام ۵ (API & Delivery):** اتصال موتور گراف به FastAPI و تحویل پاسخ‌های ساختاریافته به کلاینت وب‌اپلیکیشن.
