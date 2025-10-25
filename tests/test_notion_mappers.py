from integrations.notion.mappers import (
    NotionSyncItem,
    NotionUser,
    build_notion_update_payload,
    parse_notion_page,
)


def _sample_page():
    return {
        "id": "1234abcd-5678-ef00-1234-abcdef123456",
        "properties": {
            "Name": {
                "type": "title",
                "title": [{"plain_text": "Demo Issue"}],
            },
            "Status": {"type": "status", "status": {"name": "In Progress"}},
            "Assignee": {
                "type": "people",
                "people": [
                    {
                        "id": "user-1",
                        "name": "Ada Lovelace",
                        "person": {"email": "ada@example.com"},
                    }
                ],
            },
            "Labels": {
                "type": "multi_select",
                "multi_select": [{"name": "backend"}, {"name": "priority:high"}],
            },
            "GitHub URL": {"type": "url", "url": "https://github.com/PR-CYBR/test/issues/42"},
            "GitHub ID": {
                "type": "rich_text",
                "rich_text": [{"plain_text": "MDU6SXNzdWUxMjM0NTY="}],
            },
            "GitHub Number": {"type": "number", "number": 42},
            "Pull Requests": {
                "type": "relation",
                "relation": [
                    {"id": "1111aaaa-2222-bbbb-3333-cccc4444dddd"},
                    {"id": "eeeeffff-1111-2222-3333-444455556666"},
                ],
            },
        },
    }


def test_parse_notion_page_extracts_core_fields():
    page = parse_notion_page("issues", _sample_page())

    assert page.title == "Demo Issue"
    assert page.status == "In Progress"
    assert page.github_url == "https://github.com/PR-CYBR/test/issues/42"
    assert page.github_number == 42
    assert page.github_node_id == "MDU6SXNzdWUxMjM0NTY="
    assert page.relations["Pull Requests"] == [
        "1111aaaa-2222-bbbb-3333-cccc4444dddd",
        "eeeeffff-1111-2222-3333-444455556666",
    ]
    assert page.assignees[0].email == "ada@example.com"


def test_build_notion_update_payload_matches_expected_structure():
    item = NotionSyncItem(
        database_slug="issues",
        notion_page_id="1234abcd-5678-ef00-1234-abcdef123456",
        title="Demo Issue",
        status="In Progress",
        assignees=[NotionUser(id="user-1")],
        labels=["backend"],
        github_url="https://github.com/PR-CYBR/test/issues/42",
        github_node_id="MDU6SXNzdWUxMjM0NTY=",
        github_number=42,
        relations={
            "Pull Requests": ["1111aaaa-2222-bbbb-3333-cccc4444dddd"],
        },
    )

    payload = build_notion_update_payload(item)

    assert payload["properties"]["Name"]["title"][0]["text"]["content"] == "Demo Issue"
    assert payload["properties"]["Status"]["status"]["name"] == "In Progress"
    assert payload["properties"]["Assignee"]["people"][0]["id"] == "user-1"
    assert payload["properties"]["Labels"]["multi_select"][0]["name"] == "backend"
    assert payload["properties"]["GitHub URL"]["url"] == "https://github.com/PR-CYBR/test/issues/42"
    assert payload["properties"]["GitHub ID"]["rich_text"][0]["text"]["content"] == "MDU6SXNzdWUxMjM0NTY="
    assert payload["properties"]["GitHub Number"]["number"] == 42
    assert payload["properties"]["Pull Requests"]["relation"][0]["id"] == "1111aaaa-2222-bbbb-3333-cccc4444dddd"
