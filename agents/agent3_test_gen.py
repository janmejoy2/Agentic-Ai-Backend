import os
import yaml
import json
from langchain_google_genai import ChatGoogleGenerativeAI
from typing import List, Dict, Any, Tuple


def load_config() -> Dict[str, Any]:
    """Load configuration from integration.yml"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(os.path.dirname(current_dir), "integration.yml")
    with open(config_path) as f:
        return yaml.safe_load(f)


def get_source_files_for_testing(repo_dir: str) -> str:
    """
    Get all source code files that need test coverage.
    Focuses on Java source files and configuration.
    """
    source_files = []
    
    for root, dirs, files in os.walk(repo_dir):
        for file in files:
            if file.endswith('.java') and 'src/main/java' in root:
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        rel_path = os.path.relpath(file_path, repo_dir)
                        source_files.append(f"// SOURCE FILE: {rel_path}\n{content}")
                except Exception as e:
                    print(f"Could not read {file_path}: {e}")
    
    # Also include pom.xml for dependency analysis
    pom_path = os.path.join(repo_dir, "pom.xml")
    if os.path.exists(pom_path):
        try:
            with open(pom_path, "r", encoding="utf-8") as f:
                pom_content = f.read()
                source_files.append(f"// POM FILE: pom.xml\n{pom_content}")
        except Exception as e:
            print(f"Could not read pom.xml: {e}")
    
    return "\n\n".join(source_files)


def generate_comprehensive_tests(source_code: str, config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Generate comprehensive JUnit tests with maximum JaCoCo coverage.
    """
    llm = ChatGoogleGenerativeAI(
        model=config["gemini"]["model"], 
        google_api_key=config["gemini"]["api_key"]
    )
    
    prompt = f"""
You are an expert Java testing engineer specializing in JUnit 5 and maximum code coverage. 
Your task is to generate comprehensive JUnit tests for the modernized Java application.

**REQUIREMENTS:**
1. **Maximum Coverage**: Aim for 95%+ JaCoCo code coverage
2. **JUnit 5**: Use latest JUnit 5 features (assertions, parameterized tests, etc.)
3. **Test All Scenarios**: Happy path, edge cases, error conditions, boundary values
4. **Mocking**: Use Mockito for external dependencies
5. **Test Organization**: Follow AAA pattern (Arrange, Act, Assert)
6. **Naming**: Clear, descriptive test method names
7. **Coverage**: Test all public methods, constructors, and important private logic

**TESTING STRATEGIES:**
- **Unit Tests**: Test individual classes and methods
- **Integration Tests**: Test component interactions
- **Exception Testing**: Test error conditions and edge cases
- **Parameterized Tests**: Test multiple input combinations
- **Mock Testing**: Mock external dependencies (databases, APIs, etc.)
- **Boundary Testing**: Test limits, null values, empty collections
- **State Testing**: Verify object state changes

**COVERAGE TARGETS:**
- **Line Coverage**: 95%+
- **Branch Coverage**: 90%+
- **Method Coverage**: 100%
- **Class Coverage**: 100%

**DEPENDENCIES TO INCLUDE:**
```xml
<dependency>
    <groupId>org.junit.jupiter</groupId>
    <artifactId>junit-jupiter</artifactId>
    <scope>test</scope>
</dependency>
<dependency>
    <groupId>org.mockito</groupId>
    <artifactId>mockito-core</artifactId>
    <scope>test</scope>
</dependency>
<dependency>
    <groupId>org.mockito</groupId>
    <artifactId>mockito-junit-jupiter</artifactId>
    <scope>test</scope>
</dependency>
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-test</artifactId>
    <scope>test</scope>
</dependency>
```

**SOURCE CODE TO TEST:**
{source_code}

**INSTRUCTIONS:**
Analyze the source code and generate comprehensive JUnit tests. Return ONLY a JSON response with the following format:

{{
  "test_files": [
    {{
      "path": "src/test/java/com/example/ControllerTest.java",
      "action": "create",
      "content": "// Complete JUnit test file content here"
    }}
  ],
  "pom_updates": [
    {{
      "path": "pom.xml",
      "action": "update",
      "content": "// Updated pom.xml with test dependencies"
    }}
  ]
}}

**IMPORTANT:**
- Generate tests for EVERY public class and method
- Include tests for edge cases and error conditions
- Use modern JUnit 5 features and best practices
- Ensure maximum code coverage possible
- Test both positive and negative scenarios
- Mock external dependencies appropriately
- Follow Java testing conventions and naming

Return ONLY the JSON response, no explanations or markdown.
"""

    try:
        response = llm.invoke(prompt)
        raw_output = response.content
        
        if isinstance(raw_output, str):
            raw_output = raw_output.strip()
        else:
            raw_output = str(raw_output).strip()

        # Clean up markdown formatting
        if raw_output.startswith("```json"):
            raw_output = raw_output.lstrip("```json").rstrip("```").strip()
        elif raw_output.startswith("```"):
            raw_output = raw_output.lstrip("```").rstrip("```").strip()

        # Parse JSON response
        parsed = json.loads(raw_output)
        
        # Combine test files and pom updates
        all_files = []
        if "test_files" in parsed:
            all_files.extend(parsed["test_files"])
        if "pom_updates" in parsed:
            all_files.extend(parsed["pom_updates"])
        
        return all_files
        
    except Exception as e:
        print(f"❌ Error generating tests: {e}")
        return []


def run_jacoco_coverage_check(repo_dir: str) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Run JaCoCo coverage analysis and return results.
    """
    import subprocess
    import xml.etree.ElementTree as ET
    
    try:
        print("🧪 Running JaCoCo coverage analysis...")
        
        # First, run tests
        print("🔍 Running JUnit tests...")
        
        # Use mvn.cmd on Windows, mvn on other platforms
        import platform
        mvn_command = "mvn.cmd" if platform.system() == "Windows" else "mvn"
        
        test_result = subprocess.run(
            [mvn_command, "clean", "test", "jacoco:report"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if test_result.returncode != 0:
            return False, "Tests failed", {
                "test_output": test_result.stdout + test_result.stderr,
                "coverage": None
            }
        
        print("✅ Tests passed, analyzing coverage...")
        
        # Parse JaCoCo report
        jacoco_report_path = os.path.join(repo_dir, "target", "site", "jacoco", "index.html")
        if not os.path.exists(jacoco_report_path):
            return False, "JaCoCo report not found", {
                "test_output": test_result.stdout,
                "coverage": None
            }
        
        # Parse XML report for detailed coverage
        xml_report_path = os.path.join(repo_dir, "target", "site", "jacoco", "jacoco.xml")
        coverage_data = {}
        
        if os.path.exists(xml_report_path):
            try:
                tree = ET.parse(xml_report_path)
                root = tree.getroot()
                
                # Extract coverage metrics
                for counter in root.findall(".//counter"):
                    counter_type = counter.get("type")
                    covered = int(counter.get("covered", 0))
                    missed = int(counter.get("missed", 0))
                    total = covered + missed
                    
                    if total > 0:
                        percentage = (covered / total) * 100
                        coverage_data[counter_type] = {
                            "covered": covered,
                            "missed": missed,
                            "total": total,
                            "percentage": round(percentage, 2)
                        }
                
                print("📊 Coverage Analysis Complete")
                for metric, data in coverage_data.items():
                    print(f"  {metric}: {data['percentage']}% ({data['covered']}/{data['total']})")
                
            except Exception as e:
                print(f"⚠️ Could not parse XML report: {e}")
        
        return True, "Coverage analysis complete", {
            "test_output": test_result.stdout,
            "coverage": coverage_data,
            "report_url": jacoco_report_path
        }
        
    except subprocess.TimeoutExpired:
        return False, "Tests timed out", {"coverage": None}
    except Exception as e:
        return False, f"Coverage check failed: {e}", {"coverage": None}


def generate_test_coverage_report(coverage_data: Dict[str, Any]) -> str:
    """
    Generate a human-readable coverage report.
    """
    if not coverage_data:
        return "No coverage data available"
    
    report_lines = ["📊 **JaCoCo Code Coverage Report**\n"]
    
    for metric, data in coverage_data.items():
        percentage = data['percentage']
        covered = data['covered']
        total = data['total']
        
        # Add emoji based on coverage level
        if percentage >= 90:
            emoji = "🟢"
        elif percentage >= 80:
            emoji = "🟡"
        elif percentage >= 70:
            emoji = "🟠"
        else:
            emoji = "🔴"
        
        report_lines.append(f"{emoji} **{metric.title()}**: {percentage}% ({covered}/{total})")
    
    # Calculate overall coverage
    total_covered = sum(data['covered'] for data in coverage_data.values())
    total_lines = sum(data['total'] for data in coverage_data.values())
    
    if total_lines > 0:
        overall_coverage = (total_covered / total_lines) * 100
        overall_emoji = "🟢" if overall_coverage >= 90 else "🟡" if overall_coverage >= 80 else "🟠" if overall_coverage >= 70 else "🔴"
        report_lines.append(f"\n{overall_emoji} **Overall Coverage**: {overall_coverage:.1f}%")
    
    return "\n".join(report_lines)


def create_test_agent_workflow(repo_dir: str) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Main workflow for Agent 3: Generate tests and check coverage.
    """
    try:
        config = load_config()
        
        print("🧪 Agent 3: Starting comprehensive test generation...")
        
        # Step 1: Get source code for testing
        print("📖 Analyzing source code for test generation...")
        source_code = get_source_files_for_testing(repo_dir)
        
        if not source_code:
            return False, "No source code found for testing", {}
        
        # Step 2: Generate comprehensive tests
        print("✍️ Generating comprehensive JUnit tests...")
        test_files = generate_comprehensive_tests(source_code, config)
        
        if not test_files:
            return False, "Failed to generate tests", {}
        
        print(f"✅ Generated {len(test_files)} test files")
        
        # Step 3: Apply test files to repository
        print("💾 Applying test files to repository...")
        from utils.file_ops import apply_structured_changes
        apply_structured_changes(test_files, repo_dir)
        
        # Step 4: Run tests and check coverage
        print("🔍 Running tests and analyzing coverage...")
        success, message, coverage_info = run_jacoco_coverage_check(repo_dir)
        
        if not success:
            return False, f"Coverage check failed: {message}", coverage_info
        
        # Step 5: Generate coverage report
        coverage_report = generate_test_coverage_report(coverage_info.get("coverage", {}))
        
        return True, "Test generation and coverage analysis complete", {
            "test_files": test_files,
            "coverage_data": coverage_info.get("coverage", {}),
            "coverage_report": coverage_report,
            "report_url": coverage_info.get("report_url"),
            "test_output": coverage_info.get("test_output", "")
        }
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"❌ Agent 3 workflow failed: {e}")
        print(f"Traceback: {error_details}")
        return False, f"Test generation failed: {e}", {"error_details": error_details}
