# Agentic AI API

A Flask API that modernizes projects using AI agents and creates merge requests.

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

### POST /modernize

Modernizes a project and creates a merge request.

**Request Body:**
```json
{
    "requirement": "Modernize the project to Spring Boot 3 and Java 17",
    "gitlab_repo_url": "username/repo-name"
}
```

**Response:**
```json
{
    "success": true,
    "message": "Project modernized successfully!",
    "mr_description": "Generated description of the changes...",
    "mr_url": "https://gitlab.com/username/repo-name/-/merge_requests/123",
    "branch_name": "feature_refactor_20241203_143022"
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

## Usage with Postman

1. Set the request method to `POST`
2. Set the URL to `http://localhost:5000/modernize`
3. Set the Content-Type header to `application/json`
4. Add the request body:
```json
{
    "requirement": "Your modernization requirement here",
    "gitlab_repo_url": "username/repo-name"
}
```

**Note:** The `gitlab_repo_url` field should contain just the repository path (e.g., "janmejoyparida/employeeapi"), not the full GitLab URL. The API will automatically concatenate it with the GitLab URL from your configuration.

## Error Handling

The API returns appropriate HTTP status codes:
- `200`: Success
- `400`: Bad request (missing fields or invalid URL)
- `500`: Server error (build failure or other issues)

## Configuration

The `integration.yml` file contains all configuration settings:

```yaml
gemini:
  api_key: "your-gemini-api-key"
  model: "gemini-1.5-flash-002"  # AI model to use

gitlab:
  private_token: "your-gitlab-token"
  url: "https://gitlab.com"
  repo_path: "username/repo-name"
  default_branch: main

repository:
  local_dir: ./generated_service
```

You can change the `model` field to use different Gemini models (e.g., "gemini-1.5-pro", "gemini-1.5-flash-001", etc.).

## Notes

- The API creates temporary directories for each request
- Temporary directories are cleaned up after processing
- The API uses the same agentic AI workflow as the command-line version
- All AI agents use the model specified in the configuration file 