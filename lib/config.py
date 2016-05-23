import ConfigParser, logging, os

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

class Config(ConfigParser.SafeConfigParser):
    def __init__(self, filename = 'peaver.conf'):
        self.config_dir = os.path.realpath(os.path.join(os.path.dirname(__file__), '../config'))
        self.config_file = os.path.realpath(os.path.join(self.config_dir, filename))
        ConfigParser.SafeConfigParser.__init__(self)

    def load(self):
        if not os.path.exists(self.config_file):
            raise Exception('Config file ({0}) not found, you must run setup first'.format(self.config_file))
        logger.debug('Loading {0}'.format(self.config_file))
        if not self.read(self.config_file):
            raise Exception('Failed to read {0}'.format(self.config_file))
        return self

    def save(self):
        if not os.path.exists(self.config_dir):
            logger.info('Creating directory: {0}'.format(self.config_dir))
            os.makedirs(self.config_dir)
        logger.info('Writing {0}'.format(self.config_file))
        with open(self.config_file, 'w') as f:
            self.write(f)
