import pytest

from scripts.lib.workshop import Blocked, choose_subscription, scope_plan


def test_subscription_selection_does_not_fall_back():
    account = {"name": "MVP Credit Ext", "id": "approved", "tenantId": "tenant", "state": "Enabled"}
    assert choose_subscription([account, {**account, "name": "Azure for Students", "id": "other"}])["id"] == "approved"
    with pytest.raises(Blocked):
        choose_subscription([{**account, "name": "Student"}])
    with pytest.raises(Blocked):
        choose_subscription([account, {**account, "name": "MVP", "id": "ambiguous"}])


def test_plan_rejects_foreign_resources_and_replacements():
    target = {"id": "approved", "tenantId": "tenant"}
    plan = {"variables": {"subscription_id": {"value": "approved"}, "tenant_id": {"value": "tenant"}},
            "resource_changes": [{"type": "azurerm_container_app", "address": "foreign", "change": {
                "actions": ["update"], "after": {"resource_group_name": "production"}}}]}
    with pytest.raises(Blocked, match="Foreign"):
        scope_plan(plan, target, "rg-apiaddicts")
    plan["resource_changes"][0]["change"] = {"actions": ["delete", "create"], "after": {}}
    with pytest.raises(Blocked, match="Replacement"):
        scope_plan(plan, target, "rg-apiaddicts")
    plan["variables"]["subscription_id"]["value"] = "other"
    with pytest.raises(Blocked, match="subscription"):
        scope_plan(plan, target, "rg-apiaddicts")