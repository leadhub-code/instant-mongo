#!/usr/bin/env python3
'''
Download the mongod binary from the official MongoDB APT repository and install
it into ~/.local/bin without touching the system package manager.

The script:

1. detects the Debian/Ubuntu codename and CPU architecture of this machine,
2. lists the MongoDB release series available for it (7.0, 8.0, 9.0, ...),
3. picks the newest mongodb-org-server package of the requested series
   (or of the newest series that has a server package),
4. downloads the .deb, verifies its SHA256 against the repository index,
5. extracts just /usr/bin/mongod, optionally strips it,
6. runs `mongod --version` as a smoke test,
7. and only then points the ~/.local/bin/mongod symlink at it.

Only the Python standard library is needed. Examples:

    scripts/install-mongod.py                 # newest available
    scripts/install-mongod.py --series 8.0    # newest 8.0.x
    scripts/install-mongod.py --version 8.0.29
    scripts/install-mongod.py --list

Not every series is built for every distro release (e.g. Debian 13 "trixie"
only has 9.0). Packages built for an older release run fine on a newer one,
so on trixie you can still get 7.0 or 8.0 with:

    scripts/install-mongod.py --codename bookworm --series 8.0
'''

import argparse
import hashlib
import logging
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path


logger = logging.getLogger('install-mongod')

REPO_HOST = 'https://repo.mongodb.org'
# The HTML directory index of repo.mongodb.org is JavaScript-only; the bucket
# itself is listable through the S3 API.
S3_LIST_URL = 'https://s3.amazonaws.com/repo.mongodb.org'
PACKAGE_NAME = 'mongodb-org-server'
MONGOD_MEMBER = './usr/bin/mongod'

ARCH_MAP = {
    'x86_64': 'amd64',
    'aarch64': 'arm64',
    'arm64': 'arm64',
}

# (repo path, APT component) per distro ID from /etc/os-release
DISTRO_MAP = {
    'debian': ('apt/debian', 'main'),
    'ubuntu': ('apt/ubuntu', 'multiverse'),
}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--series', metavar='X.Y', help='MongoDB release series, e.g. 7.0, 8.0 or 9.0 (default: newest with a server package)')
    p.add_argument('--version', metavar='X.Y.Z', help='exact server version to install (implies --series X.Y)')
    p.add_argument('--dest', type=Path, default=Path.home() / '.local' / 'bin', help='destination directory (default: ~/.local/bin)')
    p.add_argument('--codename', help='override distro codename detected from /etc/os-release (e.g. trixie, bookworm, noble)')
    p.add_argument('--distro', choices=sorted(DISTRO_MAP), help='override distro ID detected from /etc/os-release')
    p.add_argument('--arch', choices=sorted(set(ARCH_MAP.values())), help='override Debian architecture (default: detected)')
    p.add_argument('--no-strip', action='store_true', help='do not strip debug symbols from the binary')
    p.add_argument('--no-symlink', action='store_true', help='do not create/update the mongod symlink')
    p.add_argument('--force', action='store_true', help='re-download even if the versioned binary already exists')
    p.add_argument('--list', action='store_true', help='only list available series and server versions, install nothing')
    p.add_argument('-v', '--verbose', action='store_true')
    args = p.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(message)s' if not args.verbose else '%(asctime)s %(levelname)5s: %(message)s')

    if args.version and args.series and not args.version.startswith(args.series + '.'):
        p.error(f'--version {args.version} does not belong to --series {args.series}')
    if args.version:
        args.series = '.'.join(args.version.split('.')[:2])
    if args.series and not re.fullmatch(r'\d+\.\d+', args.series):
        p.error('--series must look like X.Y, e.g. 8.0')

    try:
        repo = Repository(
            distro=args.distro or detect_distro(),
            codename=args.codename or detect_codename(),
            arch=args.arch or detect_arch())
        if args.list:
            list_available(repo)
            return
        pkg = select_package(repo, args.series, args.version)
        install(repo, pkg, args)
    except InstallError as e:
        logger.error('Error: %s', e)
        sys.exit(1)


class InstallError(Exception):
    pass


class Repository:

    def __init__(self, distro, codename, arch):
        if distro not in DISTRO_MAP:
            raise InstallError(f'Unsupported distro {distro!r}; supported: {", ".join(sorted(DISTRO_MAP))}')
        self.distro = distro
        self.codename = codename
        self.arch = arch
        self.base_path, self.component = DISTRO_MAP[distro]
        logger.info('Repository: %s/%s %s %s', REPO_HOST, self.base_path, codename, arch)

    def list_series(self):
        prefix = f'{self.base_path}/dists/{self.codename}/mongodb-org/'
        url = f'{S3_LIST_URL}?list-type=2&prefix={prefix}&delimiter=/'
        root = ET.fromstring(http_get(url))
        ns = {'s3': root.tag[1:].split('}')[0]} if root.tag.startswith('{') else {}
        tag = 's3:CommonPrefixes/s3:Prefix' if ns else 'CommonPrefixes/Prefix'
        series = []
        for el in root.iterfind(tag, ns):
            name = el.text[len(prefix):].strip('/')
            if re.fullmatch(r'\d+\.\d+', name):
                series.append(name)
        if not series:
            raise InstallError(f'No MongoDB series found for {self.codename}; is the codename right? (see --codename)')
        return sorted(series, key=version_key)

    def server_packages(self, series):
        '''
        Return the mongodb-org-server stanzas of the given series, newest first.
        '''
        url = f'{REPO_HOST}/{self.base_path}/dists/{self.codename}/mongodb-org/{series}/{self.component}/binary-{self.arch}/Packages'
        try:
            text = http_get(url).decode()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return []
            raise
        pkgs = [s for s in parse_packages(text) if s.get('Package') == PACKAGE_NAME]
        return sorted(pkgs, key=lambda s: version_key(s['Version']), reverse=True)


def list_available(repo):
    for series in repo.list_series():
        pkgs = repo.server_packages(series)
        versions = ', '.join(s['Version'] for s in pkgs) or f'(no {PACKAGE_NAME} package)'
        logger.info('%-5s %s', series, versions)


def select_package(repo, series, version):
    available = repo.list_series()
    if series:
        if series not in available:
            raise InstallError(f'Series {series} not available for {repo.codename}; available: {", ".join(available)}')
        candidates = [series]
    else:
        candidates = list(reversed(available))
    for s in candidates:
        pkgs = repo.server_packages(s)
        if version:
            pkgs = [p for p in pkgs if p['Version'] == version]
            if not pkgs:
                raise InstallError(f'Version {version} not found in series {s}; run --list to see what is available')
        if pkgs:
            logger.info('Selected %s %s from series %s', PACKAGE_NAME, pkgs[0]['Version'], s)
            return pkgs[0]
        if series:
            raise InstallError(f'Series {s} has no {PACKAGE_NAME} package for {repo.codename}/{repo.arch}; run --list to see what is available')
        logger.info('Series %s has no %s package for %s/%s, skipping', s, PACKAGE_NAME, repo.codename, repo.arch)
    raise InstallError(f'No {PACKAGE_NAME} package found for {repo.codename}/{repo.arch} in any series')


def install(repo, pkg, args):
    version = pkg['Version']
    dest_dir = args.dest
    dest_dir.mkdir(parents=True, exist_ok=True)
    binary = dest_dir / f'mongod-{version}'
    link = dest_dir / 'mongod'

    if binary.exists() and not args.force:
        logger.info('%s already exists, not downloading (use --force to re-download)', binary)
    else:
        with tempfile.TemporaryDirectory(prefix='install-mongod.', dir=dest_dir) as tmp:
            tmp = Path(tmp)
            deb_path = tmp / 'server.deb'
            deb_url = f'{REPO_HOST}/{repo.base_path}/{pkg["Filename"]}'
            download(deb_url, deb_path, int(pkg['Size']), pkg['SHA256'])
            extracted = tmp / 'mongod'
            extract_mongod(deb_path, extracted)
            if not args.no_strip:
                strip_binary(extracted)
            extracted.chmod(0o755)
            os.replace(extracted, binary)
            logger.info('Installed %s (%s)', binary, human_size(binary.stat().st_size))

    smoke_test(binary, version)

    if args.no_symlink:
        return
    if link.exists() and not link.is_symlink():
        raise InstallError(f'{link} exists and is not a symlink, refusing to replace it')
    tmp_link = dest_dir / f'.mongod.{os.getpid()}.tmp'
    tmp_link.symlink_to(binary.name)
    os.replace(tmp_link, link)
    logger.info('Symlink %s -> %s', link, binary.name)
    if str(dest_dir) not in os.environ.get('PATH', '').split(os.pathsep):
        logger.warning('Note: %s is not in your PATH', dest_dir)


def download(url, path, expected_size, expected_sha256):
    logger.info('Downloading %s (%s)', url, human_size(expected_size))
    h = hashlib.sha256()
    done = 0
    with urllib.request.urlopen(url, timeout=60) as resp, path.open('wb') as f:
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)
            h.update(chunk)
            done += len(chunk)
            logger.debug('  %s / %s', human_size(done), human_size(expected_size))
    if done != expected_size:
        raise InstallError(f'Downloaded {done} bytes, expected {expected_size}')
    if h.hexdigest() != expected_sha256:
        raise InstallError(f'SHA256 mismatch: got {h.hexdigest()}, expected {expected_sha256}')
    logger.info('SHA256 verified')


def extract_mongod(deb_path, out_path):
    '''
    A .deb is an `ar` archive containing data.tar.<compression>; pull just the
    mongod binary out of that tarball.
    '''
    with deb_path.open('rb') as f:
        members = {name: (offset, size) for name, offset, size in iter_ar_members(f)}
        data_name = next((n for n in members if n.startswith('data.tar')), None)
        if not data_name:
            raise InstallError(f'No data.tar member in {deb_path}, members: {", ".join(members)}')
        offset, size = members[data_name]
        logger.info('Extracting %s from %s', MONGOD_MEMBER, data_name)
        f.seek(offset)
        # The tarball is contiguous in the ar archive; give tarfile a bounded view of it.
        with tarfile.open(fileobj=BoundedReader(f, offset, size), mode='r:*') as tar:
            try:
                member = tar.getmember(MONGOD_MEMBER)
            except KeyError:
                raise InstallError(f'{MONGOD_MEMBER} not found in {data_name}')
            with tar.extractfile(member) as src, out_path.open('wb') as dst:
                shutil.copyfileobj(src, dst, 1024 * 1024)
    logger.info('Extracted %s (%s)', out_path.name, human_size(out_path.stat().st_size))


def iter_ar_members(f):
    '''
    Yield (name, data_offset, size) for each member of a classic `ar` archive.
    '''
    if f.read(8) != b'!<arch>\n':
        raise InstallError('Not an ar archive (bad magic)')
    while True:
        header = f.read(60)
        if len(header) < 60:
            return
        if header[58:60] != b'`\n':
            raise InstallError('Corrupt ar archive (bad member header)')
        name = header[0:16].decode().strip().rstrip('/')
        size = int(header[48:58].decode().strip())
        offset = f.tell()
        yield name, offset, size
        f.seek(offset + size + (size % 2))


class BoundedReader:
    '''
    Read-only, seekable window [offset, offset + size) over an underlying file.
    '''

    def __init__(self, f, offset, size):
        self._f = f
        self._offset = offset
        self._size = size
        self._pos = 0

    def read(self, n=-1):
        remaining = self._size - self._pos
        if n < 0 or n > remaining:
            n = remaining
        self._f.seek(self._offset + self._pos)
        data = self._f.read(n)
        self._pos += len(data)
        return data

    def seek(self, pos, whence=0):
        if whence == 0:
            self._pos = pos
        elif whence == 1:
            self._pos += pos
        elif whence == 2:
            self._pos = self._size + pos
        self._pos = max(0, min(self._pos, self._size))
        return self._pos

    def tell(self):
        return self._pos

    def seekable(self):
        return True

    def readable(self):
        return True


def strip_binary(path):
    strip = shutil.which('strip')
    if not strip:
        logger.info('strip not found, leaving debug symbols in place (install binutils, or use --no-strip to silence this)')
        return
    before = path.stat().st_size
    subprocess.run([strip, str(path)], check=True)
    logger.info('Stripped %s -> %s', human_size(before), human_size(path.stat().st_size))


def smoke_test(binary, version):
    logger.info('Running %s --version', binary)
    try:
        r = subprocess.run([str(binary), '--version'], capture_output=True, text=True, timeout=60)
    except OSError as e:
        raise InstallError(f'Cannot execute {binary}: {e} (missing shared library? try: ldd {binary})')
    if r.returncode != 0:
        raise InstallError(f'{binary} --version failed with exit code {r.returncode}:\n{r.stdout}{r.stderr}')
    first_line = r.stdout.strip().splitlines()[0] if r.stdout.strip() else ''
    if version not in first_line:
        raise InstallError(f'Unexpected output of {binary} --version: {first_line!r} (expected version {version})')
    logger.info('OK: %s', first_line)


def parse_packages(text):
    '''
    Parse a Debian Packages index into a list of dicts (one per stanza).
    '''
    stanzas = []
    current = {}
    key = None
    for line in text.splitlines():
        if not line.strip():
            if current:
                stanzas.append(current)
            current, key = {}, None
        elif line[0] in ' \t' and key:
            current[key] += '\n' + line.strip()
        else:
            key, _, value = line.partition(':')
            current[key.strip()] = value.strip()
    if current:
        stanzas.append(current)
    return stanzas


def version_key(v):
    '''
    Sort key for Debian-ish versions: numeric dotted parts, with a `~` suffix
    (pre-release, e.g. 8.0.0~rc1) sorting before the final release.
    '''
    main, _, pre = v.partition('~')
    nums = tuple(int(x) for x in re.findall(r'\d+', main))
    return (nums, pre == '', pre)


def detect_distro():
    distro = os_release().get('ID')
    if not distro:
        raise InstallError('Cannot detect distro ID from /etc/os-release; use --distro')
    return distro


def detect_codename():
    codename = os_release().get('VERSION_CODENAME')
    if not codename:
        raise InstallError('Cannot detect VERSION_CODENAME from /etc/os-release; use --codename')
    return codename


def detect_arch():
    machine = platform.machine()
    if machine not in ARCH_MAP:
        raise InstallError(f'Unsupported architecture {machine!r}; use --arch')
    return ARCH_MAP[machine]


def os_release():
    info = {}
    try:
        with open('/etc/os-release') as f:
            for line in f:
                key, _, value = line.strip().partition('=')
                if key:
                    info[key] = value.strip('"')
    except FileNotFoundError:
        pass
    return info


def http_get(url):
    logger.debug('GET %s', url)
    with urllib.request.urlopen(url, timeout=60) as resp:
        return resp.read()


def human_size(n):
    for unit in ('B', 'KB', 'MB', 'GB'):
        if n < 1024 or unit == 'GB':
            return f'{n:.0f} {unit}' if unit == 'B' else f'{n:.1f} {unit}'
        n /= 1024


if __name__ == '__main__':
    main()
