from workflows.state import WorkflowGraphState
from workflows.who_am_i.nodes import generate_identity_reply


def test_generate_identity_reply():
    state: WorkflowGraphState = {
        "collected_fields": {
            "actor_profile": {
                "full_name": "Test User",
                "role": "site_engineer",
                "org_name": "Acme Corp",
                "projects": [
                    {
                        "name": "Project Alpha",
                        "location": "North Site",
                        "status": "in_progress",
                    }
                ],
                "sites": [{"name": "Site A"}],
            }
        }
    }

    result = generate_identity_reply(state)
    prompt = result["pending_prompt"]

    assert "Test User" in prompt
    assert "Site Engineer" in prompt
    assert "Acme Corp" in prompt
    assert "Project Alpha" in prompt
    assert "North Site" in prompt
    assert "In Progress" in prompt
    assert "Site A" in prompt


def test_generate_identity_reply_empty_profile():
    state: WorkflowGraphState = {"collected_fields": {}}
    result = generate_identity_reply(state)
    assert "I don't have your full profile" in result["pending_prompt"]
