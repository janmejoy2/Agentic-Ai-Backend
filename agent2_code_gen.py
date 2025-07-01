import os
import yaml
from langchain_google_genai import ChatGoogleGenerativeAI

with open("integration.yml") as f:
    config = yaml.safe_load(f)
GEMINI_API_KEY = config["gemini"]["api_key"]
LOCAL_REPO_DIR = config["repository"]["local_dir"]

def get_existing_code(base_dir):
    code_map = []
    for root, _, files in os.walk(base_dir):
        for file in files:
            if file.endswith((".java", ".py", ".js", ".ts", ".xml", ".yml", ".yaml", ".properties")):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        code = f.read()
                        relative_path = os.path.relpath(file_path, base_dir)
                        code_map.append(f"// FILE: {relative_path}\n{code}")
                except Exception as e:
                    print(f"Could not read file: {file_path}. Reason: {e}")
    return "\n\n".join(code_map)

def generate_code(refined_req: str) -> list:
    existing_code = get_existing_code(LOCAL_REPO_DIR)
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash-002", google_api_key=GEMINI_API_KEY)
    prompt = (
        "You are an expert software engineer specializing in modernizing applications. Your task is to analyze the ENTIRE project "
        "and make comprehensive changes to modernize the application according to the given requirement. "
        "Consider the following modernization aspects:\n\n"
        "1. **Architecture Modernization**:\n"
        "   - Modernize data access patterns (replace old patterns with modern equivalents)\n"
        "   - Implement proper service layer patterns for business logic\n"
        "   - Use dependency injection and modern frameworks\n"
        "   - Add proper exception handling and custom exceptions\n"
        "   - Follow modern architectural patterns for the specific technology stack\n\n"
        "2. **Code Quality Improvements**:\n"
        "   - Add proper validation and error handling\n"
        "   - Implement comprehensive logging\n"
        "   - Use modern language features and best practices\n"
        "   - Add meaningful error messages and proper error handling\n"
        "   - Follow coding standards for the specific language/framework\n\n"
        "3. **Testing Modernization**:\n"
        "   - Create comprehensive unit tests with modern testing frameworks\n"
        "   - Add integration tests where appropriate\n"
        "   - Implement proper test coverage\n"
        "   - Use modern testing patterns and tools\n\n"
        "4. **Configuration & Dependencies**:\n"
        "   - Update dependency files with latest stable versions\n"
        "   - Add missing dependencies for validation, logging, etc.\n"
        "   - Ensure ALL dependencies have explicit version numbers\n"
        "   - Fix any missing version specifications in existing dependencies\n"
        "   - Implement proper application configuration\n"
        "   - Add health checks and monitoring where appropriate\n\n"
        "   **Maven-Specific Rules (CRITICAL):**\n"
        "   - Parent POM version MUST be literal value (e.g., <version>3.1.0</version>)\n"
        "   - NEVER use property references in parent version (e.g., <version>${spring.boot.version}</version> is WRONG)\n"
        "   - Property references only work in dependency versions, NOT in parent versions\n"
        "   - Spring Boot parent POM provides dependency management but requires literal version\n"
        "   - Example of CORRECT parent POM:\n"
        "     <parent>\n"
        "       <groupId>org.springframework.boot</groupId>\n"
        "       <artifactId>spring-boot-starter-parent</artifactId>\n"
        "       <version>3.1.0</version>\n"
        "     </parent>\n\n"
        "5. **Cleanup & Migration**:\n"
        "   - Remove old/legacy components that conflict with new architecture\n"
        "   - Remove old test files that reference deleted components\n"
        "   - Clean up any unused imports and dependencies\n"
        "   - Ensure no references to old architecture remain\n"
        "   - Delete obsolete configuration files\n"
        "   - Remove legacy code that conflicts with new architecture\n"
        "   - Update or remove files that are no longer compatible\n\n"
        "6. **API/Interface Modernization**:\n"
        "   - Implement modern API design patterns\n"
        "   - Add proper documentation where applicable\n"
        "   - Implement proper status codes and response formats\n"
        "   - Follow modern interface design principles\n\n"
        "Analyze the entire codebase and make ALL necessary changes across ALL components to create a modern, maintainable, and production-ready application.\n\n"
        "Only return a structured list of files to be updated or created, with their new contents, in JSON format as below:\n\n"
        "{\n  \"files\": [\n    {\"path\": \"path/to/file.ext\", \"action\": \"update\", \"content\": \"...new code...\"},\n"
        "    {\"path\": \"path/to/newfile.ext\", \"action\": \"create\", \"content\": \"...new code...\"},\n"
        "    {\"path\": \"path/to/obsolete.ext\", \"action\": \"delete\"}\n  ]\n}\n"
        "DO NOT return markdown, comments, or explanation.\n"
        "Use appropriate testing frameworks and patterns for the specific technology stack.\n"
        "Ensure ALL changes work together cohesively and follow modern best practices for the specific technology.\n"
        "IMPORTANT: When modernizing, always include cleanup actions to remove old components that conflict with the new architecture.\n"
        "CRITICAL MAVEN WARNING: When creating/updating pom.xml, NEVER use property references in parent POM version. Use literal values only.\n"
        f"Requirement:\n{refined_req}\n"
        f"Codebase Snapshot:\n{existing_code}"
    )
    response = llm.invoke(prompt)
    raw_output = response.content
    if isinstance(raw_output, str):
        raw_output = raw_output.strip()
    else:
        raw_output = str(raw_output).strip()

    # Strip markdown-style formatting like ```json ... ```
    if raw_output.startswith("```json"):
        raw_output = raw_output.lstrip("```json").rstrip("```").strip()
    elif raw_output.startswith("```"):
        raw_output = raw_output.lstrip("```").rstrip("```").strip()

    # DEBUG
    print("===== CLEANED RAW OUTPUT =====")
    print(raw_output)
    print("===== END CLEANED RAW OUTPUT =====")

    import json
    try:
        parsed = json.loads(raw_output)
        if "files" not in parsed:
            raise ValueError("Missing 'files' key in Gemini response.")
        return parsed["files"]
    except Exception as e:
        print("❌ Failed to parse JSON from Gemini after cleaning.")
        print(raw_output)
        raise e
