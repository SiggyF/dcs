import json
import os
import shutil
import zipfile
from json import dumps
from logging.config import dictConfig, logging
from flask_autodoc import Autodoc
from flask import Flask, request, jsonify, make_response, Response, send_from_directory

with open('logging.json') as jl:
    dictConfig(json.load(jl))

app = Flask(__name__)
auto = Autodoc(app)


if os.environ.has_key('store'):
    app.config['settings'] = os.environ['store']
else:
    if not os.path.exists('/tmp/store'):
        os.mkdir('/tmp/store')
    app.config['settings'] = '/tmp/store'

def __upload__(file_name):
    logging.info(file_name)
    path = os.path.join(app.config['settings'], file_name)
    if os.path.exists(path):
        raise ApplicationException('File (%s) already exists, will not overwrite' % file_name)
    with open(path, 'wb') as f:
        chunk_size=1024
        while True:
            chunk = request.stream.read(chunk_size)
            if len(chunk) == 0:
                break
            f.write(chunk)
            f.flush()
    return 'Upload received!'

def __download__(file_name):
    logging.info(file_name)
    path = os.path.join(app.config['settings'], file_name)
    if not os.path.exists(path):
        raise ApplicationException('Requested file (%s) does not exist' % file_name)
    return send_from_directory(app.config['settings'], file_name)

def __deleter__(file_name):
    logging.info(file_name)
    path = os.path.join(app.config['settings'], file_name)
    if not os.path.exists(path):
        raise ApplicationException('Requested file (%s) does not exist' % file_name)
    os.remove(path)
    return Response('ok')

def __get_all_files__():
    root = app.config['settings']
    if not root or not os.path.exists(root) or not os.path.isdir(root):
        raise ApplicationException('Something wrong with our filesystem (%s)' % root)
    return Response(dumps([f for f in os.listdir(root) if os.path.isfile(os.path.join(root, f))]), mimetype='application/json')

def __extract__(file_name):
    logging.info(file_name)
    path = os.path.join(app.config['settings'], file_name)
    if not os.path.exists(path):
        raise ApplicationException('Requested file (%s) does not exist' % file_name)
    try:
        file_path = os.path.join(app.config['settings'], os.path.splitext(file_name)[0])
        if os.path.exists(file_path):
            shutil.rmtree(file_path)
        os.mkdir(file_path)
        os.chdir(file_path)
        with zipfile.ZipFile('../%s' % file_name, allowZip64=True) as zf:
            zf.extractall()
        created = []
        for d in next(os.walk('.'))[1]:
            os.chdir(d)
            with zipfile.ZipFile('../../job-%s.zip' % d, 'w', compression=zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
                for dir_path, dir_names, file_names in os.walk('.'):
                    for name in file_names:
                        path = os.path.normpath(os.path.join(dir_path, name))
                        if os.path.isfile(path):
                            zf.write(path, path)
            os.chdir('..')
            created.append('job-%s' % str(d))
        os.chdir('..')
        shutil.rmtree(os.path.splitext(file_name)[0])
        return Response(dumps(created), mimetype='application/json')
    except Exception:
        logging.exception('error during extract of %s' % file_name)
        raise ApplicationException('error during extract of %s' % file_name)

def __compress__(pdata, file_name):
    logging.info(file_name)
    file_names = pdata.get_json(force=True)
    file_path = os.path.join(app.config['settings'], os.path.splitext(file_name)[0])
    if os.path.exists(os.path.join(app.config['settings'], file_name)):
        os.remove(os.path.join(app.config['settings'], file_name))
    try:
        if os.path.exists(file_path):
            shutil.rmtree(file_path)
        os.mkdir(file_path)
        os.chdir(file_path)
        for name in file_names:
            zn = '../%s.zip' % name
            if os.path.exists(zn):
                os.mkdir(os.path.splitext(name)[0])
                os.chdir(os.path.splitext(name)[0])
                with zipfile.ZipFile('../../%s.zip' % name, allowZip64=True) as zf:
                    zf.extractall()
                os.remove('../../%s.zip' % name)
                os.chdir('..')
            else:
                os.mkdir('%s_failed' % os.path.splitext(name)[0])
                logging.warning('could not find %s' % zn)
        with zipfile.ZipFile('../%s.zip' % os.path.splitext(file_name)[0], 'w', compression=zipfile.ZIP_DEFLATED, allowZip64=True) as ozf:
            for dir_path, dir_names, files in os.walk('.'):
                for fname in files:
                    path = os.path.normpath(os.path.join(dir_path, fname))
                    if os.path.isfile(path):
                        ozf.write(path, path)
        os.chdir('..')
        if os.path.exists('%s.zip' % os.path.splitext(file_name)[0]) and os.path.getsize('%s.zip' % os.path.splitext(file_name)[0]) > 0:
            shutil.rmtree(os.path.splitext(file_name)[0])
            return Response('ok')
        raise ApplicationException('archive %s.zip not created!' % os.path.splitext(file_name)[0])
    except Exception:
        logging.exception('error during compress of %s' % file_name)
        raise ApplicationException('error during compress of %s' % file_name)


# actual api here :P

@app.route('/')
def documentation():
    return auto.html()

@app.route('/<file_name>', methods=['POST'])
@auto.doc()
def upload(file_name):
    """ upload a file to the store """
    return __upload__(file_name)

@app.route('/<file_name>', methods=['GET'])
@auto.doc()
def download(file_name):
    """ download a file from the store """
    return __download__(file_name)

@app.route('/<file_name>', methods=['DELETE'])
@auto.doc()
def delete(file_name):
    """ delete a file from the store """
    return __deleter__(file_name)

@app.route('/files/', methods=['GET'])
@auto.doc()
def list_files():
    """ List all files in the store """
    return __get_all_files__()

@app.route('/extract/<file_name>', methods=['GET'])
def extract(file_name):
    """ extract a file on the store """
    return __extract__(file_name)

@app.route('/compress/<file_name>', methods=['POST'])
def compress(file_name):
    """ compress multiple archives into one archive on the store """
    return __compress__(request, file_name)


# register error handlers
class ApplicationException(Exception):
    status_code = 500

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['message'] = self.message
        return rv

@app.errorhandler(ApplicationException)
def handle_application_exception(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response
