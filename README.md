# Agentic AI API

A Flask API that modernizes projects using AI agents and creates merge requests. Enhanced with **LangGraph** for structured AI agent orchestration!

## Features

- 🤖 **AI-Powered Modernization**: Uses Gemini AI to analyze and modernize codebases
- 🔄 **LangGraph Workflow**: Structured workflow orchestration for reliable execution
- 🏗️ **Multi-Agent System**: Four specialized AI agents working together
- 📊 **PlantUML Diagrams**: Automatic generation of codebase architecture diagrams
- 🔧 **Auto-Fix & Build**: Intelligent error detection and automatic fixes
- 📝 **Merge Request Creation**: Automatic GitLab merge request generation
- 🚀 **Health Monitoring**: Built-in health checks and deployment verification
- 🧹 **Automatic Cleanup**: Automatic cleanup of temporary files on server shutdown

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure `integration.yml` with your GitLab credentials, Gemini API key, and model configuration.

3. Run the API:
```bash
python app.py
```

The API will be available at `http://localhost:5000`

## API Endpoints

### POST /requirement

Modernizes a project using the LangGraph orchestrated workflow for reliable execution.

**Request Body:**
```json
{
    "requestMessage": "Modernize the project to Spring Boot 3 and Java 17",
    "githubRepo": "username/repo-name"
}
```

**Success Response (Build Successful):**
```json
{
    "success": true,
    "mr_details": "Generated description of the changes...",
    "mr_link": "https://gitlab.com/username/repo-name/-/merge_requests/123",
    "branch_name": "feature_refactor_20241203_143022",
    "endpoint_url": "http://localhost:8080/",
    "endpoint_health": true,
    "actuator_health_url": "http://localhost:8080/actuator/health",
    "plantuml_png": "diagrams/diagram_uuid.png"
}
```

**Error Response (Build Failed):**
```json
{
    "success": false,
    "error": "Build verification failed - merge request not created",
    "build_output": "Maven build output with error details...",
    "branch_name": "feature_refactor_20241203_143022"
}
```

**Note:** The merge request is only created if the build is successful. If the build fails, no merge request is created and an error response is returned with build details for debugging.

### POST /summarize

Generates a summary and PlantUML diagram of an existing codebase.

**Request Body:**
```json
{
    "githubRepo": "username/repo-name"
}
```

**Response:**
```json
{
    "summary": "Bullet-point summary of the codebase...",
    "plantuml_png": "diagrams/diagram_uuid.png"
}
```

### POST /generate_tests

Generate comprehensive JUnit tests and run coverage analysis for an existing project.

**Request Body:**
```json
{
    "githubRepo": "username/repo-name"
}
```

**Response:**
```json
{
    "success": true,
    "message": "Test generation and coverage analysis complete",
    "test_files_count": 15,
    "coverage_data": {
        "LINE": {"covered": 95, "missed": 5, "total": 100, "percentage": 95.0},
        "BRANCH": {"covered": 90, "missed": 10, "total": 100, "percentage": 90.0},
        "METHOD": {"covered": 100, "missed": 0, "total": 100, "percentage": 100.0}
    },
    "coverage_report": "📊 **JaCoCo Code Coverage Report**\n🟢 **Line**: 95% (95/100)\n🟡 **Branch**: 90% (90/100)\n🟢 **Method**: 100% (100/100)\n🟢 **Overall Coverage**: 95.0%",
    "report_url": "target/site/jacoco/index.html",
    "plantuml_png": "diagrams/diagram_uuid.png"
}
```

### GET /health

Health check endpoint.

**Response:**
```json
{
    "status": "healthy",
    "message": "Agentic AI API is running"
}
```

### GET /diagrams/<filename>

Serves generated PlantUML diagram images.

### POST /cleanup

Manually clean up temporary directories and files without shutting down the server.

**Request Body (Optional):**
```json
{
    "force": true
}
```

**Response:**
```json
{
    "success": true,
    "message": "Cleanup completed successfully",
    "cleaned_folders": ["diagrams", "generated_service"],
    "force_cleanup": false
}
```

**Note:** Set `"force": true` to delete Git repositories in the `generated_service` folder. Use with caution!

### GET /cleanup/status

Get the current status of directories that would be cleaned up.

**Response:**
```json
{
    "success": true,
    "status": {
        "config": {
            "auto_cleanup": true,
            "cleanup_on_startup": false,
            "preserve_git_repos": true,
            "cleanup_diagrams": true,
            "cleanup_generated_service": true
        },
        "diagrams": {
            "exists": true,
            "path": "/path/to/diagrams",
            "size": 1024,
            "size_formatted": "1.0 KB",
            "cleanup_enabled": true
        },
        "generated_service": {
            "exists": true,
            "path": "/path/to/generated_service",
            "is_git_repo": true,
            "size": 2048,
            "size_formatted": "2.0 KB",
            "cleanup_enabled": true,
            "preserve_git_repos": true
        }
    }
}
```

## AI Agent Workflow

### LangGraph Workflow (`/requirement`)
1. **Refine Node**: Agent 1 refines requirements
2. **Codegen Node**: Agent 2 generates and applies code changes
3. **Test Generation Node**: Agent 3 generates comprehensive JUnit tests with JaCoCo coverage
4. **Build & Deploy Node**: Agent 4 builds, tests, and deploys the application
5. **Merge Request Creation**: **Only if build is successful** - creates GitLab merge request with changes
6. **Structured Flow**: Sequential execution with state management

**Important:** The merge request is only created if the build process succeeds. If the build fails, no merge request is created and an error response is returned with build details for debugging.

### Agent 3: Test Generation & Coverage Analysis
**Agent 3** is a specialized AI agent that:
- **Generates comprehensive JUnit 5 tests** for all modernized code
- **Aims for 95%+ JaCoCo code coverage** (line, branch, method, class)
- **Uses modern testing practices**: Mockito, parameterized tests, edge case testing
- **Automatically adds test dependencies** to pom.xml
- **Runs tests and generates coverage reports** with detailed metrics
- **Follows testing best practices**: AAA pattern, descriptive naming, comprehensive scenarios

### Agent 4: Build & Deploy
**Agent 4** handles the build and deployment process:
- **Intelligent Build Process**: Maven compilation with automatic error fixing
- **Auto-Fix Capabilities**: Automatically fixes common build issues (Java version, dependencies, Spring Boot versions)
- **Deployment**: Starts the Spring Boot application
- **Health Monitoring**: Checks application health endpoints
- **Error Recovery**: Multiple build attempts with intelligent fixes
- **Complete Independence**: Works independently of Agent 3 - builds and deploys regardless of test generation status

## Usage Examples

### Using the LangGraph Workflow
```bash
curl -X POST http://localhost:5000/requirement \
  -H "Content-Type: application/json" \
  -d '{
    "requestMessage": "Convert this Spring Boot 2 app to Spring Boot 3",
    "githubRepo": "janmejoyparida/employeeapi"
  }'
```

### Generating Tests for Existing Project
```bash
curl -X POST http://localhost:5000/generate_tests \
  -H "Content-Type: application/json" \
  -d '{
    "githubRepo": "janmejoyparida/employeeapi"
  }'
```

### Manual Cleanup
```bash
# Regular cleanup (preserves Git repositories)
curl -X POST http://localhost:5000/cleanup

# Force cleanup (deletes everything including Git repositories)
curl -X POST http://localhost:5000/cleanup \
  -H "Content-Type: application/json" \
  -d '{"force": true}'

# Check cleanup status
curl -X GET http://localhost:5000/cleanup/status
```

## Configuration

Create an `integration.yml` file in the project root with the following structure:

```yaml
# Gemini API Configuration
gemini:
  api_key: "your_gemini_api_key_here"
  model: "gemini-1.5-flash"

# GitLab Configuration
gitlab:
  url: "https://gitlab.com"
  repo_path: "username/repo-name"  # This will be updated dynamically
  private_token: "your_gitlab_private_token_here"
  default_branch: "main"

# Local Repository Configuration
repository:
  local_dir: "generated_service"

# Agent Configuration
agents:
  skip_test_generation: false  # Set to true to skip Agent 3 (test generation)
  skip_build_deploy: false     # Set to true to skip Agent 4 (build & deploy)

# Cleanup Configuration
cleanup:
  auto_cleanup: true                    # Enable/disable automatic cleanup on shutdown
  cleanup_on_startup: false             # Clean up on server startup (optional)
  cleanup_diagrams: true                # Always clean up diagrams folder
```

### Agent Configuration Options

#### `skip_test_generation: false`
- **Default**: `false` (test generation enabled)
- **When `true`**: Agent 3 (test generation) will be skipped
- **Use cases**: 
  - Faster processing when tests are not needed
  - Debugging code generation without test overhead
  - CI/CD pipelines where tests are handled separately

#### `skip_build_deploy: false`
- **Default**: `false` (build and deploy enabled)
- **When `true`**: Agent 4 (build & deploy) will be skipped
- **Use cases**:
  - Code review workflows without deployment
  - Testing code generation without building
  - Development environments where deployment is handled separately

### Cleanup Configuration Options

#### **`auto_cleanup`** (Default: `true`)
- **`true`**: Automatic cleanup runs when server shuts down (Ctrl+C, SIGTERM, normal exit)
- **`false`**: No automatic cleanup - manual cleanup only via `/cleanup` endpoint

#### **`cleanup_on_startup`** (Default: `false`)
- **`true`**: Clean up temporary files when server starts
- **`false`**: No cleanup on startup

#### **`cleanup_diagrams`** (Default: `true`)
- **`true`**: Always clean up PlantUML diagram files
- **`false`**: Preserve diagram files

#### **`generated_service`** (Always Preserved)
- The `generated_service` folder is **always preserved** for workspace inspection
- The Spring Boot server running in the workspace will be stopped on cleanup
- No configuration option needed - this behavior is built-in

## Dependencies

Key packages used:
- **Flask**: Web framework
- **LangGraph**: AI workflow orchestration
- **LangChain Google GenAI**: Gemini AI integration
- **Python-GitLab**: GitLab API integration
- **PlantUML**: Architecture diagram generation
- **GitPython**: Git operations

**Utility Modules:**
- **`utils/file_ops.py`**: File operations and modernization cleanup
- **`utils/cleanup.py`**: Automatic cleanup and shutdown handlers

## Error Handling

The API returns appropriate HTTP status codes:
- `200`: Success
- `400`: Bad request (missing fields or invalid repo format)
- `404`: No code files found
- `500`: Server error (build failure or other issues)

## Notes

- The API creates temporary directories for each request
- Temporary directories are cleaned up after processing
- The LangGraph workflow provides reliable execution with better state management
- All AI agents use the model specified in the configuration file
- PlantUML diagrams are automatically generated and served via `/diagrams/<filename>`
- **Automatic Cleanup**: The `diagrams` and `generated_service` folders are automatically deleted when the server shuts down (Ctrl+C, SIGTERM, or normal exit)
- **Manual Cleanup**: Use the `/cleanup` endpoint to clean up temporary files without shutting down the server
- **Cleanup Status**: Use `/cleanup/status` to check the current state of directories that would be cleaned up
- **Utility Organization**: Cleanup logic is organized in `utils/cleanup.py` for better maintainability
- **Configurable Cleanup**: Cleanup behavior can be controlled via `integration.yml` configuration
- **Agent Configuration**: Individual agents can be skipped via `integration.yml` configuration
- **Agent Independence**: Agent 4 (build & deploy) works completely independently of Agent 3 (test generation)
- **Spring Boot Management**: The Spring Boot server started by Agent 4 is automatically stopped when the Flask API server shuts down
- **Git Repository Recovery**: Automatically handles corrupted or invalid Git repositories by removing and re-cloning
- **Windows Maven Support**: Automatically detects Windows platform and uses `mvn.cmd` instead of `mvn` for proper Maven execution
- **Conditional MR Creation**: Merge requests are only created if the build process succeeds, ensuring quality control

## Architecture

### High-Level Architecture
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   User Request  │───▶│  LangGraph      │───▶│  AI Agents      │
│                 │    │  Workflow       │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │  Agent 1:      │
                       │  Refine        │
                       └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │  Agent 2:      │
                       │  Code Gen      │
                       └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │  Agent 3:      │
                       │  Test Gen      │
                       │  + Coverage    │
                       └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │  Agent 4:      │
                       │  Build & Deploy│
                       │  + Health Check│
                       └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │  Build Success? │
                       │  Check          │
                       └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │  GitLab MR      │
                       │  + Diagrams     │
                       │  + Coverage     │
                       │  (Only if OK)   │
                       └─────────────────┘
```

### Low-Level Design (LLD) Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              Flask API Layer                                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │   /health   │  │ /requirement│  │/generate_   │  │  /summarize  │            │
│  │             │  │             │  │   tests     │  │             │            │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘            │
│         │                │                │                │                   │
│         └────────────────┼────────────────┼────────────────┘                   │
│                          ▼                ▼                                    │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │                        Request Validation Layer                             │ │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐            │ │
│  │  │ validate_modern │  │ load_and_update │  │ clone_or_pull_  │            │ │
│  │  │ ize_request()   │  │    _config()    │  │     repo()      │            │ │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘            │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            LangGraph Workflow Engine                            │
├─────────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │  StateGraph<ModernizeState>                                                │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │ │
│  │  │   START     │──▶│   refine    │──▶│  codegen    │──▶│  test_gen   │        │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │ │
│  │                                                                             │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │ │
│  │  │  build_     │──▶│     END     │  │  node_      │  │  node_      │        │ │
│  │  │  deploy     │  └─────────────┘  │  refine()   │  │  codegen()  │        │ │
│  │  └─────────────┘                   └─────────────┘  └─────────────┘        │ │
│  │                                                                             │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │ │
│  │  │  node_test_ │  │  node_build │  │  create_    │  │  Modernize   │        │ │
│  │  │  _gen()     │  │  _deploy()  │  │  modernize_ │  │  State      │        │ │
│  │  └─────────────┘  └─────────────┘  │  graph()    │  │  (TypedDict)│        │ │
│  │                                    └─────────────┘  └─────────────┘        │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              AI Agent Layer                                     │
├─────────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │   Agent 1:      │  │   Agent 2:      │  │   Agent 3:      │  │   Agent 4:  │ │
│  │  Requirement    │  │   Code          │  │   Test          │  │   Build &   │ │
│  │  Refinement     │  │  Generation     │  │  Generation     │  │   Deploy    │ │
│  │                 │  │                 │  │                 │  │             │ │
│  │ • refine_       │  │ • generate_code │  │ • create_test_  │  │ • fix_and_  │ │
│  │   requirement() │  │ • generate_mr_  │  │   agent_        │  │   build()   │ │
│  │ • Uses Gemini   │  │   description() │  │   workflow()    │  │ • try_build │ │
│  │   AI            │  │ • apply_        │  │ • JUnit 5       │  │ • fix_build │ │
│  │                 │  │   structured_   │  │   generation    │  │   _issues() │ │
│  │                 │  │   changes()     │  │ • JaCoCo        │  │ • deploy_   │ │
│  │                 │  │ • Uses Gemini   │  │   coverage      │  │   and_check │ │
│  │                 │  │   AI            │  │ • Mockito       │  │   _health() │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            External Services Layer                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │   GitLab API    │  │   Gemini AI     │  │   PlantUML      │  │   Maven     │ │
│  │                 │  │                 │  │   Server        │  │   Build     │ │
│  │ • Clone/Pull    │  │ • Code          │  │                 │  │   System    │ │
│  │   Repository    │  │   Generation    │  │ • Diagram       │  │             │ │
│  │ • Create MR     │  │ • Requirement   │  │   Generation    │  │ • Compile   │ │
│  │ • Commit        │  │   Refinement    │  │ • PNG Output    │  │ • Package   │ │
│  │   Changes       │  │ • Test          │  │ • Architecture  │  │ • Run Tests │ │
│  │ • Branch        │  │   Generation    │  │   Visualization │  │ • Deploy    │ │
│  │   Management    │  │ • MR            │  │                 │  │   App       │ │
│  │                 │  │   Description   │  │                 │  │             │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              Data Flow Layer                                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │   Request       │  │   State         │  │   File          │  │   Response  │ │
│  │   Processing    │  │   Management    │  │   Operations    │  │   Generation │ │
│  │                 │  │                 │  │                 │  │             │ │
│  │ • JSON          │  │ • Modernize     │  │ • apply_        │  │ • Success   │ │
│  │   Validation    │  │   State         │  │   structured_   │  │   Response  │ │
│  │ • Error         │  │   (TypedDict)   │  │   changes()     │  │ • Error     │ │
│  │   Handling      │  │ • State         │  │ • ensure_clean_ │  │   Response  │ │
│  │ • Config        │  │   Transitions   │  │   modernizat    │  │ • MR        │ │
│  │   Loading       │  │ • Build         │  │   ion()         │  │   Creation  │ │
│  │ • Git           │  │   Success       │  │ • File          │  │ • Diagram   │ │
│  │   Operations    │  │   Tracking      │  │   Backup        │  │   URLs      │ │
│  │                 │  │                 │  │   (.bak)        │  │ • Health    │ │
│  │                 │  │                 │  │   Cleanup       │  │   Status    │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              Utility Layer                                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │   File          │  │   Cleanup       │  │   Git           │  │   PlantUML  │ │
│  │   Operations    │  │   Management    │  │   Handler       │  │   Utils     │ │
│  │                 │  │                 │  │                 │  │             │ │
│  │ • get_code_     │  │ • setup_cleanup │  │ • AgenticGit    │  │ • render_   │ │
│  │   files_for_    │  │   _handlers()   │  │   Handler       │  │   plantuml_ │ │
│  │   summary()     │  │ • cleanup_      │  │ • clone_or_     │  │   to_png()  │ │
│  │ • generate_     │  │   directories() │  │   pull_repo()   │  │ • Diagram   │ │
│  │   gemini_       │  │ • get_cleanup_  │  │ • apply_and_    │  │   Generation│ │
│  │   summary()     │  │   status()      │  │   commit_       │  │ • PNG       │ │
│  │ • generate_     │  │ • Automatic     │  │   changes()     │  │   Output    │ │
│  │   plantuml_     │  │   Shutdown      │  │ • create_merge_ │  │ • Error     │ │
│  │   diagram()     │  │   Cleanup       │  │   request()     │  │   Handling  │ │
│  │                 │  │                 │  │                 │  │             │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Component Interaction Flow

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Client    │───▶│  Flask API  │───▶│ LangGraph   │───▶│   Agent 1   │
│  Request    │    │  Endpoint   │    │  Workflow   │    │  Refine     │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                                                              │
                                                              ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   GitLab    │◀───│  Git        │◀───│   Agent 2   │◀───│   State     │
│   MR        │    │  Handler    │    │  Code Gen   │    │  Update     │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
       ▲                   ▲                   │                   │
       │                   │                   ▼                   ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  PlantUML   │    │   Maven     │    │   Agent 3   │    │   Agent 4   │
│  Diagrams   │    │   Build     │    │  Test Gen   │    │  Build &    │
│             │    │   System    │    │             │    │  Deploy     │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
       ▲                   ▲                   ▲                   ▲
       │                   │                   │                   │
       └───────────────────┼───────────────────┼───────────────────┘
                           │                   │
                           ▼                   ▼
                   ┌─────────────┐    ┌─────────────┐
                   │   Gemini    │    │   Health    │
                   │     AI      │    │   Check     │
                   └─────────────┘    └─────────────┘
```

### Data State Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ModernizeState Flow                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │ raw_        │  │ refined_    │  │ file_       │  │ test_       │        │
│  │ requirement │  │ requirement │  │ instructions│  │ files       │        │
│  │ (str)       │  │ (str)       │  │ (List[Dict])│  │ (List[Dict])│        │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
│         │                │                │                │               │
│         ▼                ▼                ▼                ▼               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │ coverage_   │  │ coverage_   │  │ test_       │  │ tests_      │        │
│  │ data        │  │ report      │  │ success     │  │ skipped     │        │
│  │ (Dict)      │  │ (str)       │  │ (bool)      │  │ (bool)      │        │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
│         │                │                │                │               │
│         ▼                ▼                ▼                ▼               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │ build_      │  │ build_      │  │ endpoint_   │  │ endpoint_   │        │
│  │ success     │  │ output      │  │ url         │  │ health      │        │
│  │ (bool)      │  │ (str)       │  │ (str)       │  │ (bool)      │        │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
│         │                │                │                │               │
│         ▼                ▼                ▼                ▼               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │ actuator_   │  │ MR          │  │ PlantUML    │  │ Response    │        │
│  │ health_url  │  │ Creation    │  │ Diagram     │  │ Generation  │        │
│  │ (str)       │  │ Decision    │  │ Generation  │  │             │        │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```