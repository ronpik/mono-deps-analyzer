import pytest
from pathlib import Path
from unittest.mock import patch, mock_open
from mono_deps_analyzer.analyzer import (
    ImportAnalyzer,
    DependencyAnalyzer,
    ModuleInfo,
    AnalysisResult
)

@pytest.fixture
def temp_project(tmp_path):
    """Create a temporary project structure."""
    project = tmp_path / "project"
    project.mkdir()
    
    # Create main service file
    service = project / "service"
    service.mkdir()
    main_py = service / "main.py"
    main_py.write_text("""
import os
import json
from shared.database import connect
from shared.utils.helpers import format_data
import requests
from external_pkg import something
""")

    # Create shared modules
    shared = project / "shared"
    shared.mkdir()
    
    db_pkg = shared / "database"
    db_pkg.mkdir()
    (db_pkg / "__init__.py").write_text("""
import sqlalchemy
import shared.utils.config as config
""")

    utils = shared / "utils"
    utils.mkdir()
    (utils / "__init__.py").touch()
    (utils / "helpers.py").write_text("""
from datetime import datetime
import pandas
""")
    (utils / "config.py").write_text("CONFIG = {}")

    return project

def test_import_analyzer_stdlib():
    """Test standard library import detection."""
    code = "import os\nfrom json import loads"
    analyzer = ImportAnalyzer([])
    tree = compile(code, '<string>', 'exec', ast.PY_AST_ONLY)
    analyzer.visit(tree)
    assert not analyzer.external_packages
    assert not analyzer.found_imports

def test_import_analyzer_external():
    """Test external package import detection."""
    code = "import requests\nfrom pandas import DataFrame"
    analyzer = ImportAnalyzer([])
    tree = compile(code, '<string>', 'exec', ast.PY_AST_ONLY)
    analyzer.visit(tree)
    assert analyzer.external_packages == {'requests', 'pandas'}

def test_import_analyzer_local(temp_project):
    """Test local module import detection."""
    code = "from shared.database import connect"
    analyzer = ImportAnalyzer([str(temp_project)])
    tree = compile(code, '<string>', 'exec', ast.PY_AST_ONLY)
    analyzer.visit(tree)
    
    assert len(analyzer.found_imports) == 1
    module = next(iter(analyzer.found_imports))
    assert module.import_path == "shared.database"
    assert module.file_path.name == "__init__.py"
    assert module.is_package

@pytest.mark.parametrize("import_stmt,expected_path", [
    ("import shared.database", "shared/database/__init__.py"),
    ("from shared.utils import helpers", "shared/utils/helpers.py"),
    ("from shared.utils.helpers import format_data", "shared/utils/helpers.py"),
])
def test_module_resolution(temp_project, import_stmt, expected_path):
    """Test different import patterns resolution."""
    analyzer = ImportAnalyzer([str(temp_project)])
    tree = compile(import_stmt, '<string>', 'exec', ast.PY_AST_ONLY)
    analyzer.visit(tree)
    
    assert len(analyzer.found_imports) == 1
    module = next(iter(analyzer.found_imports))
    assert str(module.file_path.relative_to(temp_project)) == expected_path

def test_dependency_analyzer(temp_project):
    """Test full project analysis."""
    entry_point = temp_project / "service" / "main.py"
    analyzer = DependencyAnalyzer([str(temp_project)])
    
    with patch('mono_deps_analyzer.analyzer.importlib.metadata.version') as mock_version:
        mock_version.side_effect = lambda x: "1.0.0" if x in {"requests", "sqlalchemy", "pandas"} else None
        result = analyzer.analyze_project([entry_point])
    
    assert "requests" in result.external_dependencies
    assert "sqlalchemy" in result.external_dependencies
    assert "pandas" in result.external_dependencies
    
    local_modules = {str(p) for p in result.processed_files}
    assert len(local_modules) >= 4  # main.py, database/__init__.py, utils/helpers.py, utils/config.py

def test_write_requirements(tmp_path):
    """Test requirements.txt generation."""
    analyzer = DependencyAnalyzer([])
    analyzer.result.external_dependencies = {
        "requests": "2.26.0",
        "pandas": "1.3.0",
        "unknown-pkg": None
    }
    
    output_file = tmp_path / "requirements.txt"
    analyzer.write_requirements(str(output_file))
    
    content = output_file.read_text()
    assert "requests==2.26.0" in content
    assert "pandas==1.3.0" in content
    assert "unknown-pkg\n" in content

def test_analysis_result():
    """Test AnalysisResult operations."""
    result = AnalysisResult()
    
    result.add_external_dependency("requests", "2.26.0")
    result.add_local_module("shared.utils", Path("/path/to/utils.py"))
    
    assert "requests" in result.external_dependencies
    assert result.external_dependencies["requests"] == "2.26.0"
    assert len(result.processed_files) == 1
    assert len(result.local_modules) == 1

def test_module_info():
    """Test ModuleInfo functionality."""
    info = ModuleInfo(
        import_path="shared.utils",
        file_path=Path("/path/to/utils.py"),
        is_package=False
    )
    
    assert info.import_path == "shared.utils"
    assert isinstance(info.file_path, Path)
    assert info.is_package is False

