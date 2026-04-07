# SkillUp Agent

Multi-Agent AI System for Google GenAI APAC 2026 Hackathon (Track 2)

## Project Overview

SkillUp Agent is a production-ready AI system that helps users:
- Discover trending tech skills
- Analyze resume and identify skill gaps
- Get personalized learning recommendations
- Learn through curated videos and coding practice
- Get evaluated and matched with real job opportunities

## Architecture

### Agents
1. **Orchestrator Agent**: Entry point, resume analysis, recommendations, level assessment
2. **Learning Agent**: Video curation, coding practice, Socratic AI assistant
3. **Evaluator Agent**: Final assessment, scoring, job matching

### Tech Stack
- Google ADK
- Gemini 2.5 Flash
- Flask
- Google Cloud Firestore
- YouTube Data API v3
- Judge0 (code execution)
- RapidAPI JSearch (job search)

## Setup Instructions

### Prerequisites
- Python 3.9 or higher
- Google Cloud account
- API keys (Gemini, YouTube, RapidAPI)

### Installation

1. Clone the repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Set up Google Cloud:
   - Install Google Cloud CLI
   - Run: gcloud auth application-default login
   - Project: multi-agent-492316

4. Configure environment variables:
   - Copy .env.example to .env
   - Fill in your API keys

5. Run the application:
   ```
   python api/flask_app.py
   ```

## Project Structure

```
skillup-agent/
├── config/           # Configuration settings
├── database/         # Firestore client
├── agents/           # Three AI agents
├── tools/            # MCP tools, external APIs
├── utils/            # Logging, validators
├── api/              # Flask endpoints
├── static/           # CSS, JavaScript
├── templates/        # HTML templates
└── requirements.txt  # Python dependencies
```

## API Endpoints

- POST /api/trending-skills - Get trending tech skills
- POST /api/analyze-resume - Analyze uploaded resume
- POST /api/recommend-skills - Get skill recommendations
- POST /api/assess-level - User level assessment
- POST /api/generate-schedule - Create learning schedule
- POST /api/get-videos - Fetch learning videos
- POST /api/run-code - Execute code practice
- POST /api/get-hint - Get Socratic hints
- POST /api/evaluate - Final evaluation
- POST /api/get-jobs - Fetch job matches

## Features

- Trending skills discovery (Gemini)
- Resume analysis (PDF, text, image, URL)
- Smart skill gap recommendations
- Adaptive level assessment
- User-controlled scheduling
- Video curation (12 master channels)
- Coding practice (Judge0)
- Socratic AI assistant
- Final evaluation with badge
- Real job matching (10 jobs)

## Development

Built for Google GenAI APAC 2026 Hackathon.

## License

MIT
