def poll_agnes(video_id):
    headers = {
        "Authorization": f"Bearer {AGNES_API_KEY}",
        "Accept": "application/json"
    }
    
    for i in range(60):
        time.sleep(5)
        try:
            res = requests.get(f"https://apihub.agnes-ai.com/agnesapi?video_id={video_id}&model_name=agnes-video-2.5-flash", headers=headers, timeout=15)
            print(f"[{i+1}] Agnes Durum Yanıtı:", res.text) # Render loglarında ne döndüğünü göreceğiz
            data = res.json()
            
            # API bazen status döner
            status = data.get("status")
            if status == "failed" or status == "error":
                return None
                
            video_url = data.get("video_url") or data.get("url") or data.get("video")
            if video_url:
                return video_url
        except Exception as e:
            print("Poll hatası:", e)
            continue
    return None
