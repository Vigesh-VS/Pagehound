from google import genai

from app import config

client = genai.Client(api_key=config.GEMINI_API_KEY)
for model in client.models.list():
    actions = getattr(model, "supported_actions", None) or []
    if "generateContent" in actions:
        print(model.name)
