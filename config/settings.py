import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # Google Cloud
    GOOGLE_CLOUD_PROJECT = os.getenv('GOOGLE_CLOUD_PROJECT', 'multi-agent-492316')
    
    # API Keys
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')
    RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY')
    
    # RapidAPI Hosts
    RAPIDAPI_JSEARCH_HOST = os.getenv('RAPIDAPI_JSEARCH_HOST', 'jsearch.p.rapidapi.com')
    
    # Piston API
    PISTON_API_URL = os.getenv('PISTON_API_URL', 'https://emkc.org/api/v2/piston/execute')
    EXECUTOR_SERVICE_URL = os.getenv('EXECUTOR_SERVICE_URL', '')
    EXECUTOR_SHARED_SECRET = os.getenv('EXECUTOR_SHARED_SECRET', '')
    EXECUTOR_REQUEST_TIMEOUT = int(os.getenv('EXECUTOR_REQUEST_TIMEOUT', '20'))
    
    # Flask
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    FLASK_SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
    FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'True') == 'True'
    
    # Cache TTL (hours)
    TRENDING_CACHE_TTL = int(os.getenv('TRENDING_CACHE_TTL', '24'))
    VIDEO_CACHE_TTL = int(os.getenv('VIDEO_CACHE_TTL', '12'))
    JOB_CACHE_TTL = int(os.getenv('JOB_CACHE_TTL', '6'))
    MARKET_PROFILE_CACHE_TTL_MINUTES = int(os.getenv('MARKET_PROFILE_CACHE_TTL_MINUTES', '15'))
    ENABLE_MARKET_PROFILE_PREWARM = os.getenv('ENABLE_MARKET_PROFILE_PREWARM', 'False') == 'True'

    # Market profile prewarm roles for production refresh jobs
    HOT_MARKET_ROLES = [
        role.strip()
        for role in os.getenv(
            'HOT_MARKET_ROLES',
            'AI Engineer,ML Engineer,Data Scientist,Backend Developer,Frontend Developer,Full Stack Developer'
        ).split(',')
        if role.strip()
    ]
    
    # Timeouts (seconds)
    API_TIMEOUT = int(os.getenv('API_TIMEOUT', '30'))
    
    # Master YouTube Channels
    MASTER_CHANNELS = [
        "UC8butISFwT-Wl7EV0hUK0BQ",  # freeCodeCamp
        "UCW5YeuERMmlnqo4oq8vwUpg",  # Net Ninja
        "UC29ju8bIPH5as8OGnQzwJyA",  # Traversy Media
        "UCsBjURrPoezykLs9EqgamOA",  # Fireship
        "UCvjgXvBlbQiydffZU7m1_aw",  # Coding Train
        "UCV0qA-eDDICsRR9rPcnG7tw",  # Joma Tech
        "UC8S4rDRZn6Z_StJ-hh7ph8g",  # Kevin Powell
        "UCFbNIlppjAuEX4znoulh0Cw",  # Web Dev Simplified
        "UC-T8W79DN6PBnzomelvqJYw",  # Hitesh Choudhary
        "UCeVMnSShP_Iviwkknt83cww",  # Code with Harry
        "UCWX0cUR2rZcqKei1Vstww-A",  # Programming with Mosh
        "UCmXVXfidLZQkppLPaATcHag"   # Academind
    ]
    
    @staticmethod
    def validate():
        errors = []
        if not Settings.GEMINI_API_KEY:
            errors.append("GEMINI_API_KEY not set")
        if not Settings.YOUTUBE_API_KEY:
            errors.append("YOUTUBE_API_KEY not set")
        if not Settings.RAPIDAPI_KEY:
            errors.append("RAPIDAPI_KEY not set")
        
        if errors:
            raise ValueError(f"Missing required environment variables: {', '.join(errors)}")
        
        return True

settings = Settings()
