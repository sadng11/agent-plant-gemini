#!/usr/bin/env bash
# run_dev.sh - اجرای همزمان بک‌اند FastAPI و فرانت‌اند Vue 3

echo "🌿 در حال راه‌اندازی سامانه هوشمند فیتوایجنت..."

# اجرای بک‌اند در پس‌زمینه
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8013 --reload &
BACKEND_PID=$!
echo "🚀 سرور بک‌اند روی http://localhost:8013 (PID: $BACKEND_PID) فعال شد."

# اجرای فرانت‌اند
cd frontend
npm run dev &
FRONTEND_PID=$!
echo "🎨 کلاینت فرانت‌اند روی http://localhost:5173 (PID: $FRONTEND_PID) فعال شد."

# مدیریت توقف هر دو پروسس با فشردن Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID; exit" INT TERM EXIT
wait