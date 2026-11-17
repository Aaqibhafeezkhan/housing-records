import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

from pipeline.refresh_sources import (
    SOURCES,
    SourceError,
    collect_assets,
    latest_judgements_publication_date,
    register_publication_date,
    resolve_attachment,
)


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

    def test_register_date_comes_from_published_filename(self):
        self.assertEqual(
            register_publication_date("List_of_registered_providers_17_November_2026.xlsx"),
            "2026-11-17",
        )

    def test_register_date_rejects_unparseable_filename(self):
        with self.assertRaisesRegex(SourceError, "Cannot read a publication date"):
            register_publication_date("List_of_registered_providers_latest.xlsx")

    def test_refresh_is_limited_to_monthly_register_and_judgements(self):
        self.assertEqual(len(SOURCES), 2)
        self.assertIn("registered-providers-of-social-housing", SOURCES[0][0])
        self.assertIn("regulatory-judgements-and-enforcement-notices", SOURCES[1][0])

    def test_judgements_date_comes_from_latest_publication_date(self):
        class DateValues:
            empty = False

            def dropna(self):
                return self

            def max(self):
                return datetime(2026, 11, 12)

        class PublicationSheet:
            def __getitem__(self, column):
                self.asserted_column = column
                return "publication-date-values"

        sheet = PublicationSheet()
        pandas_stub = SimpleNamespace(
            read_excel=Mock(return_value=sheet),
            to_datetime=Mock(return_value=DateValues()),
        )
        with patch.dict("sys.modules", {"pandas": pandas_stub}):
            self.assertEqual(latest_judgements_publication_date("judgements.xlsx"), "2026-11-12")
        pandas_stub.read_excel.assert_called_once_with(
            "judgements.xlsx", sheet_name="Regulatory Judgements", usecols=["Publication Date"]
        )


if __name__ == "__main__":
    unittest.main()
