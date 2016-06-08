import configparser
from flask import Flask, redirect, render_template, request, session, url_for
import logging
import os
import requests
from requests_oauthlib import OAuth1Session
import time
import twitter
import multiprocessing as mp

FORMAT = '%(asctime)s %(name)s %(levelname)s %(message)s'
logging.basicConfig(filename='logs/app.log', level=logging.INFO, format=FORMAT)
logger = logging.getLogger('stalkker')

logger.info('booting system')
logger.info('loading config')
config = configparser.ConfigParser()
config_path = os.path.join(os.path.dirname(__file__), 'app.conf')
if not os.path.isfile(config_path):
    logger.error('config not found')
    raise ConfigNotExistsError('Copy app.conf.org to app.conf. And write settings.')
config.read(config_path)
logger.info('done')

CONSUMER_KEY = config['twitter']['consumer_key']
CONSUMER_SECRET = config['twitter']['consumer_secret']
SECRET_KEY = config['stalkker']['secret_key']

REQUEST_TOKEN_URL = 'https://api.twitter.com/oauth/request_token'
ACCESS_TOKEN_URL = 'https://api.twitter.com/oauth/access_token'
AUTHORIZATION_URL = 'https://api.twitter.com/oauth/authorize'
SIGNIN_URL = 'https://api.twitter.com/oauth/authenticate'

def create_list(target, access_token_key, access_token_secret):
    logger.info('creating stalking-{0} list'.format(target))
    api = twitter.Api(consumer_key=CONSUMER_KEY,
                      consumer_secret=CONSUMER_SECRET,
                      access_token_key=access_token_key,
                      access_token_secret=access_token_secret,
                      sleep_on_rate_limit=True)
    stalking_list = api.CreateList(name='stalking-{0}'.format(target), mode='private')
    myfriends = [f.screen_name for f in api.GetFriends()]
    time.sleep(5)
    member = [f.screen_name for f in api.GetFriends(screen_name=target)
                            if not f.protected or (f.protected and f.screen_name in myfriends)] + [target]
    time.sleep(5)
    api.CreateListsMember(list_id=stalking_list.id, screen_name=member)
    time.sleep(5)
    logger.info('created {0} list'.format(stalking_list.slug))

    # dm 送る
    logger.info('sending dm')
    stalker = stalking_list.user.screen_name
    stalking_list_url = 'https://twitter.com/{0}/lists/{1}'.format(stalker, stalking_list.slug)
    text = "リストの作成が完了しました。{0}".format(stalking_list_url)
    api.PostDirectMessage(screen_name=stalker, text=text)

app = Flask(__name__)
app.secret_key = SECRET_KEY

@app.route('/')
def index():
    logger.info('get access to /')
    return render_template('index.html')

@app.route('/stalking')
def stalking():
    logger.info('get access to /stalking')
    target = request.args['target']
    logger.info('target is {0}'.format(target))
    if requests.get('https://twitter.com/{0}'.format(target)).status_code == 404:
        logger.info('target is not exists')
        return render_template('target_not_exists.html')
    oauth_client = OAuth1Session(CONSUMER_KEY, client_secret=CONSUMER_SECRET, callback_uri=url_for('callback', _external=True))
    responce = oauth_client.fetch_request_token(REQUEST_TOKEN_URL)
    request_token = responce.get('oauth_token')
    request_token_secret = responce.get('oauth_token_secret')
    session['request_token'] = request_token
    session['request_token_secret'] = request_token_secret
    session['target'] = target
    return redirect(oauth_client.authorization_url(AUTHORIZATION_URL))

@app.route('/callback')
def callback():
    if 'denied' in request.args:
        logger.info('stalker did not accepted twitter authenticate')
        return redirect(url_for('index'))
    oauth_verifier = request.args['oauth_verifier']
    oauth_client = OAuth1Session(CONSUMER_KEY, client_secret=CONSUMER_SECRET,
                                 resource_owner_key=session['request_token'],
                                 resource_owner_secret=session['request_token_secret'],
                                 verifier=oauth_verifier)
    responce = oauth_client.fetch_access_token(ACCESS_TOKEN_URL)
    target = session['target']
    access_token_key = responce.get('oauth_token')
    access_token_secret = responce.get('oauth_token_secret')
    logger.info('create background process')
    process = mp.Process(target=create_list, args=(target, access_token_key, access_token_secret))
    process.start()
    return render_template('thanks.html')

if __name__ == '__main__':
    app.run()
