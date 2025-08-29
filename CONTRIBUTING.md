# Contributing

## Development Setup

1. **Prerequisites**
   - Python 3.9+
   - Node.js 20+
   - AWS CLI configured
   - Poetry installed

2. **Install Dependencies**
   ```bash
   poetry install
   npm install -g aws-cdk@2.111.0
   ```

3. **Run Tests**
   ```bash
   poetry run pytest
   poetry run cdk synth
   ```

## Code Standards

- **Formatting**: Use `poetry run black .`
- **Linting**: Use `poetry run flake8 .`
- **Type Checking**: Use `poetry run mypy .`
- **Testing**: Add tests for new constructs in `tests/`

## Pull Request Process

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## Architecture Decisions

Document significant changes in `docs/adr/` following ADR format.

## Issues

Use GitHub issues for bugs and feature requests. Include:
- Clear description
- Steps to reproduce (for bugs)
- Expected vs actual behavior