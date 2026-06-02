"""
Parse FC Velocity knowledge-base metadata for the dashboard overview cards.
"""

import os
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_DATA_DIR = _ROOT / "data"

_DOCUMENTS = [
    {
        "file": "players.txt",
        "title": "Player Profiles",
        "category": "Squad",
        "description": "Positions, baselines, and current medical status",
    },
    {
        "file": "injury_history.txt",
        "title": "Injury History",
        "category": "Clinical",
        "description": "Full injury timeline per player",
    },
    {
        "file": "treatment_protocols.txt",
        "title": "Treatment Protocols",
        "category": "Protocols",
        "description": "Muscle, ligament, and ACL rehab stages",
    },
    {
        "file": "return_to_play.txt",
        "title": "Return to Play",
        "category": "Protocols",
        "description": "Five-stage RTP framework and clearance tests",
    },
    {
        "file": "fitness_assessments.txt",
        "title": "Fitness Assessments",
        "category": "Performance",
        "description": "ACWR, readiness scores, and test results",
    },
    {
        "file": "prevention_guidelines.txt",
        "title": "Prevention Guidelines",
        "category": "Protocols",
        "description": "FIFA 11+, hamstring, ACL, and load management",
    },
    {
        "file": "medical_staff_guide.txt",
        "title": "Medical Staff Guide",
        "category": "Operations",
        "description": "Matchday protocols and emergency procedures",
    },
    {
        "file": "quick_reference.txt",
        "title": "Quick Reference",
        "category": "Clinical",
        "description": "Red flags, dosages, and taping techniques",
    },
    {
        "file": "clinical_notes.txt",
        "title": "Clinical Notes",
        "category": "Clinical",
        "description": "Physiotherapy assessments and session diary",
    },
]

_PROTOCOLS = [
    "Muscle strain (POLICE → RTP)",
    "Ligament sprain rehabilitation",
    "ACL reconstruction (9–12 months)",
    "Five-stage return-to-play framework",
    "FIFA 11+ warm-up programme",
    "Hamstring & ACL prevention",
    "Pre-season musculoskeletal screening",
]


def _parse_players(text: str) -> list[dict]:
    players: list[dict] = []
    squad = "First squad"

    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "FIRST SQUAD":
            squad = "First squad"
            continue
        if stripped == "RESERVE SQUAD":
            squad = "Reserve squad"
            continue
        if not stripped.startswith("Player ID:"):
            continue

        parts = [p.strip() for p in stripped.split("|")]
        if len(parts) < 3:
            continue

        player_id = parts[0].replace("Player ID:", "").strip()
        name = parts[1]
        position = parts[2]
        players.append(
            {
                "id": player_id,
                "name": name,
                "position": position,
                "squad": squad,
                "status": "cleared",
                "status_label": "Cleared",
            }
        )

    # Medical status lines follow player lines in the source file.
    blocks = re.split(r"(?=Player ID:)", text)
    for block in blocks:
        if "Medical status:" not in block:
            continue
        id_match = re.search(r"Player ID:\s*(PLR-\d+)", block)
        status_match = re.search(r"Medical status:\s*(.+)", block)
        if not id_match or not status_match:
            continue

        pid = id_match.group(1)
        status_text = status_match.group(1).strip()
        for player in players:
            if player["id"] != pid:
                continue
            if status_text.lower().startswith("active"):
                player["status"] = "active"
                player["status_label"] = "Active case"
            elif "load being managed" in status_text.lower():
                player["status"] = "monitoring"
                player["status_label"] = "Load managed"
            else:
                player["status"] = "cleared"
                player["status_label"] = "Cleared"
            break

    return players


def get_overview() -> dict:
    players_path = _DATA_DIR / "players.txt"
    players: list[dict] = []
    if players_path.is_file():
        players = _parse_players(players_path.read_text(encoding="utf-8"))

    documents = []
    for doc in _DOCUMENTS:
        path = _DATA_DIR / doc["file"]
        documents.append({**doc, "available": path.is_file()})

    active_players = [p for p in players if p["status"] in ("active", "monitoring")]
    protocol_docs = [d for d in documents if d["category"] == "Protocols"]

    return {
        "club": {
            "name": "FC Velocity",
            "league": "Israeli Premier League",
            "department": "First-team medical dept.",
        },
        "players": players,
        "player_count": len(players),
        "active_cases": active_players,
        "active_case_count": len(active_players),
        "documents": documents,
        "document_count": len([d for d in documents if d["available"]]),
        "protocols": _PROTOCOLS,
        "protocol_count": len(_PROTOCOLS),
        "protocol_doc_count": len(protocol_docs),
        "categories": {
            "Squad": len([d for d in documents if d["category"] == "Squad"]),
            "Clinical": len([d for d in documents if d["category"] == "Clinical"]),
            "Protocols": len([d for d in documents if d["category"] == "Protocols"]),
            "Performance": len([d for d in documents if d["category"] == "Performance"]),
            "Operations": len([d for d in documents if d["category"] == "Operations"]),
        },
    }
