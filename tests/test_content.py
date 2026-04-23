import os.path
import unittest
import shutil
import pandas as pd

from qa4sm_api.client_api import Connection
from qa4sm_autoreports.report import AutoReportCreator
from qa4sm_autoreports.run import ValidationRun
from tempfile import mkdtemp
from pathlib import Path

QA4SM_IP_OR_URL = "test.qa4sm.eu"
QA4SM_API_TOKEN = "2b37740a1f6733c9cfc2e1e105abe974ff8c4204"
RUN1_NAME = "01-SmosL2-vs-C3sComb-abs"
RUN1_ID = "6eb61199-59b8-4ecc-8e3c-7b1139df4a05"
RUN2_NAME = "02-SmosL2-vs-Era5Land-abs"
RUN2_ID = "e95eeaeb-1d2f-43c4-b019-b7f3b3dbd29e"

QA4SM = Connection(QA4SM_IP_OR_URL, QA4SM_API_TOKEN)


class TestReportCompiler(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        tempdir = Path(mkdtemp())

        path_run1 = tempdir / 'run1'
        path_run2 = tempdir / 'run2'

        run1 = ValidationRun.from_remote(path_run1, QA4SM, RUN1_ID)
        run2 = ValidationRun.from_remote(path_run2, QA4SM, RUN2_ID)

        cls.compiler = AutoReportCreator([run1, run2],
                                         series_root=tempdir)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tempdir)

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_is_ready(self):
        assert self.compiler.validations_complete()
        self.__class__._stage = 1  # data collection stage

    def test_download_data(self):
        self.compiler.download_all_results()

        path_run1 = self.compiler.runs[0].local_root
        nc1 = self.compiler.runs[0].remote_id + ".nc"
        assert os.path.exists(path_run1/ nc1)
        assert os.path.exists(path_run1 / "config.json")
        assert os.path.exists(path_run1 / "summary_stats.csv")

        path_run2 = self.compiler.runs[1].local_root
        nc2 = self.compiler.runs[1].remote_id + ".nc"
        assert os.path.exists(path_run2 / nc2)
        assert os.path.exists(path_run2 / "config.json")
        assert os.path.exists(path_run2 / "summary_stats.csv")

        self.__class__._stage = 1  # data collection stage

    def test_validation_run_table(self):
        table = self.compiler.validation_run_table(short_url=True)
        assert len(table.index) == 2
        assert table['URL'].values[0].startswith(r'\href')
        assert table['Reference'].values[0] == "SMOS Level 2 (v700)"
        assert table['Completed'].values[0] == "2025-12-01 21:51"

        self.__class__._stage = 2  # compilation stage

    def test_collect_content(self):
        path_run1 = self.compiler.runs[0].local_root
        path_run2 = self.compiler.runs[1].local_root
        path_report = self.compiler.report_root

        self.compiler.collect_content(force_download=False)
        assert os.path.exists(path_report / "val_run_list.csv")
        df = pd.read_csv(path_report / "val_run_list.csv", sep=';')
        assert len(df.index) == 2

        assert os.path.exists(path_report / "val_run_list.csv")
        assert os.path.exists(path_report / "ReportVars.csv")

        assert os.path.exists(path_report / "run1" / "ContentVars.yml")

        self.__class__._stage = 2  # compilation stage

if __name__ == '__main__':
    tests = TestReportCompiler()
    tests.setUpClass()
    tests.setUp()
    tests.test_is_ready()
    tests.test_download_data()
    tests.test_validation_run_table()
    tests.test_collect_content()