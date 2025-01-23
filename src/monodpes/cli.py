"""
Command line interface for mono-deps-analyzer.
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from .analyzer import DependencyAnalyzer

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Analyze Python project dependencies in monorepo environments'
    )
    parser.add_argument(
        'entry_points',
        nargs='+',
        type=str,
        help='One or more Python files to analyze'
    )
    parser.add_argument(
        '-p', '--paths',
        nargs='+',
        default=[],
        help='Additional paths to search for local modules'
    )
    parser.add_argument(
        '-o', '--output',
        default='requirements.txt',
        help='Output requirements file path'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    parser.add_argument(
        '--ignore-paths',
        nargs='+',
        default=[],
        help='Paths to ignore during analysis'
    )
    return parser.parse_args()

def validate_paths(paths: List[str]) -> Optional[str]:
    """Validate that all paths exist."""
    for path in paths:
        if not Path(path).exists():
            return f"Path does not exist: {path}"
    return None

def main() -> int:
    """Main entry point for the CLI."""
    args = parse_args()

    # Validate entry points
    if error := validate_paths(args.entry_points):
        print(f"Error: {error}", file=sys.stderr)
        return 1

    # Prepare search paths
    search_paths = [str(Path(ep).parent) for ep in args.entry_points]
    search_paths.extend(args.paths)

    if args.verbose:
        print(f"Entry points: {', '.join(args.entry_points)}")
        print(f"Search paths: {', '.join(search_paths)}")
        if args.ignore_paths:
            print(f"Ignored paths: {', '.join(args.ignore_paths)}")

    try:
        # Run analysis
        analyzer = DependencyAnalyzer(search_paths)
        result = analyzer.analyze_project([Path(ep) for ep in args.entry_points])
        analyzer.write_requirements(args.output)

        if args.verbose:
            print("\nAnalysis complete!")
            print(f"\nFound {len(result.external_dependencies)} external dependencies:")
            for package, version in sorted(result.external_dependencies.items()):
                version_str = f"version {version}" if version else "version unknown"
                print(f"  - {package} ({version_str})")

            print(f"\nProcessed {len(result.processed_files)} local modules:")
            for module in sorted(result.local_modules):
                print(f"  - {module}")

        print(f"\nRequirements written to {args.output}")
        return 0

    except Exception as e:
        print(f"Error during analysis: {str(e)}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())

