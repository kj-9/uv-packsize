# uv-packsize

[![PyPI](https://img.shields.io/pypi/v/uv-packsize.svg)](https://pypi.org/project/uv-packsize/)
[![Changelog](https://img.shields.io/github/v/release/kj-9/uv-packsize?include_prereleases&label=changelog)](https://github.com/kj-9/uv-packsize/releases)
[![Tests](https://github.com/kj-9/uv-packsize/actions/workflows/ci.yml/badge.svg)](https://github.com/kj-9/uv-packsize/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/kj-9/uv-packsize/blob/master/LICENSE)

report size of python package with its deps using uv

## Installation

Install this tool using `pip`:
```bash
pip install uv-packsize
```
or using `uv`:
```bash
uv tool install uv-packsize
```

## Usage

For help, run:
```
uv-packsize --help
```
<!-- [[[cog
import cog
from uv_packsize import cli
from click.testing import CliRunner
runner = CliRunner()
result = runner.invoke(cli.cli, ["--help"])
help = result.output.replace("Usage: cli", "Usage: uv-packsize")
cog.out(
    f"```bash\n{help}\n```"
)
]]] -->
```bash
Usage: uv-packsize [OPTIONS] PACKAGE_NAME

  Report the size of a Python package and its dependencies using uv.

Options:
  --version          Show the version and exit.
  --bin              Include the size of binaries in the .venv/bin directory.
  -p, --python TEXT  Specify the Python version for the virtual environment.
  --help             Show this message and exit.

```
<!-- [[[end]]] -->

### Example

```bash
uv-packsize apache-airflow==3.0.0
```
<!-- [[[cog
import cog
from uv_packsize import cli
from click.testing import CliRunner
runner = CliRunner()
result = runner.invoke(cli.cli, ["apache-airflow==3.0.0"])
help = result.output.replace("Usage: cli", "Usage: uv-packsize")
cog.out(
    f"```bash\n{help}\n```"
)
]]] -->
```bash
Calculating size for apache-airflow==3.0.0...
Creating virtual environment...
Installing apache-airflow==3.0.0 and its dependencies...
Analyzing sizes...

--- Package Sizes ---
Package                                        Size
----------------------------------------  ---------
grpc                                       33.16 MB
cryptography                               20.91 MB
airflow                                    12.73 MB
libcst                                      7.45 MB
sqlalchemy                                  6.18 MB
pygments                                    4.29 MB
uvloop                                      4.17 MB
pydantic_core                               4.16 MB
google                                      2.17 MB
rignore                                     1.94 MB
pydantic                                    1.69 MB
opentelemetry                               1.52 MB
sentry_sdk                                  1.23 MB
dns                                         1.03 MB
alembic                                   995.36 KB
pytz                                      986.13 KB
watchfiles                                961.79 KB
psutil                                    942.53 KB
rich                                      938.10 KB
rpds                                      913.84 KB
pendulum                                  871.96 KB
charset_normalizer                        809.24 KB
werkzeug                                  743.19 KB
fsspec                                    710.02 KB
fastapi                                   662.95 KB
websockets                                661.72 KB
git                                       654.53 KB
pycparser                                 602.81 KB
yaml_ft                                   594.59 KB
tzdata                                    569.46 KB
yaml                                      562.73 KB
jinja2                                    485.42 KB
jsonschema                                464.39 KB
msgspec                                   445.28 KB
anyio                                     421.14 KB
dateutil                                  418.10 KB
urllib3                                   415.04 KB
cffi                                      373.32 KB
click                                     361.20 KB
dill                                      357.50 KB
httptools                                 344.21 KB
idna                                      342.03 KB
flask                                     336.86 KB
text_unidecode                            316.51 KB
certifi                                   288.90 KB
httpx                                     288.62 KB
httpcore                                  281.44 KB
more_itertools                            274.10 KB
mako                                      269.40 KB
sqlalchemy_utils                          268.16 KB
gunicorn                                  264.55 KB
starlette                                 252.16 KB
packaging                                 232.93 KB
cadwyn                                    218.52 KB
structlog                                 215.54 KB
uvicorn                                   212.48 KB
markdown_it                               208.91 KB
requests                                  199.67 KB
attr                                      190.39 KB
typer                                     186.49 KB
aiologic                                  183.86 KB
cron_descriptor                           183.40 KB
gitdb                                     176.97 KB
apache_airflow_core                       176.55 KB
wrapt                                     166.03 KB
lazy_object_proxy                         149.50 KB
upath                                     142.63 KB
sqlparse                                  138.50 KB
tabulate                                  128.64 KB
argcomplete                               127.72 KB
referencing                               112.91 KB
h11                                       101.67 KB
pathspec                                  100.51 KB
email_validator                            98.96 KB
python_multipart                           86.26 KB
croniter                                   84.15 KB
rich_toolkit                               82.01 KB
tenacity                                   81.50 KB
importlib_metadata                         73.96 KB
jwt                                        73.12 KB
rich_argparse                              71.38 KB
svcs                                       69.31 KB
asgiref                                    69.19 KB
setproctitle                               69.16 KB
smmap                                      67.68 KB
markupsafe                                 66.64 KB
pluggy                                     64.45 KB
typing_inspection                          52.08 KB
python_daemon                              51.08 KB
retryhttp                                  50.63 KB
aiosqlite                                  48.61 KB
linkify_it                                 48.18 KB
a2wsgi                                     47.31 KB
jsonschema_specifications                  46.37 KB
fastapi_cloud_cli                          46.23 KB
itsdangerous                               45.94 KB
apache_airflow                             41.47 KB
requests-stubs                             39.19 KB
daemon                                     38.26 KB
grpcio                                     38.21 KB
googleapis_common_protos                   36.94 KB
annotated_types                            36.36 KB
lockfile                                   34.88 KB
fastapi_cli                                28.85 KB
universal_pathlib                          28.51 KB
dotenv                                     28.29 KB
opentelemetry_semantic_conventions         27.18 KB
python_dotenv                              27.12 KB
colorlog                                   26.25 KB
blinker                                    24.08 KB
attrs                                      23.77 KB
wirerope                                   23.37 KB
mdurl                                      22.93 KB
zipp                                       22.89 KB
sniffio                                    22.56 KB
deprecated                                 21.55 KB
opentelemetry_sdk                          20.93 KB
apache_airflow_task_sdk                    20.54 KB
gitpython                                  20.45 KB
dnspython                                  18.81 KB
shellingham                                18.23 KB
opentelemetry_proto                        18.12 KB
termcolor                                  18.02 KB
opentelemetry_api                          17.60 KB
uuid6                                      17.58 KB
typing_extensions                          17.48 KB
SQLAlchemy_JSONField                       17.19 KB
types_requests                             16.61 KB
markdown_it_py                             16.03 KB
opentelemetry_exporter_otlp_proto_http     15.47 KB
opentelemetry_exporter_otlp_proto_grpc     15.43 KB
opentelemetry_exporter_otlp_proto_common   14.78 KB
opentelemetry_exporter_otlp                14.71 KB
python_dateutil                            13.33 KB
apache_airflow_providers_standard          12.27 KB
slugify                                    11.75 KB
pyyaml_ft                                  11.48 KB
linkify_it_py                              11.43 KB
python_slugify                             10.72 KB
apache_airflow_providers_common_sql         9.00 KB
apache_airflow_providers_common_compat      8.46 KB
protobuf                                    7.74 KB
Deprecated                                  7.57 KB
sqlalchemy_jsonfield                        7.22 KB
apache_airflow_providers_smtp               7.04 KB
apache_airflow_providers_common_io          7.03 KB
PyJWT                                       6.90 KB
MarkupSafe                                  6.49 KB
rpds_py                                     6.00 KB
uc_micro_py                                 5.89 KB
methodtools                                 5.25 KB
tools                                       5.16 KB
PyYAML                                      5.11 KB
six                                         3.36 KB
uc_micro                                    2.65 KB
_yaml_ft                                    1.39 KB
_yaml                                       1.37 KB
multipart                                   1.03 KB
----------------------------------------  ---------
Total Package Size                        128.56 MB

Total size:                               128.56 MB

Calculation complete.

```
<!-- [[[end]]] -->


You can also use:
```bash
python -m uv_packsize --help
```
## Development

To contribute to this tool, first checkout the code. Then create a new virtual environment using uv:
```bash
make sync
```

To run the tests:
```bash
make test
```

To run all formatting and linting, type check:
```bash
make check
```

this also runs [cog](https://cog.readthedocs.io/en/latest/) on README.md and updates the help message inside it.
