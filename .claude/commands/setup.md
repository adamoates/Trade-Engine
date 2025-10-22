Set up the development environment:

1. Check Python version (3.11+ required)
2. Create virtual environment if needed: `python -m venv .venv`
3. Activate virtual environment
4. Install dependencies based on project structure:
   - If poetry: `poetry install`
   - If requirements.txt: `pip install -r requirements.txt`
   - If pyproject.toml: `pip install -e .`
5. Install development dependencies
6. Verify installation by running: `pytest --version`
