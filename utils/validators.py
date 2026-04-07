import re

def sanitize_input(text):
    if not text:
        return ""
    
    # Remove emojis and special unicode characters
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "]+",
        flags=re.UNICODE
    )
    text = emoji_pattern.sub(r'', text)
    
    # Keep only safe characters
    text = re.sub(r'[^\x00-\x7F]+', '', text)
    
    return text.strip()

def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_url(url):
    pattern = r'^https?://[^\s<>"{}|\\^`\[\]]+$'
    return re.match(pattern, url) is not None
