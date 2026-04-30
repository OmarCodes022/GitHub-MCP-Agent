# GitHub MCP Agent

A GitHub project management agent powered by AWS Bedrock and the GitHub MCP server.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Create a `.env` file:
   ```
   GITHUB_TOKEN=your_github_token
   AWS_PROFILE=your_aws_profile
   ```

3. Run:
   ```bash
   ./run.sh
   ```

## Requirements

- Docker (for the GitHub MCP server)
- AWS credentials with Bedrock access
- GitHub personal access token with `repo`, `read:org`, and `project` scopes
