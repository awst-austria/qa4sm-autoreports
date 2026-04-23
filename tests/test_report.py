import os.path
import unittest
import shutil
from datetime import datetime
from pathlib import Path
from qa4sm_api.client_api import Connection
from qa4sm_autoreports.report import AutoReportCreator
from tempfile import mkdtemp

QA4SM_IP_OR_URL = "test.qa4sm.eu"
QA4SM_API_TOKEN = "2b37740a1f6733c9cfc2e1e105abe974ff8c4204"
RUN_ID = "6eb61199-59b8-4ecc-8e3c-7b1139df4a05"
QA4SM = Connection(QA4SM_IP_OR_URL, QA4SM_API_TOKEN)

TEST_PATH = Path(os.path.dirname(os.path.abspath(__file__)))


class TestReport(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tempdir = mkdtemp()
        cls.valrun = AutoReportCreator.from_scratch(
            cls.tempdir, TEST_PATH / "templates", QA4SM)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tempdir)

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_override_params(self):
        pass

    def test_validation_run_table(self):
        pass

    def test_report_from_results(self):
        # Check whether creating a report
        pass