import os.path
import pandas as pd
import unittest
from datetime import datetime
from pathlib import Path
from tempfile import mkdtemp

from qa4sm_api.client_api import Connection
from qa4sm_autoreports.report import AutoReportCreator
from qa4sm_autoreports.run import ValidationRun

QA4SM = Connection("test.qa4sm.eu")
RUN_ID = "6eb61199-59b8-4ecc-8e3c-7b1139df4a05"

TEST_PATH = Path(os.path.dirname(os.path.abspath(__file__)))


class TestReportExistingRemote(unittest.TestCase):

    def setUp(self):
        tempdir = Path(mkdtemp())

        run1 = ValidationRun.from_remote(
            local_root=tempdir / "run1",
            connection=QA4SM,
            remote_id="bd9b2b74-0ac4-46ac-9562-ffe5c0ac3848"
        )

        run2 = ValidationRun.from_remote(
            local_root=tempdir / "run2",
            connection=QA4SM,
            remote_id="bcb88178-4f99-4e4b-b910-cac6d9178e28"
        )

        self.report = AutoReportCreator(runs=[run1, run2],
                                        report_root=tempdir)

    def tearDown(self):
        pass

    def test_instance(self):
        assert self.report[0].instance == QA4SM.session.instance

    def test_status(self):
        for _, run in self.report.runs.items():
            assert run.status[1] == 100
            assert run.status[0].lower() == "done"

        assert self.report.status == 2
        assert (self.report._STATUS_LUT[self.report.status].lower()
                == "processed")

    def test_verify_validations_complete(self):
        assert self.report.validations_complete()

    def test_verify_dataset_availability(self):
        assert self.report.verify_dataset_availability()

    def test_override_params(self):
        self.report.override_params(interval_from='1900-01-01',
                                    interval_to='1900-01-31')

        for _, run in self.report.runs.items():
            assert run.config.data['interval_from'] == '1900-01-01'
            assert run.config.data['interval_to'] == '1900-01-31'

    def test_report_rollback(self):
        pass

    def test_validation_run_table(self):
        df = self.report.validation_run_table()
        assert len(df) == len(self.report.runs)
        assert 'URL' in df.columns
        for date in df['Completed']:
            assert pd.to_datetime(date).to_pydatetime() < datetime.now()

    def test_download_data(self):
        assert self.report.status == 2
        self.report.download_all_results()
        for _, run in self.report.runs.items():
            runpath = run.local_root
            assert os.path.isfile(runpath / f"{run.remote_id}.nc")
            assert os.path.isfile(
                runpath / f"config-{run.connection.session.instance}.json")
            assert os.path.isfile(runpath / f"summary_stats.csv")
            assert len(os.listdir(runpath / f"qa4sm_graphics")) > 0

    def test_collect_content(self):
        self.report.download_all_results()
        assert self.report.status == 2
        self.report.collect_content()
        assert self.report.status == 3

        assert os.path.isfile(self.report.report_root / "common_extent.png")
        assert os.path.isfile(self.report.report_root / "ReportVars.yml")
        assert os.path.isfile(self.report.report_root / "val_run_list.csv")

        for _, run in self.report.runs.items():
            assert len(os.listdir(run.local_root / 'latex')) > 0
            assert os.path.isfile(run.local_root / "ContentVars.yml")

    def test_pdf_report_from_results(self):
        # Check whether creating a report
        self.report.download_all_results()
        self.report.compile(TEST_PATH / "latex_templates",
                            tex_ignore=["tracking.tex"])
        path = self.report.report_root
        assert os.path.exists(path / "pdf_report" / "main.pdf")
        assert os.path.exists(path / "pdf_report" / "references.bib")
        assert os.path.exists(path / "pdf_report" / "something.tex")
        assert os.path.exists(path / "pdf_report" / "main.tex")
        assert os.path.exists(path / "run1" / "run.tex")
        assert os.path.exists(path / "run2" / "run.tex")


if __name__ == '__main__':
    tests = TestReportExistingRemote()
    tests.setUp()
    tests.test_collect_content()