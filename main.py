# whatsapp_gemini_bot.py
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import requests
import os
from dotenv import load_dotenv
import uvicorn

load_dotenv()

VONAGE_API_KEY = os.getenv("VONAGE_API_KEY")
VONAGE_API_SECRET = os.getenv("VONAGE_API_SECRET")
VONAGE_SANDBOX_NUMBER = os.getenv("VONAGE_SANDBOX_NUMBER")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

app = FastAPI(title="WhatsApp Gemini Bot with Web UI")
templates = Jinja2Templates(directory="templates")


def get_gemini_response(user_input: str) -> str:
    url = "https://api.gemini.ai/v1/response"
    headers = {"Authorization": f"Bearer {GEMINI_API_KEY}"}
    payload = {"prompt": user_input}
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        return response.json().get("response", "عذرًا، لم أفهم الرسالة.")
    except Exception as e:
        print("Gemini error:", e)
        return "حدث خطأ في معالجة الرسالة."


def send_whatsapp(to_number: str, message: str):
    url = "https://messages-sandbox.nexmo.com/v1/messages"
    headers = {
        "Authorization": f"Basic {VONAGE_API_KEY}:{VONAGE_API_SECRET}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    data = {
        "from": {"type": "whatsapp", "number": VONAGE_SANDBOX_NUMBER},
        "to": {"type": "whatsapp", "number": to_number},
        "message": {"content": {"type": "text", "text": message}}
    }
    try:
        res = requests.post(url, json=data, headers=headers, timeout=10)
        print("Sent to WhatsApp:", res.status_code, res.text)
    except Exception as e:
        print("Vonage error:", e)


# Webhook لاستقبال رسائل الواتساب
@app.post("/webhook")
async def whatsapp_webhook(req: Request):
    data = await req.json()
    try:
        user_number = data["from"]["number"]
        user_text = data["message"]["content"]["text"]
    except KeyError:
        return {"status": "ignored"}

    bot_reply = get_gemini_response(user_text)
    send_whatsapp(user_number, bot_reply)
    return {"status": "ok"}


# واجهة الويب لإرسال الرسائل
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/send_message")
async def send_message(request: Request, number: str = Form(...), message: str = Form(...)):
    send_whatsapp(number, message)
    return RedirectResponse("/", status_code=303)


# دالة main لتشغيل السيرفر
def main():
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
