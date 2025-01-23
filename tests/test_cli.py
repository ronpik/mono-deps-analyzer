import pytest
from pathlib import Path
from unittest.mock import patch, Mock
from mono_deps_analyzer.cli import main, validate_paths
from mono_deps_analyzer.analyzer import AnalysisResult

@pytest.fixture
def mock_project(tmp_path):
    """Create a minimal project structure for testing."""
    main_py = tmp_path / "main.py"
    main_py.write_text("import requests")
    return tmp_path

def test_validate_paths_success(mock_project):
    """Test path validation with existing paths."""
    assert validate_paths([str(mock_project)]) is None

def test_validate_paths_failure():
    """Test path validation with non-existent paths."""
    error = validate_paths(["/non/existent/path"])
    assert error is not None
    assert "does not exist" in error

@pytest.mark.parametrize("args,expected_code", [
    (["non_existent.py"], 1),
    ([], 2),  # SystemExit from argparse
])
def test_main_invalid_args(args):
    """Test main function with invalid arguments."""
    with patch("sys.argv", ["script"] + args):
        with pytest.raises((SystemExit, Exception)):
            main()

def test_main_success(mock_project):
    """Test successful execution of main function."""
    result = AnalysisResult()
    result.add_external_dependency("requests", "2.26.0")
    
    with patch("sys.argv", ["script", str(mock_project / "main.py")]):
        with patch("mono_deps_analyzer.cli.DependencyAnalyzer") as MockAnalyzer:
            mock_analyzer = Mock()
            mock_analyzer.analyze_project.return_value = result
            MockAnalyzer.return_value = mock_analyzer
            
            assert main() == 0
            mock_analyzer.write_requirements.assert_called_once()

def test_main_verbose(mock_project, capsys):
    """Test main function with verbose output."""
    result = AnalysisResult()
    result.add_external_dependency("requests", "2.26.0")
    result.add_local_module("local_module", Path("local_module.py"))
    
    with patch("sys.argv", ["script", str(mock_project / "main.py"), "-v"]):
        with patch("mono_deps_analyzer.cli.DependencyAnalyzer") as MockAnalyzer:
            mock_analyzer = Mock()
            mock_analyzer.analyze_project.return_value = result
            MockAnalyzer.return_value = mock_analyzer
            
            main()
            captured = capsys.readouterr()
            assert "Entry points:" in captured.out
            assert "requests" in captured.out
            assert "2.26.0" in captured.out

def test_main_custom_output(mock_project, tmp_path):
    """Test main function with custom output path."""
    output_file = tmp_path / "custom-requirements.txt"
    
    with patch("sys.argv", ["script", str(mock_project / "main.py"), "-o", str(output_file)]):
        with patch("mono_deps_analyzer.cli.DependencyAnalyzer") as MockAnalyzer:
            mock_analyzer = Mock()
            mock_analyzer.analyze_project.return_value = AnalysisResult()
            MockAnalyzer.return_value = mock_analyzer
            
            main()
            mock_analyzer.write_requirements.assert_called_once_with(str(output_file))

def test_main_multiple_entry_points(mock_project):
    """Test main function with multiple entry points."""
    entry_points = [mock_project / "main1.py", mock_project / "main2.py"]
    for ep in entry_points:
        ep.write_text("# test file")
    
    with patch("sys.argv", ["script"] + [str(ep) for ep in entry_points]):
        with patch("mono_deps_analyzer.cli.DependencyAnalyzer") as MockAnalyzer:
            mock_analyzer = Mock()
            mock_analyzer.analyze_project.return_value = AnalysisResult()
            MockAnalyzer.return_value = mock_analyzer
            
            assert main() == 0
            # Verify analyzer was called with both entry points
            call_args = mock_analyzer.analyze_project.call_args[0][0]
            assert len(call_args) == 2
            assert all(isinstance(arg, Path) for arg in call_args)

def test_main_with_additional_paths(mock_project):
    """Test main function with additional search paths."""
    additional_path = mock_project / "lib"
    additional_path.mkdir()
    
    with patch("sys.argv", ["script", str(mock_project / "main.py"), "-p", str(additional_path)]):
        with patch("mono_deps_analyzer.cli.DependencyAnalyzer") as MockAnalyzer:
            mock_analyzer = Mock()
            mock_analyzer.analyze_project.return_value = AnalysisResult()
            MockAnalyzer.return_value = mock_analyzer
            
            assert main() == 0
            # Verify analyzer was initialized with additional path
            MockAnalyzer.assert_called_once()
            paths_arg = MockAnalyzer.call_args[0][0]
            assert str(additional_path) in paths_arg

def test_main_error_handling(mock_project):
    """Test error handling in main function."""
    with patch("sys.argv", ["script", str(mock_project / "main.py")]):
        with patch("mono_deps_analyzer.cli.DependencyAnalyzer") as MockAnalyzer:
            mock_analyzer = Mock()
            mock_analyzer.analyze_project.side_effect = Exception("Test error")
            MockAnalyzer.return_value = mock_analyzer
            
            assert main() == 1

