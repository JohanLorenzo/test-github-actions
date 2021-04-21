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
import os
import pathlib
import six

_ROOT_DIR = os.path.dirname(os.path.realpath(__file__))
_DOCKER_DIR = os.path.join(_ROOT_DIR, 'docker')


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


def main():
    docker_dirs = os.listdir(_DOCKER_DIR)
    docker_images = [{
        "name": docker_dir,
        "sha256": hash_paths(_DOCKER_DIR, [os.path.join(docker_dir, "**/*")]),
    } for docker_dir in docker_dirs]

    print(json.dumps(docker_images))

__name__ == "__main__" and main()
