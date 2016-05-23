import json, logging, requests
from config import Config

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

class DictWithAttributeAccess(dict):
    def __getattr__(self, key):
        return self[key]

    def __setattr__(self, key, value):
        self[key] = value

class StatusException(Exception):
    def __init__(self, message, status):
        Exception.__init__(self, message)
        self.status = status

class SchedulesDirectAPI():
    def __init__(self, config = None, base_url = 'https://json.schedulesdirect.org/20141201/'):
        config = config if config else Config().load()
        self.username = config.get('schedules_direct', 'username')
        self.password_digest = config.get('schedules_direct', 'password_digest')
        self.base_url = base_url
        self.token = None

    def url(self, path):
        return path if path.startswith('https://') else '%s%s' % (self.base_url, path)

    def establish_token(self):
        if not self.token:
            logger.info('Establishing token')
            r = requests.post(self.url('token'), data = json.dumps({'username': self.username, 'password': self.password_digest}))
            j = r.json()
            if j['code'] != 0:
                raise Exception('Unexpected response: %s' % json.dumps(j))
            self.token = j['token']
            logger.info('Token is %s' % self.token)

    def make_headers(self, headers):
        self.establish_token()
        h = {'token': self.token}
        h.update(headers)
        return h

    def json(self, response):
        return json.loads(response.content, object_hook = DictWithAttributeAccess)

    def get(self, path, headers = {}):
        get_headers = self.make_headers(headers)
        return self.json(requests.get(self.url(path), headers = get_headers))

    def post(self, path, data, content_type = 'application/json', headers = {}):
        post_headers = self.make_headers(headers)
        #post_headers.update({'Content-Type': content_type})
        return self.json(requests.post(self.url(path), headers = post_headers, data = json.dumps(data) if data else None))

    def ensure_online(self):
        status = self.get_status()
        if status.code != 0:
            raise StatusException('nonzero status code', status)
        elif status.systemStatus[0].status != 'Online':
            raise StatusException('Schedules Direct is not online', status)

    def get_status(self):
        return self.get('status')

    def get_lineup(self, lineup):
        return self.get('lineups/%s' % lineup)
