import os
import uvicorn

# AI Multi-Model Cascading Fallback Keys (Gemini -> ChatGPT -> Claude -> Local Semantic Engine)
if not os.environ.get("GEMINI_API_KEY"):
    os.environ["GEMINI_API_KEY"] = "AQ.Ab8RN6IDH607A1KEwR4Gmgn6FYDIzlTydHMkrOKrPZYaBPn0sA"

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
