# Contributing to ytsum

Thank you for your interest in contributing to ytsum! This document provides guidelines for contributing to the project.

**Note**: This project was developed with significant assistance from AI tools (primarily Claude by Anthropic). We welcome both human and AI-assisted contributions. See [AI_ATTRIBUTION.md](AI_ATTRIBUTION.md) for details.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/yourusername/ytsum.git`
3. Create a new branch: `git checkout -b feature/your-feature-name`
4. Make your changes
5. Test your changes
6. Commit your changes: `git commit -am 'Add new feature'`
7. Push to your fork: `git push origin feature/your-feature-name`
8. Create a Pull Request

## Development Setup

```bash
# Clone the repository
git clone https://github.com/ajstafford/ytsum.git
cd ytsum

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install in development mode with dev dependencies
pip install -e ".[dev]"

# Initialize configuration
ytsum init
```

## Code Style

- Follow PEP 8 guidelines
- Use `black` for code formatting: `black src/`
- Use `flake8` for linting: `flake8 src/`
- Maximum line length: 100 characters
- Use type hints where possible

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=ytsum
```

## Pull Request Guidelines

- **One feature per PR**: Keep pull requests focused on a single feature or bug fix
- **Update tests**: Add or update tests for any new functionality
- **Update documentation**: Update README.md if you add new features or change behavior
- **Follow code style**: Run `black` and `flake8` before committing
- **Write clear commit messages**: Use descriptive commit messages
- **Test thoroughly**: Ensure your changes work with both TUI and web interfaces

## Bug Reports

When reporting bugs, please include:

- Operating system and version
- Python version
- ytsum version
- Steps to reproduce the issue
- Expected behavior
- Actual behavior
- Error messages or logs (if applicable)

## Feature Requests

Feature requests are welcome! Please check the [Enhancement Backlog](README.md#enhancement-backlog) in the README first to see if it's already planned.

When suggesting features:

- Explain the use case
- Describe how it would work
- Consider implementation complexity
- Think about backward compatibility

## Priority Areas for Contribution

See the [Enhancement Backlog](README.md#enhancement-backlog) in the README for prioritized feature ideas.

High-priority items that would be especially welcome:

- Background processing for web UI
- Full-text search across summaries
- Export functionality (Markdown, PDF)
- Mark as read/favorite functionality
- Notification system

## Questions?

Feel free to open an issue with the "question" label if you need help or clarification.

## Code of Conduct

- Be respectful and constructive
- Welcome newcomers and help them learn
- Focus on what is best for the project
- Show empathy towards other contributors

Thank you for contributing to ytsum!
