from workflows.material_inventory_query.nodes import generate_inventory_reply
from workflows.state import WorkflowGraphState


def test_generate_inventory_reply_single_material():
    state: WorkflowGraphState = {
        "collected_fields": {
            "material_name": "cement",
            "inventory_levels": [
                {
                    "material_name": "cement",
                    "unit": "bags",
                    "received": 50.0,
                    "used": 20.0,
                    "current_stock": 30.0,
                }
            ],
        }
    }

    result = generate_inventory_reply(state)
    prompt = result["pending_prompt"]

    assert "Cement" in prompt
    assert "In stock: 30 bags" in prompt
    assert "Received  50 bags" in prompt
    assert "Used      20 bags" in prompt


def test_generate_inventory_reply_all_materials():
    state: WorkflowGraphState = {
        "collected_fields": {
            "inventory_levels": [
                {
                    "material_name": "cement",
                    "unit": "bags",
                    "received": 50.0,
                    "used": 20.0,
                    "current_stock": 30.0,
                },
                {
                    "material_name": "steel",
                    "unit": "kg",
                    "received": 100.0,
                    "used": 0.0,
                    "current_stock": 100.0,
                },
            ],
        }
    }

    result = generate_inventory_reply(state)
    prompt = result["pending_prompt"]

    assert "Cement" in prompt
    assert "Steel" in prompt
    assert "30 bags" in prompt
    assert "100 kg" in prompt


def test_generate_inventory_reply_no_data_for_named_material():
    state: WorkflowGraphState = {
        "collected_fields": {"material_name": "sand", "inventory_levels": []}
    }
    result = generate_inventory_reply(state)
    assert "sand" in result["pending_prompt"]
    assert "don't have" in result["pending_prompt"]


def test_generate_inventory_reply_no_data_at_all():
    state: WorkflowGraphState = {"collected_fields": {}}
    result = generate_inventory_reply(state)
    assert "don't have any recorded material stock" in result["pending_prompt"]


def test_fractional_quantity_formats_without_trailing_zero():
    state: WorkflowGraphState = {
        "collected_fields": {
            "material_name": "steel",
            "inventory_levels": [
                {
                    "material_name": "steel",
                    "unit": "kg",
                    "received": 12.5,
                    "used": 2.5,
                    "current_stock": 10.0,
                }
            ],
        }
    }
    result = generate_inventory_reply(state)
    prompt = result["pending_prompt"]
    assert "In stock: 10 kg" in prompt
    assert "Received  12.5 kg" in prompt
    assert "Used      2.5 kg" in prompt
