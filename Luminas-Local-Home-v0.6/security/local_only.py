"""Honest local-only validation for the software prototype."""
from pathlib import Path
import ast


FORBIDDEN_IMPORT_ROOTS = {
    "openai", "anthropic", "boto3", "google", "googleapiclient",
    "requests", "httpx", "aiohttp", "azure", "firebase_admin",
}


class LocalOnlyValidator:
    def __init__(self, project_root=None):
        self.project_root = Path(project_root) if project_root else Path(__file__).resolve().parents[1]

    def scan_python_imports(self):
        findings = []
        for path in self.project_root.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except (OSError, SyntaxError) as exc:
                findings.append({"file": str(path), "finding": f"PARSE_ERROR: {exc}"})
                continue
            for node in ast.walk(tree):
                imported = None
                if isinstance(node, ast.Import):
                    imported = node.names[0].name.split(".")[0]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported = node.module.split(".")[0]
                if imported in FORBIDDEN_IMPORT_ROOTS:
                    findings.append({"file": str(path.relative_to(self.project_root)), "finding": imported})
        return findings

    def validate(self, runtime):
        privacy = runtime.privacy.snapshot()
        guard = runtime.network.guard.snapshot()
        imports = self.scan_python_imports()
        return {
            "passed": (
                not imports
                and privacy["external_apis"] is False
                and privacy["cloud"] is False
                and privacy["bytes_transmitted"] == 0
            ),
            "internet_dependency": "NONE" if privacy["internet"] is False else "CONFIGURED",
            "cloud_dependency": "NONE" if privacy["cloud"] is False else "CONFIGURED",
            "external_api_dependency": "NONE" if privacy["external_apis"] is False and not imports else "DETECTED",
            "application_external_transmission_bytes": privacy["bytes_transmitted"],
            "blocked_external_attempts": guard["blocked_external_attempts"],
            "source_import_findings": imports,
            "measurement_scope": "APPLICATION_LEVEL",
            "host_network_capture": False,
            "honesty_note": "Zero transmitted bytes is validated at Luminas application transport boundaries; host-level packet capture is not claimed.",
        }
