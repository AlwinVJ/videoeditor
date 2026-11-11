"""
core/config.py - Centralized configuration and secrets management.

Provides unified retrieval of environment variables and API keys across:
- Local development (.env file via python-dotenv / os.environ)
- Streamlit Cloud (Streamlit Secrets via st.secrets)

Security:
- Never prints, logs, or exposes raw secrets/API keys.
- Fails gracefully with actionable guidance for developers and deployment users.
"""

import os
from typing import Optional

# Attempt to load local .env variables safely
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # Graceful fallback if python-dotenv is absent in minimal container builds
    pass


def get_secret(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Retrieve a configuration secret or API key.
    
    Order of precedence:
    1. Operating system environment variable (populated by local .env or system env)
    2. Lowercase environment variable
    3. Streamlit Cloud Secrets (st.secrets)
       - Direct top-level match (e.g., st.secrets["GROQ_API_KEY"])
       - Lowercase top-level match (e.g., st.secrets["groq_api_key"])
       - Nested section match (e.g., st.secrets["groq"]["api_key"])
    4. Default fallback value
    
    Args:
        key: The configuration key name (e.g., 'GROQ_API_KEY')
        default: Fallback value if not found
        
    Returns:
        The secret string value if found and non-empty, otherwise default.
    """
    # 1. Environment variable check
    env_val = os.getenv(key)
    if env_val is not None and str(env_val).strip():
        return str(env_val).strip()

    # Lowercase environment variable check
    env_val_lower = os.getenv(key.lower())
    if env_val_lower is not None and str(env_val_lower).strip():
        return str(env_val_lower).strip()

    # 2. Streamlit Secrets check (Streamlit Cloud fallback)
    try:
        import streamlit as st
        if hasattr(st, "secrets") and st.secrets is not None:
            # Direct key lookup
            if key in st.secrets:
                secret_val = st.secrets[key]
                if secret_val is not None and str(secret_val).strip():
                    return str(secret_val).strip()

            # Lowercase key lookup
            if key.lower() in st.secrets:
                secret_val = st.secrets[key.lower()]
                if secret_val is not None and str(secret_val).strip():
                    return str(secret_val).strip()

            # Nested section lookup: e.g. GROQ_API_KEY -> [groq] api_key = "..."
            if "_" in key:
                section, subkey = key.split("_", 1)
                for sec in (section.lower(), section.upper()):
                    if sec in st.secrets:
                        sec_val = st.secrets[sec]
                        if isinstance(sec_val, dict) or hasattr(sec_val, "get"):
                            for sub in (subkey.lower(), subkey.upper()):
                                if sub in sec_val:
                                    nested_val = sec_val[sub]
                                    if nested_val is not None and str(nested_val).strip():
                                        return str(nested_val).strip()
    except (FileNotFoundError, KeyError, AttributeError, Exception):
        # Handles missing secrets.toml, outside-of-Streamlit runs, etc.
        pass

    return default


def get_required_secret(
    key: str,
    friendly_name: Optional[str] = None,
    help_context: Optional[str] = None,
) -> str:
    """
    Retrieve a required configuration secret or raise an actionable ValueError.
    
    Args:
        key: The configuration key name (e.g. 'GROQ_API_KEY')
        friendly_name: Human-friendly name for error messages (e.g. 'Groq API key')
        help_context: Additional help text to append to the error message
        
    Returns:
        The secret value string.
        
    Raises:
        ValueError: If the key is missing or empty in all configuration sources.
    """
    val = get_secret(key)
    if not val:
        display_name = friendly_name or key
        msg = (
            f"{display_name} not found. Please ensure '{key}' is configured in your local .env file "
            f"or in Streamlit Cloud Secrets (App Settings -> Secrets)."
        )
        if help_context:
            msg += f" {help_context}"
        raise ValueError(msg)
    return val


def get_groq_api_key() -> str:
    """
    Retrieve the Groq API key from environment variables or Streamlit Secrets.
    
    Returns:
        The valid Groq API key string.
    """
    return get_required_secret("GROQ_API_KEY", friendly_name="Groq API key")


def get_pixabay_api_key() -> str:
    """
    Retrieve the Pixabay API key from environment variables or Streamlit Secrets.
    
    Returns:
        The valid Pixabay API key string.
    """
    return get_required_secret("PIXABAY_API_KEY", friendly_name="Pixabay API key")


def mask_secret(value: Optional[str]) -> str:
    """
    Return a masked representation of a secret for safe debugging/reporting.
    Never reveals the secret payload.
    """
    if not value:
        return "<not set>"
    val_str = str(value).strip()
    if len(val_str) <= 8:
        return "********"
    return f"{val_str[:4]}...{val_str[-4:]}"
