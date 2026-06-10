import os.path
import unittest
import shutil
import pandas as pd
import matplotlib
matplotlib.use('Agg')
from tempfile import mkdtemp
from pathlib import Path

from qa4sm_api.client_api import Connection
from qa4sm_autoreports.report import AutoReportCreator
from qa4sm_autoreports.run import ValidationRun

QA4SM = Connection("test.qa4sm.eu")
TEST_PATH = Path(os.path.dirname(os.path.abspath(__file__)))


class TestReportCompilerLocal(unittest.TestCase):

    def setUp(self):
        self.tempdir = Path(mkdtemp())
        shutil.copytree(
            TEST_PATH / "testdata" / "test_series" / "epoch1" / "run1",
            self.tempdir / "run1"
        )

        run1 = ValidationRun.from_results(self.tempdir / "run1", connection=QA4SM)
        self.compiler = AutoReportCreator(
            [run1], report_root=self.tempdir)

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def test_is_ready(self):
        assert self.compiler.validations_complete()

    def test_connected_remote(self):
        run_status = self.compiler[0].status
        assert run_status == ("DONE", 100)
        report_status = self.compiler.status
        assert self.compiler._STATUS_LUT[report_status].lower() == 'processed'

    def test_validation_run_table(self):
        table = self.compiler.validation_run_table(short_url=True)
        assert len(table.index) == len(self.compiler)
        assert table['URL'].values[0].startswith(r'\href')
        assert table['Completed'].values[0] == "2026-04-28 07:44"

    def test_collect_content(self):
        path_report = self.compiler.report_root

        self.compiler.collect_content(force_download=False)

        for _, run in self.compiler.runs.items():
            assert os.path.isfile(
                os.path.join(path_report, "run1", f"{run.remote_id}.nc")
            )

        assert os.path.exists(path_report / "val_run_list.csv")
        df = pd.read_csv(path_report / "val_run_list.csv", sep=';')
        assert len(df.index) == len(self.compiler)
        assert os.path.exists(path_report / "val_run_list.csv")
        assert os.path.exists(path_report / "ReportVars.yml")
        assert os.path.exists(path_report / "common_extent.png")
        assert os.path.exists(path_report / "run1" / "ContentVars.yml")


class TestReportCompilerRemote(unittest.TestCase):

    def setUp(self):
        self.tempdir = Path(mkdtemp())
        self.reference_data = TEST_PATH / "testdata" / "test_series" / "epoch1" / "run1"
        run1 = ValidationRun.from_remote(
            self.tempdir / "run1",
            connection=QA4SM,
            remote_id="d9cf81c7-5c1c-4341-8a0c-4d6fcfb91677")

        self.report = AutoReportCreator(
            [run1], report_root=self.tempdir)

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def test_download_data(self):
        self.report.download_all_results()

        path_run1 = self.report[0].local_root
        nc1 = self.report[0].remote_id + ".nc"

        with open(path_run1 / nc1, 'rb') as f:
            assert f.read() == (self.reference_data / nc1).read_bytes()
        with open(path_run1 / "summary_stats.csv", 'rb') as f:
            assert f.read() == (self.reference_data / "summary_stats.csv").read_bytes()

        downloaded_graphics = path_run1 / "qa4sm_graphics"
        reference_graphics = self.reference_data / "qa4sm_graphics"
        assert downloaded_graphics.exists()
        assert reference_graphics.exists()

        downloaded_files = sorted([f.name for f in downloaded_graphics.iterdir()])
        reference_files = sorted([f.name for f in reference_graphics.iterdir()])
        assert downloaded_files == reference_files

        for fname in downloaded_files:
            with open(downloaded_graphics / fname, 'rb') as f:
                assert f.read() == (reference_graphics / fname).read_bytes()



if __name__ == '__main__':
    tests = TestReportCompilerLocal()
    tests.setUp()
    tests.test_is_ready()
    tests.test_download_data()
    tests.test_validation_run_table()
    tests.test_collect_content()