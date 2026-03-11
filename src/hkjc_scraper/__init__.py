"""HKJC Racing Scraper - Extract horse racing data from HKJC."""

# Database
from hkjc_scraper.database import (
    create_database,
    export_json_to_db,
    get_db_connection,
    import_dividends,
    import_horses,
    import_incidents,
    import_jockeys,
    import_performance,
    import_races,
    import_sectional_times,
    import_trainers,
    load_from_db,
)

# Data parsing utilities
from hkjc_scraper.data_parsers import (
    clean_position,
    parse_rating,
    parse_prize,
    parse_running_position,
    generate_race_id,
    parse_sectional_time_cell,
)

# ID extraction utilities
from hkjc_scraper.id_parsers import (
    extract_horse_id,
    extract_jockey_id,
    extract_trainer_id,
)

# Career record parsing
from hkjc_scraper.common import (
    parse_career_record,
)

# Profile parsing
from hkjc_scraper.horse_parsers import (
    parse_horse_profile,
)
from hkjc_scraper.jockey_trainer_parsers import (
    parse_jockey_profile,
    parse_trainer_profile,
)

__all__ = [
    # Database
    "create_database",
    "export_json_to_db",
    "get_db_connection",
    "import_dividends",
    "import_horses",
    "import_incidents",
    "import_jockeys",
    "import_performance",
    "import_races",
    "import_sectional_times",
    "import_trainers",
    "load_from_db",
    # Data parsers
    "clean_position",
    "parse_rating",
    "parse_prize",
    "parse_running_position",
    "generate_race_id",
    "parse_sectional_time_cell",
    # Constants
    "RACECOURSE_MAP",
    "RACECOURSE_NAMES",
    # ID parsers
    "extract_horse_id",
    "extract_jockey_id",
    "extract_trainer_id",
    # Common
    "parse_career_record",
    # Profile parsers
    "parse_horse_profile",
    "parse_jockey_profile",
    "parse_trainer_profile",
]
