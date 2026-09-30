import os
import uvicorn

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# AI Multi-Model Cascading Fallback Keys (Gemini -> ChatGPT -> Claude -> Local Semantic Engine)
# Keys must be supplied via environment variables / host secrets (.env locally,
# platform-managed env vars in production) -- never hardcoded here.

# Placeholders for ChatGPT and Claude keys (will be used automatically once set)
if not os.environ.get("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = os.environ.get("CHATGPT_API_KEY", "")

if not os.environ.get("ANTHROPIC_API_KEY"):
    os.environ["ANTHROPIC_API_KEY"] = os.environ.get("CLAUDE_API_KEY", "")

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 8010))
    reload = os.environ.get("RELOAD", "false").lower() in ("true", "1")
    print(f"Starting Sutra Press Web Server on http://{host}:{port} ...")
    uvicorn.run("sutra.web.app:app", host=host, port=port, reload=reload)
