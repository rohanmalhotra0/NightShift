"""Supabase client for database operations."""

from supabase import create_client, Client
from config import settings

def get_supabase() -> Client:
    """Get Supabase client instance with service role key for full access."""
    return create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_SERVICE_KEY or settings.SUPABASE_ANON_KEY
    )

# Global client instance
supabase = get_supabase()
