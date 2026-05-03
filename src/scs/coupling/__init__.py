"""dataframe-first coupling analysis helpers.

this package turns trace chunks and alert chunks into:
- trace-derived service paths
- plausible timing windows for candidate pairs
- ordered alert pairs inside those windows
- pure evidence-based coupling scores
"""

from .pairs import build_alert_pairs_df
from .paths import build_service_paths_df
from .scoring import build_coupling_df, score_coupling
from .windows import build_plausible_windows_df
