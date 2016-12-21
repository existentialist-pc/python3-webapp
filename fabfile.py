# fabfile.py
import os, re
from datetime import datetime

from fabric.api import *

env.user = 'cwr'
env.sudo_user = 'root'
env.hosts = ['127.0.0.1']

db_user = 'root'
db_password = ''

_TAR_FILE = 'dist-awesome.tar.gz'


def build():
    includes = ['static', 'templates', 'transwarp', 'favicon.ico', '*.py']
    # raise error when tar documents in includes don't exist, but could be ignored.
    excludes = ['test', '.*', '*.pyc','*.pyo']
    local('rm -f dist/%s' % _TAR_FILE)
    with lcd(os.path.join(os.path.abspath('.'), 'www')):  # do in shell under this path
        cmd = ['tar', '--dereference', '-czvf', '../dist/%s' % _TAR_FILE]
        cmd.extend(['--exclude=\'%s\'' % ex for ex in excludes])
        cmd.extend(includes)
        local(' '.join(cmd))

_REMOTE_TMP_TAR = '/tmp/%s' % _TAR_FILE  # /document_path/file
_REMOTE_BASE_DIR = '/home/cwr/srv/awesome'


def deploy():
    newdir = 'www-%s' % datetime.now().strftime('%y-%m-%d_%H.%M.%S')
    run('rm -f %s' % _REMOTE_TMP_TAR)  # shell sentence under normal condition with no sudo
    put('dist/%s' % _TAR_FILE, _REMOTE_TMP_TAR)
    with cd(_REMOTE_BASE_DIR):
        sudo('mkdir %s' % newdir)
    with  cd('%s/%s' % (_REMOTE_BASE_DIR, newdir)):
        sudo('tar -xzvf %s' % _REMOTE_TMP_TAR)
    with cd(_REMOTE_BASE_DIR):
        sudo('rm -f www')
        sudo('ln -s %s www' % newdir)  # www -> newdir document  link symbolic www softlink...
        sudo('chown www-data:www-data www')  # chown [options]... [owner][:[group]] document_or_file_name
        sudo('chown -R www-data:www-data %s' % newdir)

    with settings(warn_only=True):  # restart Python serve and nginx serve
        sudo('supervisorctl stop awesome')
        sudo('supervisorctl start awesome')
        sudo('/etc/init.d/nginx reload')




