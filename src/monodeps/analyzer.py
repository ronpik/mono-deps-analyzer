import ast
import os
import sys
import argparse
from pathlib import Path
from typing import Set, Dict, List, Optional, Tuple
from packaging.requirements import Requirement
from packaging.version import Version, parse
from importlib import metadata

class ImportAnalyzer(ast.NodeVisitor):
    """Analyzes Python files for their imports."""

    def __init__(self, local_paths: List[str]):
        self.project_imports: Set[str] = set()  # Full import paths
        self.external_imports: Set[str] = set()  # External package names
        self.stdlib_modules = self._get_stdlib_modules()
        self.local_paths = local_paths
        self.files_to_process: Set[Tuple[str, Path]] = set()  # (import_path, file_path)

    def _get_stdlib_modules(self) -> Set[str]:
        """Get a set of all standard library module names."""
        import sysconfig
        stdlib_path = sysconfig.get_path('stdlib')
        stdlib_modules = set()

        # Add known stdlib modules
        for path in Path(stdlib_path).rglob('*.py'):
            parts = path.relative_to(stdlib_path).parts
            if parts[0] == '__pycache__':
                continue
            module_name = parts[0].split('.')[0]
            stdlib_modules.add(module_name)

        # Add built-in modules
        stdlib_modules.update(sys.builtin_module_names)
        return stdlib_modules

    def visit_Import(self, node: ast.Import) -> None:
        """Process Import nodes (e.g., 'import foo.bar')."""
        for name in node.names:
            self._process_import(name.name)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Process ImportFrom nodes (e.g., 'from foo.bar import baz')."""
        if node.module:
            self._process_import(node.module)

    def _find_module_file(self, import_parts: List[str]) -> Optional[Tuple[Path, bool]]:
        """
        Find the corresponding file for a module path.
        Returns tuple of (file_path, is_package).
        """
        search_paths = (
            self.local_paths
            + list(filter(None, os.getenv('PYTHONPATH', '').split(os.pathsep)))
            + list(filter(None, os.getenv('PATH', '').split(os.pathsep)))
        )

        for base_path in search_paths:
            current_path = Path(base_path)

            # Try as a direct module first
            full_module_path = current_path.joinpath(*import_parts)
            module_file = full_module_path.with_suffix('.py')
            if module_file.exists():
                return module_file, False

            # Try as a package (with __init__.py)
            init_file = full_module_path / '__init__.py'
            if init_file.exists():
                return init_file, True

            # Handle the case where it might be a submodule in a package
            for i in range(len(import_parts)):
                partial_path = current_path.joinpath(*import_parts[:i+1])
                if (partial_path / '__init__.py').exists():
                    remaining_parts = import_parts[i+1:]
                    if remaining_parts:
                        submodule = partial_path.joinpath(*remaining_parts)
                        submodule_file = submodule.with_suffix('.py')
                        if submodule_file.exists():
                            return submodule_file, False
                        init_file = submodule / '__init__.py'
                        if init_file.exists():
                            return init_file, True

        return None

    def _process_import(self, import_name: str) -> None:
        """
        Process an import name, handling both package/module imports.
        Adds the actual module file to be processed if it's a local import.
        """
        parts = import_name.split('.')
        top_level = parts[0]

        if top_level in self.stdlib_modules:
            return

        # Try to find the actual module file
        found_module = self._find_module_file(parts)

        if found_module:
            module_file, is_package = found_module
            self.project_imports.add(import_name)
            self.files_to_process.add((import_name, module_file))
        else:
            self.external_imports.add(top_level)

class DependencyAnalyzer:
    """Analyzes project dependencies and generates requirements.txt."""

    def __init__(self, entry_points: List[str], additional_paths: List[str]):
        self.entry_points = [Path(p) for p in entry_points]
        self.additional_paths = additional_paths
        self.processed_files: Set[Path] = set()
        self.external_dependencies: Set[str] = set()

        # Collect all possible local paths
        self.local_paths = set()
        for entry_point in self.entry_points:
            self.local_paths.add(str(entry_point.parent))
        self.local_paths.update(additional_paths)

    def analyze_file(self, file_path: Path) -> Set[Tuple[str, Path]]:
        """
        Analyze a single Python file for its imports.
        Returns a set of (import_path, file_path) tuples for local imports.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                tree = ast.parse(file.read())

            analyzer = ImportAnalyzer(list(self.local_paths))
            analyzer.visit(tree)
            self.external_dependencies.update(analyzer.external_imports)
            return analyzer.files_to_process

        except Exception as e:
            print(f"Error analyzing {file_path}: {str(e)}", file=sys.stderr)
            return set()

    def analyze_project(self) -> None:
        """
        Recursively analyze the project starting from all entry points,
        collecting all external dependencies.
        """
        # Initialize with entry points
        files_to_process = set()
        for entry_point in self.entry_points:
            relative_path = entry_point.relative_to(entry_point.parent)
            module_name = str(relative_path.with_suffix('')).replace(os.sep, '.')
            files_to_process.add((module_name, entry_point))

        while files_to_process:
            import_path, current_file = files_to_process.pop()
            if current_file in self.processed_files:
                continue

            self.processed_files.add(current_file)
            if current_file.exists():
                new_files = self.analyze_file(current_file)
                files_to_process.update(new_files)

    def get_installed_version(self, package: str) -> Optional[str]:
        """Get the installed version of a package using importlib.metadata."""
        try:
            return metadata.version(package)
        except metadata.PackageNotFoundError:
            return None

    def generate_requirements(self) -> Dict[str, str]:
        """
        Generate version information for each external package.
        Returns a dictionary of package names and their installed versions.
        """
        requirements = {}
        for package in self.external_dependencies:
            version = self.get_installed_version(package)
            if version:
                requirements[package] = version
            else:
                print(f"Warning: Package '{package}' is imported but not installed",
                      file=sys.stderr)
        return requirements

    def write_requirements(self, output_file: str) -> None:
        """Write the requirements.txt file."""
        requirements = self.generate_requirements()

        with open(output_file, 'w') as f:
            for package, version in sorted(requirements.items()):
                if version:
                    f.write(f"{package}=={version}\n")
                else:
                    f.write(f"{package}\n")

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Analyze Python project dependencies and generate requirements.txt'
    )
    parser.add_argument(
        '-e', '--entry-points',
        nargs='+',
        help='One or more Python files to start the analysis from'
    )
    parser.add_argument(
        '-p', '--paths',
        nargs='+',
        default=[],
        help='Additional paths to look for local modules'
    )
    parser.add_argument(
        '-o', '--output',
        default='requirements.txt',
        help='Output file path (default: requirements.txt)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    return parser.parse_args()

def main():
    args = parse_args()

    # Validate entry points
    for entry_point in args.entry_points:
        if not os.path.exists(entry_point):
            print(f"Error: File {entry_point} not found.")
            sys.exit(1)

    if args.verbose:
        print(f"Starting analysis from: {', '.join(args.entry_points)}")
        if args.paths:
            print(f"Additional module search paths: {', '.join(args.paths)}")

    analyzer = DependencyAnalyzer(args.entry_points, args.paths)
    analyzer.analyze_project()

    requirements = analyzer.generate_requirements()
    analyzer.write_requirements(args.output)

    if args.verbose:
        print("\nAnalysis complete!")
        print(f"Found {len(requirements)} external dependencies:")
        for package, version in sorted(requirements.items()):
            version_str = f"version {version}" if version else "version unknown"
            print(f"  - {package} ({version_str})")
        print("\nProcessed files:")
        for file_path in sorted(analyzer.processed_files):
            print(f"  - {file_path}")

    print(f"\nRequirements have been written to {args.output}")

if __name__ == "__main__":
    main()

