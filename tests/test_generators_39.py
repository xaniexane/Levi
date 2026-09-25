"""Proof: every one of the 39 original-catalog generators compiles a
valid blueprint into real, non-empty scaffold files.

This is the machine-checkable proof behind the law "every recovered
hunt element is built in LEVI, not merely documented": each generator
is exercised end-to-end through ``compile_blueprint``.
"""

import pytest

from levi.revival.omega import blueprint as bp
from levi.revival.omega import generators as gen

# The 39 product types of the original Omega Platform catalog.
ORIGINAL_39 = [
    "webpage", "app", "streamlit_app", "saas_landing", "widget",
    "mobile_app", "electron_app", "documentation_site", "static_site",
    "fastapi_service", "rest_api", "graphql_api", "cli_tool",
    "python_package", "npm_package", "api_client", "automation",
    "workflow", "bot", "slack_app", "discord_bot", "webhook_handler",
    "zapier_integration", "agent", "skill", "mcp_server",
    "langchain_chain", "chrome_extension", "vscode_extension",
    "plugin", "docker_compose", "database_schema", "terraform_infra",
    "kubernetes_manifest", "spreadsheet", "email_template",
    "pdf_report", "game", "iot_firmware",
]


def _blueprint(ptype: str) -> dict:
    return {
        "name": "proof-app",
        "title": "Proof App",
        "prompt": f"build a {ptype.replace('_', ' ')} for testing",
        "product_types": [ptype],
        "components": [],
        "layers": [],
        "artifacts": [],
    }


def test_catalog_covers_all_original_types():
    for ptype in ORIGINAL_39:
        assert ptype in bp.PRODUCT_TYPES, f"missing from catalog: {ptype}"


def test_every_generator_registered():
    for ptype in ORIGINAL_39:
        assert ptype in gen.registered(), f"not registered: {ptype}"


@pytest.mark.parametrize("ptype", ORIGINAL_39)
def test_generator_compiles_to_real_files(ptype):
    blueprint = _blueprint(ptype)
    check = bp.validate_blueprint(blueprint)
    assert check["ok"], f"blueprint rejected for {ptype}: {check['errors']}"
    result = gen.compile_blueprint(blueprint)
    assert result["ok"], f"errors for {ptype}: {result['errors']}"
    assert result["files"], f"no files produced for {ptype}"
    for path, content in result["files"].items():
        assert isinstance(content, str) and content.strip(), (
            f"empty file {path} for {ptype}"
        )
        # Honest provenance: every generated file names its origin.
        assert "LEVI" in content, f"no provenance in {path} for {ptype}"


def test_compile_all_39_together_has_no_crashes():
    # A blueprint requesting everything must never crash the compiler;
    # path collisions (if any) are recorded as errors, not raised.
    blueprint = _blueprint("webpage")
    blueprint["product_types"] = list(ORIGINAL_39)
    result = gen.compile_blueprint(blueprint)
    assert isinstance(result["files"], dict)
    assert isinstance(result["errors"], list)
    assert result["files"], "expected at least some files from a full compile"
