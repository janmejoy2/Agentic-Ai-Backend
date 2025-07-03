import yaml
import os
from langchain_google_genai import ChatGoogleGenerativeAI

# Get the directory where this script is located
current_dir = os.path.dirname(os.path.abspath(__file__))
# Go up one level to the parent directory and find integration.yml
config_path = os.path.join(os.path.dirname(current_dir), "integration.yml")

with open(config_path) as f:
    config = yaml.safe_load(f)
GEMINI_API_KEY = config["gemini"]["api_key"]
GEMINI_MODEL = config["gemini"]["model"]

def refine_requirement(raw_req: str) -> str:
    llm = ChatGoogleGenerativeAI(model=GEMINI_MODEL, google_api_key=GEMINI_API_KEY)
    prompt = (
        "Refine the following software development requirement for clarity, precision, and readiness to pass to a code generation AI agent. "
        "Keep it concise, actionable, and comprehensive.\n\n"
        "IMPORTANT: Your output should be a clear, step-by-step modernization plan that covers ALL relevant aspects of the requirement, including but not limited to:\n"
        "- Architecture and design patterns (e.g., layering, REST, service separation)\n"
        "- Data model and persistence (e.g., JPA entities, repositories, database config)\n"
        "- Dependency management (only stable, production-ready dependencies from Maven Central)\n"
        "- Error handling, validation, and logging\n"
        "- Application configuration and environment setup\n"
        "- API/interface design and documentation\n"
        "- Cleanup of legacy or obsolete code\n"
        "- Anticipate and avoid common issues for the chosen technology stack (e.g., missing annotations, dependency conflicts, misconfiguration, etc.)\n"
        "- Ensure the plan is production-ready and minimizes the risk of codegen errors.\n"
        f"{raw_req}"
    )
    result = llm.invoke(prompt).content
    if not isinstance(result, str):
        result = str(result)
    return result
