import os
import time
import requests
from threading import Thread
from flask import Flask

# Flask ile mini bir web sunucusu açıyoruz ki Render servisi ayakta tutsun
app = Flask('')

@app.route('/')
def home():
    return "Bot aktif ve çalışıyor!"

def run_web():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# Bilgileriniz
BOT_TOKEN = "8951343304:AAEEhyKFAPlFhJg9pp6AUsoM1EUnvKZoNNM"
AGNES_API_KEY = "sk-mzWSliOu65udCf0Wgwr06GK3Koa9cLHTPJnEASpANeEUP79U"
CHAT_ID = "-1004316545825"

BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

def send_message(chat_id, text):
    requests.post(f"{BASE_URL}/sendMessage", json={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    })

def send_video_to_channel(video_url, video_id):
    text = f"🎬 *Yeni Benzero AI Videosu Hazır!*\n\n🆔 *Video ID:* `{video_id}`\n\n⬇️ *İzle / İndir:*\n{video_url}"
    requests.post(f"{BASE_URL}/sendMessage", json={
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    })

def generate_video(prompt, photo_url):
    img_data = requests.get(photo_url).content
    import base64
    base64_image = "data:image/jpeg;base64," + base64.b64encode(img_data).decode("utf-8")

    payload = {
        "model": "agnes-video-2.5-flash",
        "prompt": prompt,
        "mode": "reference",
        "seconds": "5",
        "size": "720P",
        "aspect_ratio": "9:16",
        "images": [base64_image],
        "n": 1
    }

    headers = {
        "Authorization": f"Bearer {AGNES_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    res = requests.post("https://apihub.agnes-ai.com/v1/videos", json=payload, headers=headers)
    data = res.json()
    return data.get("video_id") or data.get("id")

def poll_agnes(video_id, chat_id):
    headers = {
        "Authorization": f"Bearer {AGNES_API_KEY}",
        "Accept": "application/json"
    }
    
    for _ in range(60):
        time.sleep(5)
        res = requests.get(f"https://apihub.agnes-ai.com/agnesapi?video_id={video_id}&model_name=agnes-video-2.5-flash", headers=headers)
        data = res.json()
        
        video_url = data.get("video_url") or data.get("url") or data.get("video")
        if video_url:
            send_message(chat_id, "✅ Videonuz başarıyla tamamlandı ve kanala iletildi!")
            send_video_to_channel(video_url, video_id)
            return
            
    send_message(chat_id, "❌ Video oluşturma zaman aşımına uğradı.")

def check_updates():
    offset = 0
    print("Bot çalışıyor ve Telegram mesajları dinleniyor...")
    while True:
        try:
            res = requests.get(f"{BASE_URL}/getUpdates", params={"offset": offset, "timeout": 30})
            data = res.json()
            
            if data.get("ok"):
                for result in data.get("result", []):
                    offset = result["update_id"] + 1
                    message = result.get("message", {})
                    chat_id = message.get("chat", {}).get("id")
                    text = message.get("text") or message.get("caption") or ""
                    
                    if text == "/start":
                        send_message(chat_id, "🎬 *Benzero AI Botuna Hoş Geldiniz!*\n\nVideo üretmek için bana bir **fotoğraf** gönderin ve açıklama kısmına **promptunuzu** yazın.")
                    
                    elif "photo" in message:
                        send_message(chat_id, "⏳ Fotoğrafınız alındı, video işleniyor. Lütfen bekleyin...")
                        photo_id = message["photo"][-1]["file_id"]
                        file_res = requests.get(f"{BASE_URL}/getFile?file_id={photo_id}").json()
                        file_path = file_res["result"]["file_path"]
                        photo_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
                        
                        prompt = text if text else "Photorealistic natural video"
                        
                        video_id = generate_video(prompt, photo_url)
                        if video_id:
                            send_message(chat_id, f"🎬 Video kuyruğa eklendi! (ID: `{video_id}`). Hazır olunca kanala gidecek.")
                            poll_agnes(video_id, chat_id)
                        else:
                            send_message(chat_id, "❌ Agnes AI video isteğini reddetti.")
                            
        except Exception as e:
            print("Hata:", e)
            time.sleep(5)

if __name__ == "__main__":
    # Web sunucusunu arka planda (thread) başlat
    t = Thread(target=run_web)
    t.start()
    # Telegram dinleyicisini ana döngüde çalıştır
    check_updates()
