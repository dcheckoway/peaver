import logging, requests
from xml.etree import ElementTree

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

class PlexException(Exception):
    def __init__(self, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)

class PlexNotRunning(PlexException):
    def __init__(self, base_url):
        PlexException.__init__(self, 'Plex Media Server is not running at {0}'.format(base_url))

class PlexRefreshError(PlexException):
    def __init__(self, section_id, status_code):
        PlexException.__init__(self, 'Plex refresh of section {0} failed (status code {1})'.format(section_id, status_code))

class PlexClient():
    def __init__(self, base_url = None, config = None):
        if base_url:
            self.base_url = base_url
        else:
            config = config if config else Config().load()
            self.base_url = config.get('plex', 'base_url')

    def library_sections(self):
        try:
            response = requests.get('{0}/library/sections'.format(self.base_url))
        except requests.exceptions.ConnectionError:
            raise PlexNotRunning(self.base_url)
        media_container = ElementTree.fromstring(response.content)
        sections = {}
        for directory in media_container:
            sections[directory.attrib['key']] = {
                'name': directory.attrib['title'],
                'paths': [location.attrib['path'] for location in directory.findall('Location')]
            }
        return sections

    def refresh_section(self, section_id):
        logger.info('Refreshing Plex section {0}'.format(section_id))
        response = requests.get('{0}/library/sections/{1}/refresh'.format(self.base_url, section_id))
        if response.status_code != 200:
            raise PlexRefreshError(section_id, response.status_code)
