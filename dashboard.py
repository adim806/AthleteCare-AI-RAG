"""
Parse FC Velocity data for the welcome-screen insight panel
(squad availability + documents by medical staff audience).
"""

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_DATA_DIR = _ROOT / "data"

_AUDIENCES = [
    {
        "id": "cmo",
        "role": "Chief Medical Officer",
        "lead": "Dr. Anat Shapira",
        "icon": "🩺",
        "documents": [
            {"file": "injury_history.txt", "title": "Injury History", "desc": "Full injury timeline and case IDs"},
            {"file": "return_to_play.txt", "title": "Return to Play", "desc": "Clearance criteria and RTP framework"},
            {"file": "concussion_protocol.txt", "title": "Concussion Protocol", "desc": "Graduated return-to-sport steps"},
            {"file": "squad_status_daily.txt", "title": "Daily Squad Status", "desc": "Availability snapshot and flags"},
            {"file": "medical_staff_guide.txt", "title": "Medical Staff Guide", "desc": "Matchday authority and emergency procedures"},
        ],
    },
    {
        "id": "lead_physio",
        "role": "Lead Physiotherapist",
        "lead": "Dr. Sara Cohen",
        "icon": "📋",
        "documents": [
            {"file": "treatment_protocols.txt", "title": "Treatment Protocols", "desc": "Muscle, ligament, and ACL rehab stages"},
            {"file": "clinical_notes_active.txt", "title": "Active Clinical Notes", "desc": "Current assessments and session diary"},
            {"file": "clinical_notes_archive.txt", "title": "Clinical Notes Archive", "desc": "Historical physiotherapy records"},
            {"file": "return_to_play.txt", "title": "Return to Play", "desc": "Stage progression and clearance tests"},
            {"file": "players.txt", "title": "Player Profiles", "desc": "Medical status and active injury cases"},
        ],
    },
    {
        "id": "physio",
        "role": "Physiotherapist",
        "lead": "Dr. Yoel Mizrahi",
        "icon": "🦴",
        "documents": [
            {"file": "treatment_protocols.txt", "title": "Treatment Protocols", "desc": "Hands-on rehab and loading progressions"},
            {"file": "clinical_notes_active.txt", "title": "Active Clinical Notes", "desc": "Treatment sessions and ROM findings"},
            {"file": "quick_reference.txt", "title": "Quick Reference", "desc": "Red flags, taping, and clinical dosages"},
            {"file": "prevention_guidelines.txt", "title": "Prevention Guidelines", "desc": "FIFA 11+ and neuromuscular programmes"},
        ],
    },
    {
        "id": "fitness",
        "role": "Fitness & Conditioning Coach",
        "lead": "Tal Ben-David",
        "icon": "📈",
        "documents": [
            {"file": "fitness_assessments.txt", "title": "Fitness Assessments", "desc": "ACWR, Yo-Yo, sprint, and readiness scores"},
            {"file": "prevention_guidelines.txt", "title": "Prevention Guidelines", "desc": "Load management and screening protocols"},
            {"file": "players.txt", "title": "Player Profiles", "desc": "Performance metrics and load flags"},
            {"file": "squad_status_daily.txt", "title": "Daily Squad Status", "desc": "ACWR and availability for session planning"},
        ],
    },
    {
        "id": "nutrition",
        "role": "Sports Nutritionist",
        "lead": "Daniela Ronen",
        "icon": "🥗",
        "documents": [
            {"file": "nutrition_plans.txt", "title": "Nutrition Plans", "desc": "Individual diet protocols and supplementation"},
            {"file": "fitness_assessments.txt", "title": "Fitness Assessments", "desc": "Body composition and recovery nutrition context"},
            {"file": "players.txt", "title": "Player Profiles", "desc": "Dietary requirements linked to medical cases"},
            {"file": "prevention_guidelines.txt", "title": "Prevention Guidelines", "desc": "Hydration and recovery nutrition guidance"},
        ],
    },
]


def _parse_squad_status(text: str) -> dict:
    last_updated = ""
    m = re.search(r"LAST_UPDATED:\s*(.+?)\s*\|", text)
    if m:
        last_updated = m.group(1).strip()

    def _parse_player_lines(block_name: str, status: str) -> list[dict]:
        pattern = rf"{re.escape(block_name)}\s*\((\d+)\):\s*\n((?:\s*-\s*.+\n?)*)"
        match = re.search(pattern, text)
        if not match:
            return []
        players = []
        for line in match.group(2).splitlines():
            line = line.strip()
            if not line.startswith("-") or line == "---":
                continue
            entry = line.lstrip("- ").strip()
            if not entry or entry.startswith("---"):
                continue
            id_match = re.match(r"(PLR-\d+)\s+(.+?)\s+—\s+(.+)", entry)
            if id_match:
                players.append(
                    {
                        "id": id_match.group(1),
                        "name": id_match.group(2).strip(),
                        "detail": id_match.group(3).strip(),
                        "status": status,
                    }
                )
        return players

    unavailable = _parse_player_lines("PLAYERS_UNAVAILABLE_FOR_TRAINING", "unavailable")
    modified = _parse_player_lines("PLAYERS_AVAILABLE_MODIFIED_TRAINING", "modified")
    cleared = _parse_player_lines("PLAYERS_CLEARED_FULL_TRAINING", "cleared")

    cleared_count = len(cleared)
    m = re.search(r"PLAYERS_CLEARED_FULL_TRAINING\s*\((\d+)\)", text)
    if m:
        header_count = int(m.group(1))
        if header_count and (not cleared_count or cleared_count != header_count):
            cleared_count = header_count

    total = len(unavailable) + len(modified) + cleared_count

    return {
        "last_updated": last_updated,
        "total_players": total,
        "cleared_count": cleared_count,
        "unavailable": unavailable,
        "modified": modified,
        "cleared": cleared,
        "not_fit": unavailable + modified,
    }


def get_dashboard() -> dict:
    squad_path = _DATA_DIR / "squad_status_daily.txt"
    squad: dict = {
        "last_updated": "",
        "total_players": 10,
        "cleared_count": 0,
        "unavailable": [],
        "modified": [],
        "cleared": [],
        "not_fit": [],
    }
    if squad_path.is_file():
        squad = _parse_squad_status(squad_path.read_text(encoding="utf-8"))

    audiences = []
    for aud in _AUDIENCES:
        docs = []
        for doc in aud["documents"]:
            path = _DATA_DIR / doc["file"]
            docs.append({**doc, "available": path.is_file()})
        audiences.append(
            {
                "id": aud["id"],
                "role": aud["role"],
                "lead": aud["lead"],
                "icon": aud["icon"],
                "document_count": len([d for d in docs if d["available"]]),
                "documents": docs,
            }
        )

    return {
        "club": {"name": "FC Velocity", "department": "First-team medical dept."},
        "squad": squad,
        "audiences": audiences,
    }
