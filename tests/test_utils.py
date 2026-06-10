import pytest
import tempfile
import os
from pathlib import Path

from qa4sm_autoreports.utils import escape_latex, load_yml_to_dict, ValidationReportError


class TestEscapeLatex:
    def test_empty_and_no_special_chars(self):
        assert escape_latex("") == ""
        assert escape_latex("Hello World") == "Hello World"

    def test_all_special_chars(self):
        assert escape_latex("Tom & Jerry") == r"Tom \& Jerry"
        assert escape_latex("100% complete") == r"100\% complete"
        assert escape_latex("Price: $50") == r"Price: \$50"
        assert escape_latex("#tag") == r"\#tag"
        assert escape_latex("file_name") == r"file\_name"
        assert escape_latex("{content}") == r"\{content\}"
        assert escape_latex("user~name") == r"user\textasciitilde{}name"
        assert escape_latex("x^2") == r"x\textasciicircum{}2"
        result = escape_latex("path\\to\\file")
        assert r"\textbackslash" in result


class TestLoadYmlToDict:
    def test_load_valid_yaml(self, tmp_path):
        yaml_content = """
section1:
  key1: value1
  key2: 123
section2:
  key3: value3
"""
        yaml_file = tmp_path / "test.yml"
        yaml_file.write_text(yaml_content)

        result = load_yml_to_dict(yaml_file)
        assert result["section1"]["key1"] == "value1"
        assert result["section1"]["key2"] == 123
        assert result["section2"]["key3"] == "value3"

        result2 = load_yml_to_dict(Path(yaml_file))
        assert result2["section1"]["key1"] == "value1"

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError, match="No file found at:"):
            load_yml_to_dict("/nonexistent/path.yml")

    def test_load_real_yaml_file(self, tmp_path):
        import shutil
        testdata_src = Path(__file__).parent / "testdata" / "test_series" / "epoch1"
        testdata_dst = tmp_path / "testdata" / "test_series" / "epoch1"
        shutil.copytree(testdata_src, testdata_dst)
        
        yaml_path = testdata_dst / "ReportVars.yml"
        result = load_yml_to_dict(yaml_path)
        assert result["Common"]["qa4sm_version"] == "3.2.1"
        assert result["Common"]["interval_days"] == 91

    def test_invalid_extension_and_content(self, tmp_path):
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("key: value")
        with pytest.raises(ValueError, match="Expected a .yml/.yaml file"):
            load_yml_to_dict(txt_file)

        yaml_file = tmp_path / "test.yml"
        yaml_file.write_text("invalid: yaml: content: [")
        with pytest.raises(Exception):
            load_yml_to_dict(yaml_file)

        yaml_file.write_text("- item1\n- item2\n")
        with pytest.raises(ValueError, match="did not parse to a dictionary"):
            load_yml_to_dict(yaml_file)


class TestValidationReportError:
    def test_default_and_custom_message(self):
        error = ValidationReportError()
        assert error.message == "Validation report failed"
        assert str(error) == "Validation report failed"

        error2 = ValidationReportError("Custom error message")
        assert error2.message == "Custom error message"
        assert str(error2) == "Custom error message"
        assert issubclass(ValidationReportError, Exception)
