# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
import enum
import logging
import os
import sys
import tempfile
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

log = logging.getLogger(__name__)

airflow_redirects_link = "https://raw.githubusercontent.com/apache/airflow/main/docs/apache-airflow/redirects.txt"
helm_redirects_link = "https://raw.githubusercontent.com/apache/airflow/main/docs/helm-chart/redirects.txt"

docs_archive_path = "../docs-archive"
airflow_docs_path = docs_archive_path + "/apache-airflow"
helm_docs_path = docs_archive_path + "/helm-chart"


# types of generations supported
class GenerationType(enum.Enum):
    airflow = 1
    helm = 2
    providers = 3


def download_file(url):
    try:
        temp_dir = Path(tempfile.mkdtemp(prefix="temp_dir", suffix=""))
        file_name = temp_dir / "redirects.txt"
        filedata = urlopen(url)
        data = filedata.read()
        with open(file_name, 'wb') as f:
            f.write(data)
        return True, file_name
    except URLError as e:
        log.warning(e)
        return False, "no-file"


def construct_mapping(file_name):
    old_to_new_map = dict()
    with open(file_name) as f:
        file_content = []
        lines = f.readlines()
        # Skip empty line

        for line in lines:
            if not line.strip():
                continue

            # Skip comments
            if line.startswith("#"):
                continue

            line = line.rstrip()
            file_content.append(line)

            old_path, new_path = line.split(" ")
            old_path = old_path.replace(".rst", ".html")
            new_path = new_path.replace(".rst", ".html")

            old_to_new_map[old_path] = new_path
    return old_to_new_map


def get_redirect_content(url: str):
    return f'<html><head><meta http-equiv="refresh" content="0; url={url}"/></head></html>'


def get_github_redirects_url(provider_name: str):
    return f'https://raw.githubusercontent.com/apache/airflow/main/docs/{provider_name}/redirects.txt'


def get_provider_docs_path(provider_name: str):
    return docs_archive_path + "/" + provider_name


def create_back_reference_html(back_ref_url, path):
    content = get_redirect_content(back_ref_url)

    if Path(path).exists():
        logging.warning(f'skipping file:{path}, redirects already exist', path)
        return

    # creating a back reference html file
    with open(path, "w") as f:
        f.write(content)


def generate_back_references(link, base_path):
    is_downloaded, file_name = download_file(link)
    if not is_downloaded:
        log.warning('skipping generating back references')
        return
    old_to_new = construct_mapping(file_name)

    versions = [f.path.split("/")[-1] for f in os.scandir(base_path) if f.is_dir()]

    for version in versions:
        r = base_path + "/" + version

        for p in old_to_new:
            old = p
            new = old_to_new[p]

            # only if old file exists, add the back reference
            if os.path.exists(r + "/" + p):
                d = old_to_new[p].split("/")
                file_name = old_to_new[p].split("/")[-1]
                dest_dir = r + "/" + "/".join(d[: len(d) - 1])

                # finds relative path of old file with respect to new and handles case of different file names also
                relative_path = os.path.relpath(old, new)
                # remove one directory level because file path was used above
                relative_path = relative_path.replace("../", "", 1)

                os.makedirs(dest_dir, exist_ok=True)
                dest_file_path = dest_dir + "/" + file_name
                create_back_reference_html(relative_path, dest_file_path)


n = len(sys.argv)
if n != 2:
    log.error("missing required arguments, syntax: python add-back-references.py [airflow | providers | "
              "helm]")

gen_type = GenerationType[sys.argv[1]]
if gen_type == GenerationType.airflow:
    generate_back_references(airflow_redirects_link, airflow_docs_path)
elif gen_type == GenerationType.helm:
    generate_back_references(helm_redirects_link, helm_docs_path)
elif gen_type == GenerationType.providers:
    all_providers = [f.path.split("/")[-1] for f in os.scandir(docs_archive_path)
                     if f.is_dir() and "providers" in f.name]
    for p in all_providers:
        log.info("processing airflow provider: %s", p)
        generate_back_references(get_github_redirects_url(p), get_provider_docs_path(p))
else:
    log.error("invalid type of doc generation required. Pass one of [airflow | providers | "
              "helm]")
