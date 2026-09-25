"""Legion service-offering standard (levi.services).

The one pipeline every provider uses to offer cyber,
software-development, and career services, whether the provider is
an organ or Levi in general:

    analyze -> quote -> deliver -> paid -> showcase

Compose, never duplicate: analysis records structured reports;
quoting composes the founder price advisor; delivery runs the bounty
hunter state machine; money moves through the Cybrus money gateway
only (fail-closed — no rails, no real money); completed work admits
to the hunt showcase. A quote is never a charge.

Job search lives and originates here (levi.services.job_search):
the job organ's sourcing/scoring/prep machinery wrapped as a
first-class offering, for Chauncey's own search (provider "levi",
internal) and as a client service (any organ provider).
"""

from levi.services.analysis import (
    AnalysisError,
    AnalysisReport,
    Finding,
    analyze_service,
    record_analysis,
)
from levi.services.offering import (
    SERVICE_TYPES,
    ServiceError,
    ServiceOffering,
    ServiceStore,
    attach_analysis,
    deliver_service,
    offer_service,
    quote_service,
    showcase_service,
)
from levi.services.job_search import (
    SERVICE_TYPE as JOB_SEARCH_SERVICE_TYPE,
    deliver_job_search,
    offer_job_search,
    quote_job_search,
    scan_opportunities,
    showcase_job_search,
)

__all__ = [
    "AnalysisError",
    "AnalysisReport",
    "Finding",
    "JOB_SEARCH_SERVICE_TYPE",
    "SERVICE_TYPES",
    "ServiceError",
    "ServiceOffering",
    "ServiceStore",
    "analyze_service",
    "attach_analysis",
    "deliver_job_search",
    "deliver_service",
    "offer_job_search",
    "offer_service",
    "quote_job_search",
    "quote_service",
    "record_analysis",
    "scan_opportunities",
    "showcase_job_search",
    "showcase_service",
]
