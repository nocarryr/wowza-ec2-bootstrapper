import os
import sys
BASE_PATH = os.path.split(os.path.split(os.path.dirname(__file__))[0])[0]
sys.path.append(BASE_PATH)

from flask import (
    Flask, 
    request, 
    redirect, 
    url_for, 
    session, 
    render_template, 
)
app = Flask(__name__)

from wowza_ec2_bootstrapper.config import Config
from wowza_ec2_bootstrapper.config import build_config as build_config_obj
from wowza_ec2_bootstrapper import actions
    
@app.route('/')
def index():
    return render_template('index.html')
    
@app.route('/build_config', methods=['GET', 'POST'])
def build_config():
    if request.method == 'GET':
        return render_template('build_config.html')
    conf_json = request.form['conf_json']
    if conf_json:
        config = Config.from_json(json=conf_json, _conf_filename=None)
    else:
        config = build_config_obj(build_default=False, _conf_filename=None)
    session['config_obj_json'] = config.to_json(filename=False)
    return redirect(url_for('edit_config'))
    
@app.route('/edit_config')
def edit_config():
    config = Config.from_json(json=session['config_obj_json'])
    return render_template('edit_config.html', config_obj=config)
    
app.secret_key = 'BIG SECRET'

if __name__ == '__main__':
    app.run(debug=True)
