"""Required-action register derived from typed obligations."""

from __future__ import annotations

from datetime import date, timedelta

from .models import Action, ContractDocument, Obligation
from .rules import extract_obligations


def build_actions(documents: list[ContractDocument]) -> list[Action]:
    actions: list[Action] = []
    for document in documents:
        for index, obligation in enumerate(extract_obligations(document, documents), start=1):
            due_date: str | None = None
            notice_window = "notice_window" in obligation.tags
            warning: str | None = None
            if notice_window:
                end = next((tag.split(":", 1)[1] for tag in obligation.tags if tag.startswith("term_end:")), None)
                days = next((int(tag.split(":", 1)[1]) for tag in obligation.tags if tag.startswith("notice_days:")), None)
                if end and days is not None:
                    due_date = (date.fromisoformat(end) - timedelta(days=days)).isoformat()
                    warning = f"Renewal notice must be received within the {days}-day notice window before term end."
            action_id = f"{document.document_id}-action-{index:03d}"
            title_map = {
                "pay": "Pay invoice",
                "deliver": "Complete delivery obligation",
                "notify": "Send required notice",
                "renew": "Review renewal or give non-renewal notice",
                "comply": "Maintain compliance with stated requirements",
                "terminate-right": "Review termination right and notice conditions",
            }
            actions.append(Action(
                action_id=action_id,
                title=title_map.get(obligation.obligation_type, "Review obligation"),
                owner=obligation.party,
                due_date=due_date,
                trigger=obligation.trigger,
                notice_window=notice_window,
                warning=warning,
                evidence=obligation.evidence,
            ))
    return sorted(actions, key=lambda action: (action.due_date is None, action.due_date or "9999-12-31", action.action_id))
