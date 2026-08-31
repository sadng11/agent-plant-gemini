مستند به‌روزشده‌ی **`AGENT.md`** که بخش جامع **«معماری رابط کاربری، تجربه کاربری و فرانت‌اند (UI/UX & Web Client Architecture)»** به همراه نقشه راه فاز جدید به آن اضافه شده است:

```markdown
# مستند جامع معماری و پیاده‌سازی: ایجنت تخصصی و هوشمند گیاه‌پزشک (PhytoAgent)

این مستند فنی شامل معماری کامل، ساختار داده‌ها، پایگاه دانش لایه‌ای، مدل وضعیت (State Machine) در **LangGraph**، اسکیماهای دیتابیس **PostgreSQL**، منطق محاسباتی تغذیه و سلامت گیاه، معماری API در **FastAPI** و مشخصات کامل طراحی رابط کاربری و تجربه کاربری (**UI/UX & Web Client**) است.

---

## ۱. اصول طراحی و بیانیه مأموریت (Core Principles)

1. **رفتار در سطح متخصص (Expert-Level Diagnostic):** سیستم مانند یک گیاه‌پزشک عمل می‌کند؛ قبل از صدور نسخه، پارامترهای حیاتی محیطی را استخراج کرده و در صورت شرایط بحرانی (مانند بستر نامناسب) صدور کود را متوقف و دستور اصلاح صادر می‌کند.
2. **عدم توهم و عدم پاسخ عمومی (Strictly Grounded):** تولید پاسخ منحصراً بر اساس ادغام فایل‌های مرجع (YAML) و متغیرهای ریاضی انجام می‌شود و از توصیه‌های کلیشه‌ای و عمومی پرهیز می‌گردد.
3. **معماری لایه‌ای تفکیک‌شده (Decoupled Engine):** جداسازی شناسنامه گونه، قوانین فیزیکی بسترها، صفات مورفولوژیکی و فازهای فنولوژیکی جهت مقیاس‌پذیری بالا.
4. **حافظه موجودیت‌محور و باغچه دیجیتال (Entity-Centric Digital Twin):** ذخیره تدریجی مشخصات هر گیاه در دیتابیس جهت مراجعات بعدی و پایش روند رشد.
5. **تجربه کاربری داده‌محور و بصری (Visual & Actionable UX):** تبدیل خروجی‌های ساختاریافته به ویجت‌های تعاملی، تقویم‌های ۴ هفته‌ای گام‌به‌گام، بنرهای تریاژ ریسک و فرم‌های هوشمند پرونده سلامت گیاه.

---

## ۲. پشته فناوری (Tech Stack)

### بک‌اند و هوش مصنوعی (Backend & AI Engine):

- **زبان و فریم‌ورک‌ها:** Python 3.11+، FastAPI، Uvicorn، LangChain، LangGraph
- **اعتبارسنجی داده‌ها:** Pydantic V2، PyYAML
- **پایگاه داده و Checkpointer:** PostgreSQL با افزونه `pgvector`، SQLAlchemy 2.0 (Async)، `asyncpg`، `PostgresSaver` برای LangGraph
- **مدل‌های زبانی:** مدل‌های دارای قابلیت Function Calling و Structured Outputs (مانند GPT-4o یا Claude 3.5 Sonnet)

### فرانت‌اند و کلاینت وب (Frontend & Web Client):

- **فریم‌ورک و هسته:** React 18+ / Next.js (App Router) یا Vite + React با TypeScript
- **طراحی و استایل‌دهی:** Tailwind CSS (طراحی مدرن، دارک/لایت مود، انیمیشن‌های نرم)
- **آیکون‌ها و کامپوننت‌ها:** Lucide React، Radix UI / Shadcn UI primitives
- **مدیریت وضعیت و کش شبکه:** TanStack Query (React Query) برای ارتباط ناهمگام با REST API
- **تایپوگرافی و بومی‌سازی:** قلم وزیرمتن (Vazirmatn)، پشتیبانی کامل از چیدمان راست‌چین (RTL First)

---

## ۳. معماری پایگاه دانش چندلایه‌ای (Knowledge Base Structure)
```

knowledge_base/
├── species/
│ ├── monstera_deliciosa.yaml
│ └── citrus_limon.yaml
└── global/
├── global_substrates.yaml
├── global_traits.yaml
└── global_phases.yaml

````

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

````

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
CREATE TABLE user_plants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(64) NOT NULL,
    nickname VARCHAR(100) NOT NULL,
    species_id VARCHAR(100) NOT NULL,

    substrate_type VARCHAR(50) NOT NULL,
    pot_type_and_size VARCHAR(50),
    light_condition VARCHAR(100),
    ambient_humidity NUMERIC(5,2),

    traits JSONB DEFAULT '[]'::jsonb,
    current_phase VARCHAR(50) DEFAULT 'active_vegetative',
    health_status VARCHAR(50) DEFAULT 'HEALTHY',

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE plant_events_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plant_id UUID REFERENCES user_plants(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    details JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

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

    plant_id: Optional[str]
    species_id: Optional[str]
    nickname: Optional[str]

    substrate_type: Optional[str]
    traits: List[str]
    current_phase: Optional[str]
    user_goal: Optional[str]

    species_data: Optional[Dict[str, Any]]
    substrate_data: Optional[Dict[str, Any]]
    traits_data: List[Dict[str, Any]]
    phase_data: Optional[Dict[str, Any]]

    missing_slots: List[str]
    risk_level: str # 'OPTIMAL', 'SUB_OPTIMAL', 'CRITICAL_BLOCKER'
    feasibility_status: Optional[str] # 'FEASIBLE', 'UNREALISTIC'

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

```python
def compute_fertilization_schedule(
    species_data: dict,
    substrate_data: dict,
    traits_data: list,
    phase_data: dict,
    goal: str
) -> dict:
    base_ratio = species_data["base_feeding"]["default_npk_ratio"]
    dose_mult = substrate_data.get("dose_multiplier", 1.0)
    interval_mult = substrate_data.get("interval_multiplier", 1.0)

    supplements = list(substrate_data.get("mandatory_supplements", []))
    banned_items = []

    for trait in traits_data:
        rules = trait.get("fertilizer_rules", {})
        if "override_npk_ratio" in rules:
            base_ratio = rules["override_npk_ratio"]
        if "banned_fertilizers" in rules:
            banned_items.extend(rules["banned_fertilizers"])
        if "mandatory_supplements" in rules:
            supplements.extend(rules["mandatory_supplements"])

    if phase_data:
        phase_rules = phase_data.get("fertilizer_rules", {})
        if phase_rules.get("suppress_high_nitrogen"):
            banned_items.append("نیتروژن بالا")
        if "override_npk_ratio" in phase_rules:
            base_ratio = phase_rules["override_npk_ratio"]
        if "mandatory_supplements" in phase_rules:
            supplements.extend(phase_rules["mandatory_supplements"])

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
شما «فیتو»، یک متخصص گیاه‌پزشکی و اگرونومی ارشد هستید. رفتار شما باید صددرصد علمی، دقیق و مبتنی بر داده باشد.

قوانین حیاتی که هرگز نباید نقض شوند:
۱. تریاژ بستر قبل از نسخه: اگر بستر گیاه با گونه ناسازگار باشد (مانند خاک رسی برای مونسترا)، اکیداً حق تجویز کود ندارید. باید خطر پوسیدگی ریشه را توضیح داده و اولویت را روی تعویض خاک بگذارید.
۲. سنجش واقع‌گرایی اهداف: اگر کاربر در محیط آپارتمانی درخواست گل/میوه برای گیاهانی مثل مونسترا دارد، توضیح دهید این امر به سن بلوغ (بالای ۵ سال)، قیم خزه‌ای مرتفع و رطوبت جنگلی وابسته است و صرفاً با کود فسفر بالا به دست نمی‌آید.
۳. اعمال محدودیت ابلق: برای گیاهان ابلق، مصرف کودهای نیتروژن‌بالا ممنوع است و باید مصرف سیلیکا و کودهای پتاسیم‌بالا را تجویز کنید.
۴. بستر کوکوپیت: در هر بستر بدون خاک خنثی، مصرف مداوم Cal-Mag الزامی است.
۵. قالب پاسخ: پاسخ‌ها باید ساختاریافته، مرحله‌به‌مرحله و شامل مقادیر دقیق (میلی‌لیتر/گرم در لیتر، دور آبیاری و EC/pH) باشند. از به کار بردن جملات کلی مانند «به گیاه کود مناسب بدهید» خودداری کنید.
```

---

## ۸. معماری لایه وب و ارتباط کلاینت-سرور (FastAPI Web Layer)

### ۸.۱. ساختار اسکیماهای API (`app/models/api_schemas.py`)

- **`ChatRequest`:** فیلدهای `user_id`، `session_id`، `message`، `plant_id`.
- **`ChatResponse`:** فیلدهای `session_id`، `response`، `plant_id`، `risk_level`، `feasibility_status`، `calculated_schedule`، `missing_slots`، `extracted_entities`.
- **`PlantResponse` / `PlantCreateRequest` / `PlantUpdateRequest`:** مدل‌های داده‌ای برای ثبت و مدیریت گیاهان در دوقلوی دیجیتال.
- **`EventLogResponse` / `EventLogCreateRequest`:** ثبت اقدامات کاربر نظیر آبیاری و کوددهی.
- **اندپوینت‌های متادیتا:** لیست گونه‌ها، بسترها، صفات و فازها جهت بارگذاری در منوهای فرانت‌اند.

---

## ۹. معماری رابط کاربری، تجربه کاربری و فرانت‌اند (UI/UX & Web Client Architecture)

### ۹.۱. هویت بصری و سیستم طراحی (Design System & Color Tokens)

- **تم رنگی ارگانیک و مدرن (Botanical Palette):**
- **رنگ اولیه (Primary):** سبز زمردی جنگلی (`Emerald-600` / `#059669` در حالت روز و `Emerald-500` در حالت شب) برای دکمه‌ها و المان‌های تعاملی شاخص.
- **سطوح ریسک تشخیصی (Risk Level Accents):**
- وضعیت بحرانی (`CRITICAL_BLOCKER`): قرمز لاکی (`Rose-600` / `#E11D48`) با پس‌زمینه اخطار `Rose-50`.
- وضعیت هشدار اصلاحی (`SUB_OPTIMAL`): زرد کهربایی (`Amber-500` / `#D97706`).
- وضعیت سالم و ایده‌آل (`OPTIMAL`): سبز نعنایی / فیروزه‌ای (`Teal-600` / `#0D9488`).

- **رنگ‌های خنثی (Neutrals):** خاکستری مایل به زغال (`Slate-900` تا `Slate-50`).

- **تایپوگرافی:** قلم فارسی **Vazirmatn** با اوزان Regular (۴۰۰)، Medium (۵۰۰) و Bold (۷۰۰) به صورت راست‌چین (RTL).

```
+-----------------------------------------------------------------------------------+
|  🌿 فیتو (PhytoAgent) - دستیار تخصصی سلامت و تغذیه گیاهان                  |
+-----------------------------------------------------------------------------------+
| [ 🪴 باغچه من ]    [ 💬 کلینیک تشخیص هوشمند ]    [ 📚 پایگاه دانش ]    [ ⚙️ تنظیمات ]|
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  +---------------------------------------+  +----------------------------------+  |
|  | 🪴 باغچه دیجیتال (Digital Twin)        |  | 💬 کلینیک و چت تشخیصی (Agent)     |  |
|  |                                       |  |                                  |  |
|  |  +---------------------------------+  |  |  👤 کاربر: برگ‌انجیری من خاکش    |  |
|  |  | 🌿 مونسترای پذیرایی               |  |  |      رس سنگینه، کود چی بدم؟    |  |
|  |  | گونه: برگ‌انجیری | بستر: خاک رسی   |  |  |                                  |  |
|  |  | وضعیت: ⚠️ خطر پوسیدگی ریشه       |  |  |  🤖 گیاه‌پزشک:                    |  |
|  |  | [ 💧 ثبت آبیاری ] [ 💊 برنامه کود] |  |  |  ⛔ [بنر تریاژ: توقف کوددهی]     |  |
|  |  +---------------------------------+  |  |  خاک رسی برای مونسترا باعث خفگی   |  |
|  |                                       |  |  ریشه می‌شود. ابتدا خاک را به     |  |
|  |  +---------------------------------+  |  |  آروئید میکس تغییر دهید.         |  |
|  |  | 🍋 درخت لیمو ترش                  |  |  |                                  |  |
|  |  | فاز: گل‌دهی | بستر: کوکوپیت      |  |  |  📅 [تقویم تعاملی ۴ هفته‌ای]     |  |
|  |  | وضعیت: ✅ پایدار (برنامه فعال)   |  |  |  • هفته ۱: فروت‌ست (Ca-B + Zn)   |  |
|  |  +---------------------------------+  |  |  • هفته ۲: فسفر بالا (10-52-10)  |  |
|  |                                       |  |                                  |  |
|  |  [ ➕ افزودن گیاه جدید به باغچه ]      |  |  [ چیپ‌های پاسخ سریع: خاک را عوض کردم ] |
|  +---------------------------------------+  +----------------------------------+  |
|                                                                                   |
+-----------------------------------------------------------------------------------+

```

---

### ۹.۲. ماژول‌ها و صفحات اصلی کلاینت وب

#### ۱. ماژول کلینیک و چت تشخیصی هوشمند (Interactive Diagnostic Chat)

- **استریم پیام‌ها و ویجت‌های تعاملی ساختاریافته (Rich Widget Rendering):**
- **بنر تریاژ ریسک (`RiskTriageBanner`):** در صورت دریافت `risk_level == 'CRITICAL_BLOCKER'`، یک بنر قرمز رنگ برجسته با آیکون خطر نمایش داده می‌شود که دلایل بیولوژیکی خفگی ریشه و دستور تعویض خاک را تفکیک می‌کند.
- **ویجت جدول کودی ۴ هفته‌ای (`FourWeekScheduleCard`):** رندر کارت‌های هفته به هفته شامل:
- نشان (Badge) فرمول کودی اختصاصی (مانند `10-10-30 پتاس بالا` یا `10-52-10`).
- تگ‌های مکمل‌های الزامی (`Cal-Mag`, `Silica`, `Humic Acid`) با دوز مصرفی دقیق به سی‌سی/گرم.
- چک‌باکس تعاملی «انجام شد» برای ثبت خودکار رویداد در پرونده دوقلوی دیجیتال.

- **چیپ‌های پر کردن سریع اطلاعات (`Quick Slot Chips`):** در صورتی که ایجنت سوال تشخیصی بپرسد (مثلاً: «بستر گیاه شما چیست؟»)، چیپ‌های قابل کلیک (مانند `کوکوپیت و پرلیت`، `خاک رسی سنگین`، `آروئید میکس سبک`) زیر پیام ظاهر می‌شوند تا کاربر بدون تایپ طولانی پاسخ دهد.

#### ۲. ماژول باغچه دیجیتال (Digital Twin Garden Dashboard)

- **کارت هوشمند گیاه (`DigitalTwinPlantCard`):**
- نمایش نام مستعار، گونه، تصویر گیاه، نوع بستر و وضعیت فعلی (`HEALTHY`، `ROOT_ROT_RISK`، `PEST`).
- نوار زمان‌بندی آخرین آبیاری و کوددهی با هشدار هوشمند نوبت بعدی.
- دکمه‌های کنش سریع (Quick Actions): `ثبت آبیاری امروز`، `ثبت کوددهی`، `مشاهده پرونده کامل`، `شروع گفتگوی تشخیصی درباره این گیاه`.

- **فرم افزودن/ویرایش گیاه (`PlantProfileModal`):**
- منوهای دراپ‌داون متصل به API متادیتای پایگاه دانش (`/api/v1/kb/*`) جهت انتخاب گونه، بستر، صفات (ابلق بودن) و فاز رشدی.

#### ۳. ماژول تقویم چرخشی و یادآور مراقبت (Care & Feeding Calendar)

- نمایش نمای تقویمی ماهانه و هفتگی برای تمام گیاهان باغچه کاربر.
- تفکیک رنگی رویدادهای «آبیاری خالص»، «کوددهی اصلی NPK»، «مصرف مکمل و اسید هیومیک» و «نوبت شستشوی بستر (Flush)».

#### ۴. ماژول کاوشگر پایگاه دانش (Knowledge Base Explorer)

- مرورگر دانشنامه اختصاصی گونه‌ها و تیپ‌های بستر با جدول مقایسه میزان نگهداری آب، هوادهی و خطرات ناشی از خاک‌های سنگین.

---

### ۹.۳. استانداردهای تعاملی و اصول تجربه کاربری (UX Best Practices)

1. **طراحی واکنش‌گرا (Responsive Mobile-First):** چیدمان منعطف برای گوشی، تبلت و دسکتاپ با منوی شناور پایینی (Bottom Navigation) در موبایل و سایدبار در دسکتاپ.
2. **وضعیت‌های بارگذاری و اسکلتون (Skeleton Loading):** استفاده از Skeleton Loader در زمان پردازش استنتاج هوش مصنوعی به جای اسپینرهای خشک.
3. **به‌روزرسانی خوش‌بینانه (Optimistic UI):** ثبت فوری تغییر وضعیت آبیاری و گیاه در رابط کاربری قبل از اتمام درخواست شبکه جهت افزایش چشمگیر حس سرعت.
4. **مدیریت خطاهای آفلاین و اعلان‌ها (Toast Notifications):** نمایش هشدارهای شناور در زمان بروز قطعی ارتباط سرور یا اعتبارسنجی فرم‌ها.

---

## ۱۰. نقشه راه پیاده‌سازی گام‌به‌گام (Implementation Roadmap)

- **فاز ۱ (تکمیل‌شده):** لایه داده، مدل‌های Pydantic V2 و لودر پایگاه دانش YAML با سیستم کشینگ.
- **فاز ۲ (تکمیل‌شده):** لایه دیتابیس PostgreSQL، مدل‌های دوقلوی دیجیتال (`UserPlant` و `PlantEventLog`) و سرویس Async.
- **فاز ۳ (تکمیل‌شده):** گراف تشخیصی LangGraph، استخراج ساختاریافته موجودیت‌ها با OpenAI، تریاژ بستر، ارزیابی امکان‌پذیری و موتور محاسبات تقویم ۴ هفته‌ای.
- **فاز ۴ (تکمیل‌شده):** سرور RESTful در FastAPI، تزریق وابستگی‌ها، روت‌های چت، باغچه دیجیتال، رویدادها و متادیتای پایگاه دانش به همراه تست‌های یکپارچگی.
- **فاز ۵ (فاز جاری): پیاده‌سازی کلاینت وب و تجربه کاربری تعاملی (Frontend Web Client & UI/UX Experience):**
- راه‌اندازی پروژه فرانت‌اند با React/Next.js/Vite + TypeScript + Tailwind CSS.
- ساخت کلاینت API و هوک‌های ارتباط با بک‌اند (`useChat`, `usePlants`, `useKnowledgeBase`).
- پیاده‌سازی کامپوننت‌های تعاملی چت و رندرر ساختاریافته جدول ۴ هفته‌ای و بنرهای تریاژ ریسک.
- پیاده‌سازی داشبورد باغچه دیجیتال، کارت‌های پرونده گیاه و فرم ثبت گیاه جدید.
- تست نهایی سرتاسری (End-to-End) اتصال کلاینت وب به سرور FastAPI.

```

```
