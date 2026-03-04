import os
import requests
import uvicorn
import google.generativeai as genai
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()

# إعداد مفاتيح البيئة
VONAGE_API_KEY = os.getenv("VONAGE_API_KEY")
VONAGE_API_SECRET = os.getenv("VONAGE_API_SECRET")
VONAGE_SANDBOX_NUMBER = os.getenv("VONAGE_SANDBOX_NUMBER") # مثال: 14157386170
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# إعداد مكتبة Gemini الرسمية
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

app = FastAPI(title="WhatsApp Gemini Bot")

# إعداد القوالب والملفات الثابتة (تجنب خطأ 404 للـ CSS)
templates = Jinja2Templates(directory="templates")
# إذا كان لديك مجلد static، فقم بإلغاء تعليق السطر التالي:
# app.mount("/static", StaticFiles(directory="static"), name="static")

def get_gemini_response(user_input: str) -> str:
    """الحصول على رد من ذكاء جوجل الاصطناعي"""
    try:
        response = model.generate_content(user_input)
        return response.text
    except Exception as e:
        print(f"Gemini Error: {e}")
        return "عذرًا، حدث خطأ أثناء معالجة طلبك عبر الذكاء الاصطناعي."

def send_whatsapp(to_number: str, message: str):
    """إرسال رسالة واتساب عبر Vonage Sandbox"""
    url = "https://messages-sandbox.nexmo.com/v1/messages"
    
    # إصلاح مشكلة التوثيق: نستخدم auth=(key, secret) ليقوم requests بالتشفير تلقائياً
    auth_credentials = (VONAGE_API_KEY, VONAGE_API_SECRET)
    
    payload = {
        "from": VONAGE_SANDBOX_NUMBER,
        "to": to_number,
        "message_type": "text",
        "text": message,
        "channel": "whatsapp"
    }
    
    try:
        res = requests.post(url, json=payload, auth=auth_credentials, timeout=10)
        print(f"Response from Vonage: {res.status_code} - {res.text}")
        return res.status_code
    except Exception as e:
        print(f"Vonage API Error: {e}")
        return None

# --- المسارات (Routes) ---

@app.post("/webhook")
async def whatsapp_webhook(req: Request):
    """استقبال الرسائل من واتساب"""
    try:
        data = await req.json()
        # هيكل بيانات Vonage Sandbox
        user_number = data["from"]
        user_text = data["message"]["content"]["text"]
        
        # الحصول على رد الذكاء الاصطناعي
        bot_reply = get_gemini_response(user_text)
        
        # إرسال الرد للمستخدم
        send_whatsapp(user_number, bot_reply)
        
        return {"status": "success"}
    except Exception as e:
        print(f"Webhook Error: {e}")
        return {"status": "ignored"}

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """واجهة الويب البسيطة"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/send_message")
async def web_send_message(number: str = Form(...), message: str = Form(...)):
    """إرسال رسالة يدوية من واجهة الويب"""
    send_whatsapp(number, message)
    return RedirectResponse(url="/", status_code=303)

if __name__ == "__main__":
    # ملاحظة: تأكد أن اسم الملف هو main.py إذا كنت تستخدم "main:app"
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
