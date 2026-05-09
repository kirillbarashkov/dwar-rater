# Re-export from shared.services for backward compatibility
from shared.services.parser import fetch_character_page, parse_character
from shared.services.processor import process_character
from shared.services.cache_service import get_cached_character, save_character_cache, log_analysis, create_named_snapshot
from shared.services.data_logger import data_logger
