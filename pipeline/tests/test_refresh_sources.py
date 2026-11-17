import unittest

from pipeline.refresh_sources import SourceError, collect_assets, resolve_attachment


class AttachmentDiscoveryTests(unittest.TestCase):
    def test_collects_nested_assets_and_ignores_non_asset_links(self):
        page = {
            "details": {
                "attachments": [{
                    "title": "Dataset",
                    "assets": [{
                        "filename": "dataset.xlsx",
                        "url": "https://assets.publishing.service.gov.uk/dataset.xlsx",
                    }],
                }]
            },
            "links": {"self": {"href": "https://www.gov.uk/example"}},
        }
        self.assertEqual(
            collect_assets(page),
            [{"name": "dataset.xlsx", "url": "https://assets.publishing.service.gov.uk/dataset.xlsx"}],
        )

    def test_resolves_one_matching_attachment(self):
        page = {"details": {"attachments": [{"assets": [
            {"filename": "old.xlsx", "url": "https://example.test/old.xlsx"},
            {"filename": "current.xlsx", "url": "https://example.test/current.xlsx"},
        ]}]}}
        self.assertEqual(resolve_attachment(page, r"current\.xlsx")["url"],
                         "https://example.test/current.xlsx")

    def test_missing_attachment_fails_loudly(self):
        with self.assertRaisesRegex(SourceError, "found 0"):
            resolve_attachment({"details": {"attachments": []}}, r"current\.xlsx")

    def test_ambiguous_attachment_fails_loudly(self):
        page = {"attachments": [
            {"filename": "current.xlsx", "url": "https://example.test/a/current.xlsx"},
            {"filename": "current.xlsx", "url": "https://example.test/b/current.xlsx"},
        ]}
        with self.assertRaisesRegex(SourceError, "found 2"):
            resolve_attachment(page, r"current\.xlsx")

    def test_duplicate_nested_asset_is_returned_once(self):
        asset = {"filename": "current.xlsx", "url": "https://example.test/current.xlsx"}
        self.assertEqual(len(collect_assets({"a": asset, "b": asset})), 1)


if __name__ == "__main__":
    unittest.main()
