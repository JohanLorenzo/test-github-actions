# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Python implementation of Github's hashFile[1][2]. It's a modified version of
# Mozilla's hash utils[3]
#
# [1] https://docs.github.com/en/actions/reference/context-and-expression-syntax-for-github-actions#hashfiles
# [2] https://github.com/actions/runner/blob/e9ae42693f71e33dbe615d4e955a599c9d73df08/src/Misc/expressionFunc/hashFiles/src/hashFiles.ts
# [3] https://searchfox.org/mozilla-central/rev/d280cc26237b62096b89317e4ed6dea8b2bdf822/taskcluster/taskgraph/util/hash.py

import hashlib
import io
import json
import logging
import os
import pathlib
import requests
import six

log = logging.getLogger(__name__)

logging.basicConfig(
    format="%(asctime)s - %(levelname)s: %(message)s",
    level=logging.DEBUG
)

_ROOT_DIR = os.path.dirname(os.path.realpath(__file__))
_DOCKER_DIR = os.path.join(_ROOT_DIR, 'docker')
_DOCKER_REPOSITORY = 'johanlorenzo/test-github-action'


_APPLICATIONS = [
    {
        "app_name": "my-ansible-app",
        "image_name": "python-ansible",
    },
    {
        "app_name": "my-other-ansible-app",
        "image_name": "python-ansible",
    },
    {
        "app_name": "my-tox-app",
        "image_name": "python-tox",
    },
]


def hash_path(path):
    """Hash a single file.

    Returns the SHA-256 hash in hex form.
    """
    with io.open(path, mode="rb") as fh:
        return hashlib.sha256(fh.read()).digest()


def hash_paths(base_path, patterns):
    """
    Give a list of path patterns, return a digest of the contents of all
    the corresponding files, similarly to git tree objects or mercurial
    manifests.

    Each file is hashed. The list of all hashes and file paths is then
    itself hashed to produce the result.
    """
    finder = pathlib.Path(base_path)
    h = hashlib.sha256()
    files = set()
    for pattern in patterns:
        found = set(finder.glob(pattern))

        if found:
            files.update(found)
        else:
            raise Exception("%s did not match anything" % pattern)
    for path in sorted(files):
        if path.suffix in (".pyc", ".pyd", ".pyo"):
            continue
        h.update(
            six.ensure_binary(
                hash_path(os.path.abspath(os.path.join(base_path, path)))
            )
        )
    return h.hexdigest()


def _get_docker_image_hash_on_registry(docker_repository, docker_image_tag):
    # Taken from https://stackoverflow.com/questions/28320134/how-can-i-list-all-tags-for-a-docker-image-on-a-remote-registry/51921869#51921869
    auth_url=f"https://auth.docker.io/token?service=registry.docker.io&scope=repository:{docker_repository}:pull"
    auth_request = requests.get(auth_url)
    auth_request.raise_for_status()
    token = auth_request.json()["token"]

    index_url=f"https://index.docker.io/v2/{docker_repository}/manifests/{docker_image_tag}"
    index_request = requests.get(index_url, headers={
        "Accept": "application/vnd.docker.distribution.manifest.v2+json",
        "Authorization": f"Bearer {token}",
    })
    try:
        index_request.raise_for_status()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            return ""
        raise

    image_hash_on_registry = index_request.headers["Docker-Content-Digest"]
    log.warning(f'Tag "{docker_image_tag}" already exists. Registry has this hash associated to it: {image_hash_on_registry}')
    return image_hash_on_registry


def _does_docker_image_already_exist_on_registry(docker_repository, docker_image_tag):
    return _get_docker_image_hash_on_registry(docker_repository, docker_image_tag) != ""


def _get_docker_image_tag_for_single_application(application, docker_images):
    tags = [
        image["image_tag"]
        for image in docker_images
        if image["image_name"] == application["image_name"]
    ]

    if len(tags) != 1:
        raise ValueError(f"We should only have a single image matching. Got: {tags}")

    return tags[0]


def _get_docker_image_tags_for_applications(applications, docker_images):
    applications_with_tags = [{
        "app_name": app["app_name"],
        "image_tag": _get_docker_image_tag_for_single_application(app, docker_images)
    }   for app in applications]

    return applications_with_tags


def main():
    docker_dirs = os.listdir(_DOCKER_DIR)
    all_docker_images = [{
        "image_name": docker_dir,
        "image_tag": "{}-{}".format(
            docker_dir,
            hash_paths(_DOCKER_DIR, [os.path.join(docker_dir, "**/*")])
        ),
    } for docker_dir in docker_dirs]

    docker_images_to_build = [
        docker_image
        for docker_image in all_docker_images
        if not _does_docker_image_already_exist_on_registry(_DOCKER_REPOSITORY, docker_image["image_tag"])
    ]

    with open(os.path.join(_ROOT_DIR, "docker_images.json"), "w") as f:
        json.dump(docker_images_to_build, f)

    applications_with_tags = _get_docker_image_tags_for_applications(_APPLICATIONS, all_docker_images)
    with open(os.path.join(_ROOT_DIR, "applications.json"), "w") as f:
        json.dump(applications_with_tags, f)


__name__ == "__main__" and main()
