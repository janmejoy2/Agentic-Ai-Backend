import yaml
from langchain_google_genai import ChatGoogleGenerativeAI

with open("integration.yml") as f:
    config = yaml.safe_load(f)
GEMINI_API_KEY = config["gemini"]["api_key"]

def refine_requirement(raw_req: str) -> str:
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash-002", google_api_key=GEMINI_API_KEY)
    prompt = (
        "Refine the following software development requirement for clarity, precision, "
        "and readiness to pass to a code generation AI agent. Keep it concise and actionable:\n\n"
        f"{raw_req}"
    )
    return llm.invoke(prompt)
