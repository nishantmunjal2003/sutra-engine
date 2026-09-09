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
    print("Starting Sutra Press Web Server on http://127.0.0.1:8010 ...")
    uvicorn.run("sutra.web.app:app", host="127.0.0.1", port=8010, reload=True)
