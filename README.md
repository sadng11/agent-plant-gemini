# 🌱 سرور و ایجنت هوشمند گیاه‌پزشک (PhytoAgent Server)

مستندات جامع نصب، پیکربندی و راه‌اندازی بخش سرور و وب‌سرویس **FastAPI** برای سامانه تخصصی و هوشمند **PhytoAgent** (تشخیص، تغذیه و مدیریت دوقلوی دیجیتال گیاهان).

---

## 📋 فهرست مطالب
- [معرفی و ویژگی‌های کلیدی](#-معرفی-و-ویژگیهای-کلیدی)
- [پشته فناوری (Tech Stack)](#-پشته-فناوری-tech-stack)
- [پیش‌نیازها](#-پیشنیازها)
- [مراحل نصب و راه‌اندازی سریع](#-مراحل-نصب-و-راهاندازی-سریع)
  - [۱. کلون یا ورود به مخزن](#۱-کلون-یا-ورود-به-مخزن)
  - [۲. ساخت و فعال‌سازی محیط مجازی (Virtual Environment)](#۲-ساخت-و-فعالسازی-محیط-مجازی-virtual-environment)
  - [۳. نصب وابستگی‌های پایتون](#۳-نصب-وابستگیهای-پایتون)
  - [۴. تنظیم متغیرهای محیطی (`.env`)](#۴-تنظیم-متغیرهای-محیطی-env)
- [پیکربندی پایگاه داده](#-پیکربندی-پایگاه-داده)
  - [گزینه الف: PostgreSQL (پیشنهادی برای توسعه اصلی و پروداکشن)](#گزینه-الف-postgresql-پیشنهادی-برای-توسعه-اصلی-و-پروداکشن)
  - [گزینه ب: SQLite ناهمگام (برای تست و راه‌اندازی سریع بدون دیتابیس خارجی)](#گزینه-ب-sqlite-ناهمگام-برای-تست-و-راهاندازی-سریع-بدون-دیتابیس-خارجی)
- [اجرای سرور FastAPI](#-اجرای-سرور-fastapi)
- [مستندات تعاملی API (Swagger / ReDoc)](#-مستندات-تعاملی-api-swagger--redoc)
- [مسیرهای اصلی و اندپوینت‌های API](#-مسیرهای-اصلی-و-اندپوینتهای-api)
- [اجرای تست‌های خودکار (Testing)](#-اجرای-تستهای-خودکار-testing)
- [ساختار فایل‌ها و پوشه‌بندی سرور](#-ساختار-فایلها-و-پوشهبندی-سرور)
- [اتصال به کلاینت فرانت‌اند (CORS)](#-اتصال-به-کلاینت-فرانتاند-cors)
- [عیب‌یابی و نکات متداول (Troubleshooting)](#-عیبیابی-و-نکات-متداول-troubleshooting)

---

## 🌟 معرفی و ویژگی‌های کلیدی

سرور **PhytoAgent** یک موتور هوش مصنوعی و وب‌سرویس بک‌اند با معماری لایه‌ای و ناهمگام (Async) است که قابلیت‌های زیر را ارائه می‌دهد:

1. **موتور استدلال و گراف سلامت گیاه (LangGraph Engine):** مدل استیت ماشین جهت تریاژ ریسک، اعتبارسنجی شرایط فیزیولوژیکی و صدور تقویم تغذیه ۴ هفته‌ای.
2. **پایگاه دانش لایه‌ای (Botanical Knowledge Base):** مدیریت شناسنامه گونه‌ها، فرمولاسیون تغذیه بر اساس بستر کشت، صفات مورفولوژیکی (مثل ابلق بودن) و فازهای فنولوژیکی.
3. **دوقلوی دیجیتال گیاهان (Digital Twin Garden):** ذخیره و بازیابی سوابق سلامت، شرایط نوری، رطوبت، گلدان و تاریخچه رویدادهای مراقبت (آبیاری، کوددهی، تعویض خاک).
4. **موتور فرمول‌بندی اگروونومی قطعی (Deterministic Agronomy Engine):** محاسبه مقادیر دقیق کوددهی (EC، نسبت NPK، اصلاح‌کننده‌ها) بدون توهم مدل‌های زبانی.

---

## 🛠 پشته فناوری (Tech Stack)

- **زبان:** Python 3.11+
- **فریم‌ورک وب:** FastAPI 0.111+
- **سرور ASGI:** Uvicorn 0.30+
- **مدل‌سازی و اعتبارسنجی داده:** Pydantic V2 & Pydantic-Settings
- **پایگاه داده و ORM:** SQLAlchemy 2.0 (Async) + `asyncpg` (PostgreSQL) / `aiosqlite` (SQLite)
- **ارکستراسیون ایجنت:** LangChain Core & LangGraph
- **موتور استخراج هوشمند و LLM:** OpenAI API (پشتیبانی از GPT-4o یا سایر مدل‌های سازگار با OpenAI Endpoint)
- **تست:** Pytest & Pytest-Asyncio

---

## 📌 پیش‌نیازها

قبل از شروع، مطمئن شوید ابزارهای زیر روی سیستم شما نصب هستند:

- **Python:** نسخه **3.11 یا بالاتر**
- **Git** (جهت مدیریت سورس کد)
- **PostgreSQL:** نسخه 14+ (اختیاری در صورت استفاده از SQLite محلی)
- پکیج‌منیجر `pip` یا `uv`

---

## 🚀 مراحل نصب و راه‌اندازی سریع

### ۱. کلون یا ورود به مخزن

اگر پروژه را کلون نکرده‌اید:
```bash
git clone <repository-url>
cd plant-agent-gemini
```

---

### ۲. ساخت و فعال‌سازی محیط مجازی (Virtual Environment)

توصیه اکید می‌شود از یک محیط مجازی تمیز پایتون استفاده کنید:

#### در لینوکس / مک (Linux / macOS):
```bash
python3 -m venv .venv
source .venv/bin/activate
```

#### در ویندوز (Windows PowerShell):
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

#### در ویندوز (Command Prompt):
```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

---

### ۳. نصب وابستگی‌های پایتون

با فعال بودن محیط مجازی، پکیج‌های مورد نیاز را نصب کنید:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

یا در حالت توسعه و نصبی قابل ویرایش (Editable):
```bash
pip install -e ".[dev]"
```

---

### ۴. تنظیم متغیرهای محیطی (`.env`)

یک کپی از فایل نمونه `.env.example` ایجاد کرده و نام آن را `.env` بگذارید:

```bash
cp .env.example .env
```

سپس فایل `.env` را باز کرده و پارامترهای لازم را مطابق جدول زیر تنظیم کنید:

| نام متغیر | مقدار پیش‌فرض | توضیحات |
| :--- | :--- | :--- |
| `PROJECT_NAME` | `"PhytoAgent"` | نام پروژه و عنوان نمایش داده شده در مستندات |
| `VERSION` | `"0.1.0"` | نسخه نرم‌افزار API |
| `DEBUG` | `false` | حالت دیباگ لاگ‌ها (در محیط توسعه `true` قرار دهید) |
| `API_V1_STR` | `"/api/v1"` | پیشوند روت‌های نگارش اول API |
| `CORS_ORIGINS` | `["*"]` | آدرس‌های مجاز کلاینت‌های فرانت‌اند |
| `DATABASE_URL` | `postgresql+asyncpg://...` | آدرس اتصال به پایگاه داده (PostgreSQL یا SQLite) |
| `OPENAI_API_KEY` | `""` | کلید دسترسی OpenAI (جهت پردازش زبان طبیعی و LLM Extractor) |
| `OPENAI_BASE_URL` | `"https://api.openai.com/v1"` | آدرس پایه سرویس هوش مصنوعی |
| `OPENAI_MODEL_NAME` | `"gpt-4o"` | مدل پیش‌فرض برای تحلیل و استخراج موجودیت‌ها |

---

## 🗄 پیکربندی پایگاه داده و مهاجرت‌ها (Database & Migrations)

سامانه به صورت خودکار در زمان استارت سرور (`lifespan`) یا از طریق دستور اختصاصی CLI، جدول‌های پایگاه داده را ایجاد و همگام‌سازی می‌کند.

### ۱. اجرای دستی ساخت جدول‌ها و مهاجرت اولیه (CLI Tool)

برای ساخت فوری و مستقیم جدول‌ها در PostgreSQL یا SQLite می‌توانید دستور زیر را اجرا کنید:

```bash
python -m app.db.init_db
```

در صورت نیاز به حذف جدول‌های قبلی و ساخت مجدد (Fresh Schema):
```bash
python -m app.db.init_db --drop
```

---

### ۲. تنظیم نوع پایگاه داده

#### گزینه الف: PostgreSQL (پیشنهادی برای توسعه اصلی و پروداکشن)

۱. یک دیتابیس جدید در سرور PostgreSQL خود ایجاد کنید:
```sql
CREATE DATABASE plant_agent;
```

۲. در فایل `.env`، متغیر `DATABASE_URL` را تنظیم کنید:
```env
DATABASE_URL=postgresql+asyncpg://<db_user>:<db_password>@<db_host>:5432/plant_agent
```
*مثال:*
```env
DATABASE_URL=postgresql+asyncpg://sadng:sadng11@localhost:5432/plant_agent
```

---

#### گزینه ب: SQLite ناهمگام (برای تست و راه‌اندازی سریع بدون دیتابیس خارجی)

اگر نمی‌خواهید دیتابیس PostgreSQL نصب کنید، می‌توانید از درایور async SQLite استفاده نمایید. کافیست مقدار زیر را در `.env` قرار دهید:

```env
DATABASE_URL=sqlite+aiosqlite:///./plant_agent.db
```

---

## ⚡ اجرای سرور FastAPI

برای اجرای سرور در حالت توسعه همراه با قابلیت بارگذاری خودکار تغییرات (Hot Reload):

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

پس از اجرای موفق، خروجی مشابه زیر در ترمینال مشاهده خواهید کرد:
```text
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Initializing PhytoAgent Knowledge Base...
INFO:     Knowledge Base loaded successfully.
INFO:     Verifying database schema...
INFO:     Database schema initialized successfully.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

---

## 📚 مستندات تعاملی API (Swagger / ReDoc)

پس از بالا آمدن سرور، مستندات کامل API از طریق آدرس‌های زیر در مرورگر در دسترس است:

- **رابط تعاملی Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **مستندات جایگزین ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **بررسی سلامت سرور (Health Check):** [http://localhost:8000/health](http://localhost:8000/health)
- **اطلاعات پایه سیستم (Root):** [http://localhost:8000/](http://localhost:8000/)

---

## 📡 مسیرهای اصلی و اندپوینت‌های API

کلیه روت‌ها با پیشوند `/api/v1` در دسترس هستند:

### ۱. چت و تشخیص هوشمند گیاه‌پزشک (`/api/v1/chat`)
- **`POST /api/v1/chat`**: ارسال پیام متنی کاربر برای تشخیص وضعیت، تریاژ خطر و دریافت برنامه زمان‌بندی ۴ هفته‌ای کوددهی و آبیاری.

```bash
curl -X POST "http://localhost:8000/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_123",
    "message": "گیاه برگ انجبری من در خاک پیت‌ماس و کوکوپیت هست و برگ‌ها کمی زرد شده‌اند."
  }'
```

### ۲. مدیریت باغچه دیجیتال و دوقلوی گیاه (`/api/v1/plants`)
- **`GET /api/v1/plants?user_id=...`**: دریافت فهرست گیاهان ثبت‌شده برای یک کاربر.
- **`POST /api/v1/plants`**: ثبت پرونده گیاه جدید (گونه، بستر، گلدان، فاز رشد، ویژگی‌ها).
- **`GET /api/v1/plants/{plant_id}`**: دریافت مشخصات کامل یک گیاه.
- **`PATCH /api/v1/plants/{plant_id}`**: به‌روزرسانی پارامترهای گیاه (خاک، فاز رشد، وضعیت سلامت).
- **`DELETE /api/v1/plants/{plant_id}`**: حذف پرونده گیاه و تاریخچه رویدادهای آن.
- **`POST /api/v1/plants/{plant_id}/events`**: ثبت لاگ رویدادهای مراقبتی (آبیاری، کوددهی، اخطار).
- **`GET /api/v1/plants/{plant_id}/events`**: دریافت تاریخچه رویدادهای گیاه به ترتیب زمان.

### ۳. پایگاه دانش گیاه‌شناسی (`/api/v1/kb`)
- **`GET /api/v1/kb/species`**: فهرست خلاصه تمامی گونه‌های ثبت‌شده در پایگاه دانش.
- **`GET /api/v1/kb/species/{species_id}`**: دریافت پروفایل بیولوژیکی و آستانه‌های تحمل کامل گونه.
- **`GET /api/v1/kb/substrates`**: فهرست بسترها و ضریب‌های غلظت و دوره آبیاری.
- **`GET /api/v1/kb/traits`**: قوانین و محدودیت‌های تغذیه‌ای برای صفات گیاه (مانند ابلق بودن).
- **`GET /api/v1/kb/phases`**: قوانین تغذیه‌ای فازهای مختلف رشد (رویشی، استراحت، گلدهی).

---

## 🧪 اجرای تست‌های خودکار (Testing)

پروژه دارای مجموعه تست‌های کامل برای اعتبارسنجی قوانین اگروونومی، لودر پایگاه دانش، لایه پایگاه داده، گراف LangGraph و وب‌سرویس‌های FastAPI است.

### اجرای کلیه تست‌ها:
```bash
pytest
```

### اجرای تست با نمایش جزئیات و خروجی لاگ‌ها:
```bash
pytest -v -s
```

### اجرای دسته‌بندی خاصی از تست‌ها:
```bash
# تست‌های وب‌سرویس و API
pytest tests/test_api.py

# تست‌های موتور استدلال LangGraph
pytest tests/test_plant_graph.py

# تست‌های دیتابیس دوقلوی دیجیتال
pytest tests/test_digital_twin_db.py

# تست‌های محاسبات اگروونومی و تغذیه
pytest tests/test_agronomy_engine.py

# تست‌های لودر فایل‌های YAML پایگاه دانش
pytest tests/test_kb_loader.py
```

---

## 📂 ساختار فایل‌ها و پوشه‌بندی سرور

```text
plant-agent-gemini/
├── app/
│   ├── main.py                     # نقطه ورود وب‌سرویس FastAPI و مدیریت Lifespan
│   ├── api/
│   │   ├── deps.py                 # Dependency Injection سشن دیتابیس
│   │   └── v1/
│   │       ├── router.py           # تجمیع روت‌های نسخه ۱
│   │       └── endpoints/
│   │           ├── chat.py         # اندپوینت چت هوشمند و تحلیل LangGraph
│   │           ├── plants.py       # اندپوینت‌های مدیریت دوقلوی دیجیتال گیاهان
│   │           └── knowledge_base.py # اندپوینت‌های پایگاه دانش گیاهی
│   ├── agents/
│   │   └── plant_graph.py          # پیاده‌سازی گراف استیت‌ماشین با LangGraph
│   ├── core/
│   │   ├── config.py               # مدیریت تنظیمات با Pydantic Settings
│   │   ├── kb_loader.py            # لودر و اعتبارسنجی فایل‌های YAML پایگاه دانش
│   │   └── agronomy_engine.py      # موتور محاسبات ریاضی و قوانین تغذیه
│   ├── db/
│   │   └── session.py              # ساخت Async Engine و Session Factory دیتابیس
│   ├── models/
│   │   ├── agent_state.py          # مدل وضعیت داخلی ایجنت
│   │   ├── api_schemas.py          # مدل‌های Request/Response اسکیماهای Pydantic
│   │   ├── db_models.py            # مدل‌های ORM دیتابیس (Plant, EventLog, ...)
│   │   └── knowledge_base.py       # اسکیماهای داده‌ای شناسنامه و قوانین پایگاه دانش
│   └── services/
│       ├── digital_twin_service.py # سرویس مدیریت پرونده و سوابق دوقلوی دیجیتال
│       └── extractor_service.py    # سرویس استخراج هوشمند موجودیت‌ها و اسلات‌ها
├── knowledge_base/                 # پایگاه دانش ساخت‌یافته گیاهی (YAML)
│   ├── species/                    # شناسنامه‌های تخصصی گونه‌ها
│   └── global/                     # قوانین بسترهای کشت، صفات و فازها
├── tests/                          # تست‌های خودکار یکپارچگی و واحد
├── .env.example                    # نمونه فایل تنظیمات متغیرهای محیطی
├── requirements.txt                # فهرست وابستگی‌های پایتون
├── pyproject.toml                  # فایل پیکربندی پروژه پایتون
└── AGENT.md                        # مستندات تخصصی معماری و طراحی سیستم
```

---

## 🌐 اتصال به کلاینت فرانت‌اند (CORS)

اگر بخش فرانت‌اند (مثلاً با Vue.js یا React + Vite) روی پورت دیگری (مانند `5173` یا `3000`) اجرا می‌شود، اطمینان حاصل کنید که آدرس فرانت‌اند در آرایه `CORS_ORIGINS` در فایل `.env` قرار داشته باشد:

```env
CORS_ORIGINS=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"]
```

همچنین می‌توانید در محیط توسعه برای رفع محدودیت‌ها از `["*"]` استفاده کنید.

---

## 💡 عیب‌یابی و نکات متداول (Troubleshooting)

### ۱. خطای اتصال به پایگاه داده PostgreSQL
- مطمئن شوید سرویس PostgreSQL فعال است (`systemctl status postgresql` یا بررسی در ابزار Docker/لوکال).
- نام کاربری، رمز عبور، پورت و نام دیتابیس در `DATABASE_URL` صحیح باشد.
- برای رفع موقت مشکل در محیط توسعه، می‌توانید از `DATABASE_URL=sqlite+aiosqlite:///./plant_agent.db` استفاده کنید.

### ۲. خطای پکیج‌های ناهمگام (Async Drivers)
- مطمئن شوید پکیج `asyncpg` (برای PostgreSQL) یا `aiosqlite` (برای SQLite) نصب شده باشد:
  ```bash
  pip install asyncpg aiosqlite
  ```

### ۳. عدم دسترسی به API Key هوش مصنوعی (OpenAI)
- در صورت عدم وارد کردن `OPENAI_API_KEY` در فایل `.env`، موتور استخراج به صورت خودکار به حالت Rule-Based / Regex fallback سوئیچ کرده و سرور بدون خطا بالا می‌آید؛ اما برای بهترین دقت در درک زبان طبیعی، کلید OpenAI را در `.env` قرار دهید.

---

## 📄 لایسنس
کلیه حقوق این پروژه متعلق به تیم توسعه **PhytoAgent** می‌باشد.
