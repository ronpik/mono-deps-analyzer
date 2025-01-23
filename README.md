# monodeps

Accurate dependency analyzer for Python monorepos with shared components.


## Installation

```bash
pip install mono-deps-analyzer
```

## Usage

```bash
# Basic usage
python -m monodeps service/main.py -o requirements.txt

# Multiple entry points
monodeps service1/main.py service2/api.py -o shared-deps.txt

# With additional source paths
monodeps service/main.py -p src/shared libs/common

# Verbose output
monodeps -v service/app.py
```

## Use Cases

### Monorepo Service Dependencies

In a monorepo with shared components:

```
monorepo/
  ├── shared/
  │   ├── database/
  │   ├── logging/
  │   └── utils/
  └── services/
      ├── api/
      └── worker/
```

The analyzer helps identify only the shared components actually used by each service:

```bash
cd monorepo
monodeps services/api/main.py -p shared -o api-requirements.txt
```

## Features

- Deep import analysis - tracks actual module usage, not just top-level packages
- PYTHONPATH-aware resolution
- Multiple entry points support
- Shared code optimization - identifies only required components
- Generates accurate requirements.txt for each service

## Contributing

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## License

MIT License - see LICENSE file for details