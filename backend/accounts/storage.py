from django_supabase_storage import SupabaseMediaStorage


class RootMediaStorage(SupabaseMediaStorage):
    """Media storage that saves at the bucket root (no extra 'media/' folder)."""
    folder_path = ""