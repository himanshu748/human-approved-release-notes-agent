import pytest


@pytest.fixture
def source_data():
    return {
        "repository": "example/harbor",
        "version": "v1.4.0",
        "pull_requests": [
            {
                "number": 12,
                "title": "Add CSV export",
                "body": "Exports selected rows.",
                "labels": ["feature"],
                "url": "https://github.com/example/harbor/pull/12",
                "merged": True,
            },
            {
                "number": 3,
                "title": "Fix empty search",
                "body": "Returns an empty list.",
                "labels": ["bug"],
                "url": "https://github.com/example/harbor/pull/3",
                "merged": True,
            },
            {
                "number": 19,
                "title": "Unfinished work",
                "body": "",
                "labels": [],
                "url": "https://github.com/example/harbor/pull/19",
                "merged": False,
            },
        ],
    }
