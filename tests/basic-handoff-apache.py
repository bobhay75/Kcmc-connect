#!/usr/bin/env python3
"""Exercise the built Core .htaccess with real, loopback-only Apache HTTP/TLS.

Requires apache2-bin and openssl (run as an unprivileged user). For an extracted
runtime, set KCMC_APACHE_BIN and KCMC_APACHE_MODULES; its shared libraries can be
provided through LD_LIBRARY_PATH. No live host, PHP, credentials or data are used.
"""
import http.client
import os
from pathlib import Path
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
MOUNTS = ('kcmc-connect', 'kcmc-connect-stage')
PUBLIC_PATHS = ('', 'member/login.php', 'admin/login.php', 'assets/test.txt')
IMAGE_TARGET = 'https://upload.wikimedia.org/wikipedia/commons/d/d0/Kimberling_City,_Missouri_Bridge.jpg'


class CoreApacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.geteuid() == 0:
            raise RuntimeError('Run the isolated Apache test as an unprivileged user.')
        binary = os.environ.get('KCMC_APACHE_BIN') or shutil.which('apache2')
        if not binary and Path('/usr/sbin/apache2').is_file():
            binary = '/usr/sbin/apache2'
        if not binary or not shutil.which('openssl'):
            raise RuntimeError('Apache and openssl are required; install apache2-bin and openssl.')
        modules = Path(os.environ.get('KCMC_APACHE_MODULES', '/usr/lib/apache2/modules'))
        cls.temp = tempfile.TemporaryDirectory(prefix='kcmc-apache-')
        cls.addClassCleanup(cls.temp.cleanup)
        root = Path(cls.temp.name)
        candidate = root / 'candidate'
        subprocess.run([sys.executable, str(ROOT / 'tools/basic-handoff/build.py'), str(candidate)],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        docroot = root / 'www'
        docroot.mkdir()
        for mount in MOUNTS:
            app = docroot / mount
            app.mkdir()
            shutil.copyfile(candidate / '.htaccess', app / '.htaccess')
            for name in ('index.html', *PUBLIC_PATHS[1:], 'data/sentinel.txt',
                         'backups/sentinel.txt', 'config.php', 'config.example.php',
                         'SETUP-CREDENTIALS.txt', 'VERSION.txt', 'sample.bundle',
                         'sample.json', 'sample.json.tmp-abcdef12', 'sample.ndjson', 'sample.lock'):
                target = app / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text('isolated Apache fixture\n')
            (app / 'empty-directory').mkdir()

        cert, key = root / 'cert.pem', root / 'key.pem'
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                        '-keyout', str(key), '-out', str(cert), '-days', '1',
                        '-subj', '/CN=localhost', '-addext', 'subjectAltName=DNS:localhost,IP:127.0.0.1'],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        cls.tls_context = ssl.create_default_context(cafile=str(cert))
        with socket.socket() as plain, socket.socket() as secure:
            plain.bind(('127.0.0.1', 0))
            secure.bind(('127.0.0.1', 0))
            cls.http_port = plain.getsockname()[1]
            cls.https_port = secure.getsockname()[1]

        loaded = '\n'.join(f'LoadModule {name}_module "{modules}/mod_{name}.so"'
                           for name in ('mpm_event', 'authz_core', 'rewrite', 'headers', 'dir', 'autoindex', 'ssl'))
        config = root / 'httpd.conf'
        config.write_text(f'''ServerRoot "{root}"
DefaultRuntimeDir "{root}"
PidFile "{root}/apache.pid"
ServerName localhost
Listen 127.0.0.1:{cls.http_port}
Listen 127.0.0.1:{cls.https_port}
{loaded}
ErrorLog "{root}/error.log"
LogLevel warn
DirectoryIndex index.html
SSLSessionCache none
<Directory />
    Require all denied
</Directory>
<Directory "{docroot}">
    Options FollowSymLinks
    AllowOverride All
    Require all granted
</Directory>
<VirtualHost 127.0.0.1:{cls.http_port}>
    ServerName localhost
    ServerAlias bobsome1.com www.bobsome1.com
    DocumentRoot "{docroot}"
</VirtualHost>
<VirtualHost 127.0.0.1:{cls.https_port}>
    ServerName localhost
    ServerAlias bobsome1.com www.bobsome1.com
    DocumentRoot "{docroot}"
    SSLEngine on
    SSLCertificateFile "{cert}"
    SSLCertificateKeyFile "{key}"
</VirtualHost>
''')
        syntax = subprocess.run([binary, '-t', '-f', str(config)],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if syntax.returncode:
            raise RuntimeError(syntax.stderr)
        cls.log = (root / 'process.log').open('w+')
        cls.addClassCleanup(cls.log.close)
        cls.process = subprocess.Popen([binary, '-f', str(config), '-DFOREGROUND'],
                                       stdout=cls.log, stderr=cls.log)
        cls.addClassCleanup(cls.stop_apache)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and cls.process.poll() is None:
            try:
                status, _, _ = cls.request('/kcmc-connect/', host='localhost')
                if status == 200:
                    return
            except (OSError, http.client.HTTPException):
                pass
            time.sleep(0.05)
        cls.log.seek(0)
        error = (root / 'error.log').read_text() if (root / 'error.log').exists() else ''
        raise RuntimeError('Isolated Apache did not start: ' + cls.log.read() + error)

    @classmethod
    def stop_apache(cls):
        cls.process.terminate()
        try:
            cls.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cls.process.kill()
            cls.process.wait(timeout=5)

    @classmethod
    def request(cls, path, host='bobsome1.com', secure=False, headers=None):
        if secure:
            connection = http.client.HTTPSConnection('127.0.0.1', cls.https_port,
                                                      context=cls.tls_context, timeout=3)
        else:
            connection = http.client.HTTPConnection('127.0.0.1', cls.http_port, timeout=3)
        try:
            connection.request('GET', path, headers={'Host': host, **(headers or {})})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def assert_upgraded(self, path, host='bobsome1.com', headers=None):
        status, response_headers, _ = self.request(path, host=host, headers=headers)
        self.assertEqual(status, 301)
        self.assertEqual(response_headers.get('Location'), 'https://bobsome1.com' + path)

    def test_http_public_routes_upgrade_on_production_hosts(self):
        for mount in MOUNTS:
            for path in PUBLIC_PATHS:
                for host in ('bobsome1.com', 'www.bobsome1.com', 'BOBSOME1.COM', 'bobsome1.com:80'):
                    with self.subTest(mount=mount, path=path, host=host):
                        self.assert_upgraded(f'/{mount}/{path}', host=host)

    def test_https_routes_do_not_loop(self):
        for mount in MOUNTS:
            for path in PUBLIC_PATHS:
                with self.subTest(mount=mount, path=path):
                    status, headers, body = self.request(f'/{mount}/{path}', secure=True)
                    self.assertEqual(status, 200)
                    self.assertNotIn('Location', headers)
                    self.assertEqual(body, b'isolated Apache fixture\n')

    def test_local_development_stays_on_http(self):
        for host in ('localhost', f'localhost:{self.http_port}', '127.0.0.1'):
            with self.subTest(host=host):
                status, headers, _ = self.request('/kcmc-connect/member/login.php', host=host)
                self.assertEqual(status, 200)
                self.assertNotIn('Location', headers)

    def test_untrusted_host_cannot_control_redirect_destination(self):
        for host in ('attacker.invalid', 'bobsome1.com.attacker.invalid',
                     'bobsome1.com@attacker.invalid'):
            with self.subTest(host=host):
                status, headers, _ = self.request('/kcmc-connect/member/login.php', host=host)
                self.assertIn(status, (200, 400))
                self.assertNotIn('Location', headers)

    def test_nested_path_and_encoded_query_are_preserved(self):
        for mount in MOUNTS:
            self.assert_upgraded(f'/{mount}/member/login.php?next=%2F{mount}%2Fadmin%2F&label=a%20b%26c')
            self.assert_upgraded(f'/{mount}/assets/name%20with%20space.txt?q=%23value')
            self.assert_upgraded(f'/{mount}/assets/hash%23percent%25.txt?name=%2520')

    def test_spoofed_forwarded_scheme_does_not_bypass_native_tls(self):
        path = '/kcmc-connect/member/login.php'
        self.assert_upgraded(path, headers={'X-Forwarded-Proto': 'https'})
        status, headers, _ = self.request(path, secure=True, headers={'X-Forwarded-Proto': 'http'})
        self.assertEqual(status, 200)
        self.assertNotIn('Location', headers)

    def test_private_file_and_directory_denials_remain_effective(self):
        for path in ('data/sentinel.txt', 'backups/sentinel.txt', 'config.php',
                     'config.example.php', 'SETUP-CREDENTIALS.txt', 'VERSION.txt',
                     'sample.bundle', 'sample.json', 'sample.json.tmp-abcdef12',
                     'sample.ndjson', 'sample.lock', 'empty-directory/'):
            for secure, host in ((True, 'bobsome1.com'), (False, 'localhost')):
                with self.subTest(path=path, secure=secure):
                    status, _, body = self.request('/kcmc-connect/' + path, host=host, secure=secure)
                    self.assertEqual(status, 403)
                    self.assertNotIn(b'isolated Apache fixture', body)

    def test_existing_image_redirects_and_security_headers_remain(self):
        for path in ('table-rock-bridge-v2.webp', 'cross-over-lake.jpg'):
            status, headers, _ = self.request('/kcmc-connect/assets/visuals/' + path, secure=True)
            self.assertEqual(status, 302)
            self.assertEqual(headers.get('Location'), IMAGE_TARGET)
        _, headers, _ = self.request('/kcmc-connect/', secure=True)
        self.assertEqual(headers.get('X-Content-Type-Options'), 'nosniff')
        self.assertEqual(headers.get('X-Frame-Options'), 'SAMEORIGIN')
        self.assertEqual(headers.get('Referrer-Policy'), 'strict-origin-when-cross-origin')


if __name__ == '__main__':
    unittest.main(verbosity=2)
