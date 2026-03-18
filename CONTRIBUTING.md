# Contributing to PlaywrightsPen

First off, thank you for considering contributing to PlaywrightsPen! It's people like you that make PlaywrightsPen such a great tool.

## How Can I Contribute?

### Reporting Bugs
*   Check if the issue has already been reported.
*   If not, use the **Bug Report** template to create a new issue.
*   Include as much detail as possible: steps to reproduce, OS, Python version, and logs.

### Suggesting Enhancements
*   Open an issue using the **Feature Request** template.
*   Explain why the feature would be useful and how it should work.

### Pull Requests
1.  Fork the repository.
2.  Create a new branch (`git checkout -b feature/amazing-feature`).
3.  Make your changes.
4.  Run tests to ensure everything is working (`pytest`).
5.  Commit your changes (`git commit -m 'Add some amazing feature'`).
6.  Push to the branch (`git push origin feature/amazing-feature`).
7.  Open a Pull Request.

## Development Setup

### 1. Prerequisites
- Python 3.10+
- Conda (recommended) or venv
- Playwright

### 2. Install Dependencies
```bash
conda create -n playwrights_pen python=3.12 -y
conda activate playwrights_pen
pip install -e .[dev]
playwright install chromium
```

### 3. Running Tests
```bash
pytest
```

## Coding Standards
*   Use **Ruff** for linting and formatting.
*   Write docstrings for all public functions and classes.
*   Include tests for all new features.
*   Update `README.md` if necessary.

## Community
Join the discussion in our [GitHub Discussions](https://github.com/your-username/playwrights_pen/discussions)!
