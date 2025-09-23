# Gemini Code Assistant Context

## Project Overview

This project is a Python command-line tool named `uv-packsize`. Its purpose is to report the size of a Python package and its dependencies. It utilizes the `uv` tool for virtual environment management and package installation. The core logic is implemented in `uv_packsize/cli.py` and it uses the `click` library for its command-line interface.

## Building and Running

### Development Environment

To set up the development environment, run:

```bash
make sync
```

This will install all the necessary dependencies using `uv`.

### Running the tool

The tool can be run using the `uv-packsize` command:

```bash
uv-packsize <package_name>
```

### Testing

To run the test suite, use the following command:

```bash
make test
```

### Linting and Formatting

To lint and format the code, run:

```bash
make check
```

This will run `ruff` for formatting and linting, `ty` for type checking, and also update the `README.md` file.

## Development Conventions

The project uses `ruff` for code formatting and linting, and `ty` for type checking. The configuration for `ruff` can be found in the `pyproject.toml` file. The project also uses `cog` to update the help message in the `README.md` file. All these checks are run as part of the `make check` command.
