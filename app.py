# -*- coding: utf-8 -*-

from flask import Flask, render_template

app = Flask(__name__, static_url_path='/assets',
            static_folder='./flask_app/assets', 
            template_folder='./flask_app')

@app.route('/')
def index():
    return render_template('index.html')
@app.route('/index.html')
def index_html():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)