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
Creating virtual environment in /var/folders/q2/w6cy9fgn57v0_m3rp_xmygw00000gn/T/tmpnv0jc_93/venv with default Python (3.13.0)...
Installing apache-airflow==3.0.0 and its dependencies...
Analyzing sizes...

--- Package Sizes ---
Package                                                         Size
---------------------------------------------------------  ---------
grpc                                                        33.16 MB
cryptography                                                20.88 MB
airflow                                                     12.73 MB
libcst                                                       7.40 MB
sqlalchemy                                                   6.14 MB
pygments                                                     4.25 MB
pydantic_core                                                4.15 MB
uvloop                                                       4.15 MB
google                                                       2.17 MB
rignore                                                      1.93 MB
pydantic                                                     1.62 MB
opentelemetry                                                1.52 MB
sentry_sdk                                                   1.21 MB
dns                                                          1.03 MB
alembic                                                    978.99 KB
watchfiles                                                 954.37 KB
psutil                                                     916.18 KB
rpds                                                       913.84 KB
rich                                                       913.17 KB
pytz                                                       912.11 KB
pendulum                                                   853.84 KB
charset_normalizer                                         770.03 KB
werkzeug                                                   732.76 KB
fsspec                                                     693.28 KB
git                                                        654.53 KB
websockets                                                 648.55 KB
fastapi                                                    630.11 KB
pycparser                                                  598.29 KB
yaml_ft                                                    594.59 KB
yaml                                                       562.73 KB
tzdata                                                     502.71 KB
jinja2                                                     478.58 KB
jsonschema                                                 451.89 KB
msgspec                                                    435.22 KB
dateutil                                                   418.10 KB
anyio                                                      412.10 KB
urllib3                                                    404.03 KB
cffi                                                       366.87 KB
click                                                      355.57 KB
dill                                                       341.38 KB
httptools                                                  338.02 KB
flask                                                      329.69 KB
idna                                                       329.45 KB
text_unidecode                                             304.26 KB
certifi                                                    284.54 KB
httpx                                                      277.73 KB
mako                                                       261.72 KB
httpcore                                                   255.80 KB
sqlalchemy_utils                                           255.71 KB
gunicorn                                                   255.53 KB
starlette                                                  241.27 KB
more_itertools                                             233.44 KB
packaging                                                  216.22 KB
cadwyn                                                     209.74 KB
markdown_it                                                208.91 KB
uvicorn                                                    200.52 KB
structlog                                                  194.54 KB
attr                                                       190.39 KB
requests                                                   182.92 KB
apache_airflow_core-3.0.0.dist-info                        176.55 KB
aiologic                                                   171.70 KB
gitdb                                                      171.24 KB
cron_descriptor                                            169.97 KB
typer                                                      168.08 KB
wrapt                                                      157.17 KB
upath                                                      142.63 KB
lazy_object_proxy                                          141.72 KB
sqlparse                                                   127.37 KB
referencing                                                107.29 KB
argcomplete                                                 98.00 KB
tabulate                                                    93.23 KB
h11                                                         90.94 KB
python_multipart                                            82.62 KB
pydantic-2.11.9.dist-info                                   77.22 KB
rich_toolkit                                                74.61 KB
pytz-2025.2.dist-info                                       74.02 KB
jwt                                                         73.12 KB
email_validator                                             70.59 KB
tenacity                                                    67.64 KB
tzdata-2025.2.dist-info                                     66.75 KB
markupsafe                                                  66.64 KB
pathspec                                                    62.26 KB
smmap                                                       60.54 KB
svcs                                                        59.66 KB
pluggy                                                      57.37 KB
asgiref                                                     57.14 KB
importlib_metadata                                          56.29 KB
setproctitle                                                56.20 KB
rich_argparse                                               54.27 KB
python_daemon-3.1.2.dist-info                               51.08 KB
croniter                                                    50.47 KB
linkify_it                                                  48.18 KB
libcst-1.8.4.dist-info                                      47.95 KB
typing_inspection                                           47.49 KB
pygments-2.19.2.dist-info                                   42.54 KB
aiosqlite                                                   41.93 KB
apache_airflow-3.0.0.dist-info                              41.47 KB
itsdangerous                                                41.35 KB
more_itertools-10.8.0.dist-info                             40.67 KB
fastapi_cloud_cli                                           39.56 KB
charset_normalizer-3.4.3.dist-info                          39.21 KB
requests-stubs                                              39.19 KB
jsonschema_specifications                                   39.05 KB
daemon                                                      38.26 KB
pathspec-0.12.1.dist-info                                   38.25 KB
grpcio-1.74.0.dist-info                                     38.21 KB
googleapis_common_protos-1.70.0.dist-info                   36.94 KB
tabulate-0.9.0.dist-info                                    35.40 KB
croniter-6.0.0.dist-info                                    33.68 KB
sqlalchemy-1.4.54.dist-info                                 33.41 KB
fastapi-0.116.1.dist-info                                   32.84 KB
a2wsgi                                                      31.19 KB
argcomplete-3.6.2.dist-info                                 29.72 KB
retryhttp-1.3.3.dist-info                                   29.01 KB
cryptography-45.0.7.dist-info                               28.82 KB
lockfile                                                    28.64 KB
universal_pathlib-0.2.6.dist-info                           28.51 KB
email_validator-2.3.0.dist-info                             28.37 KB
dotenv                                                      28.29 KB
opentelemetry_semantic_conventions-0.58b0.dist-info         27.18 KB
python_dotenv-1.1.1.dist-info                               27.12 KB
sentry_sdk-2.37.1.dist-info                                 26.73 KB
psutil-7.0.0.dist-info                                      26.36 KB
httpcore-1.0.9.dist-info                                    25.64 KB
rich-14.1.0.dist-info                                       24.93 KB
uvloop-0.21.0.dist-info                                     22.22 KB
retryhttp                                                   21.62 KB
deprecated                                                  21.55 KB
structlog-25.4.0.dist-info                                  20.99 KB
opentelemetry_sdk-1.37.0.dist-info                          20.93 KB
blinker                                                     20.63 KB
apache_airflow_task_sdk-1.0.0.dist-info                     20.54 KB
gitpython-3.1.45.dist-info                                  20.45 KB
fastapi_cli                                                 20.19 KB
annotated_types                                             19.77 KB
dnspython-2.8.0.dist-info                                   18.81 KB
typer-0.17.4.dist-info                                      18.41 KB
pendulum-3.1.0.dist-info                                    18.12 KB
opentelemetry_proto-1.37.0.dist-info                        18.12 KB
mdurl                                                       18.03 KB
importlib_metadata-8.7.0.dist-info                          17.67 KB
opentelemetry_api-1.37.0.dist-info                          17.60 KB
wirerope                                                    17.50 KB
typing_extensions-4.15.0.dist-info                          17.48 KB
sniffio-1.3.1.dist-info                                     17.36 KB
zipp                                                        17.21 KB
SQLAlchemy_JSONField-1.0.2.dist-info                        17.19 KB
rich_argparse-1.7.1.dist-info                               17.11 KB
requests-2.32.5.dist-info                                   16.75 KB
fsspec-2025.9.0.dist-info                                   16.74 KB
packaging-25.0.dist-info                                    16.71 KB
types_requests-2.32.4.20250913.dist-info                    16.61 KB
annotated_types-0.7.0.dist-info                             16.59 KB
alembic-1.16.5.dist-info                                    16.37 KB
a2wsgi-1.10.10.dist-info                                    16.12 KB
dill-0.4.0.dist-info                                        16.12 KB
markdown_it_py-4.0.0.dist-info                              16.03 KB
opentelemetry_exporter_otlp_proto_http-1.37.0.dist-info     15.47 KB
opentelemetry_exporter_otlp_proto_grpc-1.37.0.dist-info     15.43 KB
opentelemetry_exporter_otlp_proto_common-1.37.0.dist-info   14.78 KB
opentelemetry_exporter_otlp-1.37.0.dist-info                14.71 KB
attrs-25.3.0.dist-info                                      14.58 KB
tenacity-9.1.2.dist-info                                    13.87 KB
colorlog                                                    13.44 KB
cron_descriptor-2.0.6.dist-info                             13.43 KB
python_dateutil-2.9.0.post0.dist-info                       13.33 KB
websockets-15.0.1.dist-info                                 13.17 KB
setproctitle-1.3.7.dist-info                                12.96 KB
colorlog-6.9.0.dist-info                                    12.82 KB
shellingham                                                 12.78 KB
idna-3.10.dist-info                                         12.58 KB
jsonschema-4.25.1.dist-info                                 12.50 KB
sqlalchemy_utils-0.42.0.dist-info                           12.45 KB
apache_airflow_providers_standard-1.7.0.dist-info           12.27 KB
text_unidecode-1.3.dist-info                                12.25 KB
aiologic-0.14.0.dist-info                                   12.16 KB
asgiref-3.9.1.dist-info                                     12.05 KB
uvicorn-0.35.0.dist-info                                    11.96 KB
slugify                                                     11.75 KB
uuid6-2025.0.1.dist-info                                    11.75 KB
pyyaml_ft-8.0.0.dist-info                                   11.48 KB
linkify_it_py-2.0.3.dist-info                               11.43 KB
sqlparse-0.5.3.dist-info                                    11.13 KB
urllib3-2.5.0.dist-info                                     11.00 KB
starlette-0.47.3.dist-info                                  10.90 KB
httpx-0.28.1.dist-info                                      10.89 KB
h11-0.16.0.dist-info                                        10.72 KB
python_slugify-8.0.4.dist-info                              10.72 KB
werkzeug-3.1.3.dist-info                                    10.43 KB
msgspec-0.19.0.dist-info                                    10.06 KB
termcolor                                                    9.88 KB
svcs-25.1.0.dist-info                                        9.64 KB
attrs                                                        9.19 KB
anyio-4.10.0.dist-info                                       9.04 KB
gunicorn-23.0.0.dist-info                                    9.02 KB
apache_airflow_providers_common_sql-1.28.0.dist-info         9.00 KB
wrapt-1.17.3.dist-info                                       8.86 KB
cadwyn-5.4.4.dist-info                                       8.78 KB
pydantic_core-2.33.2.dist-info                               8.70 KB
fastapi_cli-0.0.11.dist-info                                 8.66 KB
apache_airflow_providers_common_compat-1.7.3.dist-info       8.46 KB
termcolor-3.1.0.dist-info                                    8.14 KB
lazy_object_proxy-1.12.0.dist-info                           7.78 KB
protobuf-6.32.1.dist-info                                    7.74 KB
mako-1.3.10.dist-info                                        7.67 KB
Deprecated-1.2.18.dist-info                                  7.57 KB
watchfiles-1.1.0.dist-info                                   7.43 KB
rich_toolkit-0.15.1.dist-info                                7.40 KB
jsonschema_specifications-2025.9.1.dist-info                 7.32 KB
sqlalchemy_jsonfield                                         7.22 KB
flask-3.1.2.dist-info                                        7.17 KB
smmap-5.0.2.dist-info                                        7.14 KB
pluggy-1.6.0.dist-info                                       7.08 KB
apache_airflow_providers_smtp-2.2.1.dist-info                7.04 KB
apache_airflow_providers_common_io-1.6.2.dist-info           7.03 KB
PyJWT-2.10.1.dist-info                                       6.90 KB
jinja2-3.1.6.dist-info                                       6.84 KB
aiosqlite-0.21.0.dist-info                                   6.67 KB
fastapi_cloud_cli-0.1.5.dist-info                            6.67 KB
MarkupSafe-3.0.2.dist-info                                   6.49 KB
cffi-2.0.0.dist-info                                         6.45 KB
lockfile-0.12.2.dist-info                                    6.24 KB
httptools-0.6.4.dist-info                                    6.19 KB
rpds_py-0.27.1.dist-info                                     6.00 KB
uc_micro_py-1.0.3.dist-info                                  5.89 KB
wirerope-1.0.0.dist-info                                     5.87 KB
uuid6                                                        5.83 KB
gitdb-4.0.12.dist-info                                       5.74 KB
zipp-3.23.0.dist-info                                        5.68 KB
click-8.2.1.dist-info                                        5.63 KB
referencing-0.36.2.dist-info                                 5.62 KB
rignore-0.6.4.dist-info                                      5.61 KB
shellingham-1.5.4.dist-info                                  5.44 KB
methodtools-0.4.7.dist-info                                  5.25 KB
sniffio                                                      5.20 KB
tools                                                        5.16 KB
PyYAML-6.0.2.dist-info                                       5.11 KB
mdurl-0.1.2.dist-info                                        4.90 KB
typing_inspection-0.4.1.dist-info                            4.60 KB
itsdangerous-2.2.0.dist-info                                 4.59 KB
pycparser-2.23.dist-info                                     4.52 KB
certifi-2025.8.3.dist-info                                   4.36 KB
python_multipart-0.0.20.dist-info                            3.64 KB
blinker-1.9.0.dist-info                                      3.46 KB
six-1.17.0.dist-info                                         3.36 KB
uc_micro                                                     2.65 KB
_yaml_ft                                                     1.39 KB
_yaml                                                        1.37 KB
multipart                                                    1.03 KB
---------------------------------------------------------  ---------
Total Package Size                                         128.56 MB

Total size:                                                128.56 MB

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
