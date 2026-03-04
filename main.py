import os
import requests
import json
import uvicorn
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

load_dotenv()

# --- الإعدادات من ملف .env أو Render ---
VONAGE_API_KEY = os.getenv("VONAGE_API_KEY")
VONAGE_API_SECRET = os.getenv("VONAGE_API_SECRET")
VONAGE_SANDBOX_NUMBER = os.getenv("VONAGE_SANDBOX_NUMBER")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# رابط Gemini 2.5 Flash المحدث
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

app = FastAPI(title="WhatsApp Gemini 2.5 Bot")
templates = Jinja2Templates(directory="templates")

# --- دالة الحصول على رد من Gemini 2.5 ---
def get_gemini_2_5_response(user_input: str) -> str:
    # إعداد بيانات الطلب مع تعليمات النظام (System Instruction) لجعل البوت أفضل
    payload = {
        "contents": [
            {
                "parts": [{"text": user_input}]
            }
        ],
        "system_instruction": {
            "parts": [{"text": "أنت مساعد ذكي ولطيف تتواصل مع المستخدمين عبر واتساب باللغة العربية."}]
        },
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 800
        }
    }
    
    try:
        response = requests.post(
            GEMINI_URL,
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            timeout=15
        )
        response.raise_for_status()
        result = response.json()
        
        # استخراج النص البرمجي للرد
        return result["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print(f"Gemini 2.5 Error: {e}")
        return "عذرًا، واجهت مشكلة فنية بسيطة. حاول مراسلتي لاحقًا!"

# --- دالة إرسال رسالة واتساب (Vonage) ---
def send_whatsapp(to_number: str, message: str):
    url = "https://messages-sandbox.nexmo.com/v1/messages"
    # التوثيق الصحيح لتجنب خطأ 401
    auth = (VONAGE_API_KEY, VONAGE_API_SECRET)
    
    data = {
        "from": VONAGE_SANDBOX_NUMBER,
        "to": to_number,
        "message_type": "text",
        "text": message,
        "channel": "whatsapp"
    }
    
    try:
        res = requests.post(url, json=data, auth=auth, timeout=10)
        print(f"Vonage Log: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"Error sending WhatsApp: {e}")

# --- مسارات التطبيق (Endpoints) ---

@app.post("/webhook")
async def webhook(req: Request):
    """استقبال الرسائل من واتساب"""
    try:
        data = await req.json()
        user_number = data["from"]
        user_text = data["message"]["content"]["text"]
        
        # جلب الرد من Gemini 2.5
        reply = get_gemini_2_5_response(user_text)
        
        # إرسال الرد للمستخدم
        send_whatsapp(user_number, reply)
        return {"status": "success"}
    except:
        return {"status": "ignored"}

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/send_message")
async def manual_send(number: str = Form(...), message: str = Form(...)):
    send_whatsapp(number, message)
    return RedirectResponse(url="/", status_code=303)

if __name__ == "__main__":
    # الحصول على المنفذ تلقائياً من Render
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
