import logging, os, subprocess
from config import Config
from database import DatabaseClient
from datetime import datetime, timedelta
from threading import Timer

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

class DVR(DatabaseClient):
    def __init__(self, config = None, media_extension = 'm4v'):
        if not config:
            config = Config().load()
        self.media_extension = media_extension
        self.media_dir = config.get('plex', 'media_dir')
        self.plex_section_id = config.get('plex', 'section_id')
        self.hdhr_ip = config.get('hdhomerun', 'ip')
        self.hdhr_port = config.get('hdhomerun', 'recording_port')
        self.hdhr_profile = config.get('hdhomerun', 'transcode_profile')
        self.start_early_sec = int(config.get('dvr', 'start_early_sec'))
        self.end_late_sec = int(config.get('dvr', 'end_late_sec'))
        self.recording_script_dir = config.get('dvr', 'recording_script_dir')
        self.recording_log_file = config.get('dvr', 'recording_log_file')
        self.set_recording_status_script_path = os.path.realpath(os.path.join(os.path.dirname(__file__), '../set-recording-status'))
        self.refresh_plex_section_script_path = os.path.realpath(os.path.join(os.path.dirname(__file__), '../refresh-plex-section'))
        DatabaseClient.__init__(self, config)

    def dest_file(self, program, air_date_time):
        title = program.title.replace(os.sep, '-')
        title_dir = os.path.join(self.media_dir, title)
        if program.season and program.episode:
            basename = '{0} S{1}E{2}'.format(title, program.season, program.episode)
        else:
            air_date = air_date_time.strftime('%Y-%m-%d')
            if program.episode_title:
                basename = '{0} - {1} - {2}'.format(title, air_date, program.episode_title.replace(os.sep, '-'))
            else:
                air_time = air_date_time.strftime('%H:%M')
                basename = '{0} - {1} - {2}'.format(title, air_date, air_time)
        filename = '{0}.{1}'.format(basename, self.media_extension)
        return os.path.realpath(os.path.join(title_dir, filename))

    def scan_for_upcoming_recordings(self):
        threshold = '10 minutes'
        logger.info('Scanning for upcoming recordings, threshold: {0}'.format(threshold))
        self.execute('SELECT recording.id as recording_id, lineup_station.atsc, station_program.air_date_time, station_program.duration, recording.media_path FROM recording JOIN station_program ON station_program.id = recording.station_program_id JOIN lineup_station ON lineup_station.station_id = station_program.station_id WHERE recording.status = \'pending\' AND station_program.air_date_time <= (CURRENT_TIMESTAMP + INTERVAL \'{0}\') ORDER BY station_program.air_date_time'.format(threshold))
        for row in self.fetchall():
            start_time = row.air_date_time - timedelta(seconds = self.start_early_sec)
            duration_sec = self.start_early_sec + row.duration + self.end_late_sec
            script_path = self.generate_recording_script(row.recording_id, row.atsc, duration_sec, row.media_path)
            self.set_recording_status(row.recording_id, 'scheduled')
            sec_until = timedelta.total_seconds(start_time - datetime.now())
            logger.info('Scheduling execution of {0} in {1} seconds'.format(script_path, sec_until))
            Timer(sec_until, self.invoke_script, [script_path]).start()

    def generate_recording_script(self, recording_id, atsc, duration_sec, media_path):
        capture_url = self.stream_capture_url(atsc, duration_sec)
        if not os.path.exists(self.recording_script_dir):
            logger.info('Creating script directory: {0}'.format(self.recording_script_dir))
            os.makedirs(self.recording_script_dir)
        script_path = os.path.realpath(os.path.join(self.recording_script_dir, 'capture-recording-{0}.sh'.format(recording_id)))
        media_path_dir = os.path.dirname(media_path)
        logger.info('Writing recording script: {0}'.format(script_path))
        with open(script_path, 'wb') as f:
            print >> f, '#! /bin/bash -x'
            print >> f, 'exec > {0} 2>&1'.format(self.recording_log_file)
            print >> f, '{0} {1} recording'.format(self.set_recording_status_script_path, recording_id)
            print >> f, 'mkdir -p \'{0}\''.format(media_path_dir.replace('\'', '\'\\\'\''))
            print >> f, 'curl -s \'{0}\' > \'{1}\''.format(capture_url, media_path.replace('\'', '\'\\\'\''))
            print >> f, '{0} {1}'.format(self.refresh_plex_section_script_path, self.plex_section_id)
            print >> f, '{0} {1} ready'.format(self.set_recording_status_script_path, recording_id)
            print >> f, 'rm -- "$0"'
        os.chmod(script_path, 0755)
        return script_path

    def stream_capture_url(self, atsc, duration_sec):
        return 'http://{0}:{1}/auto/v{2}?transcode={3}&duration={4}'.format(self.hdhr_ip, self.hdhr_port, atsc, self.hdhr_profile, duration_sec)

    def invoke_script(self, script_path):
        recording_log_file_dir = os.path.dirname(self.recording_log_file)
        if not os.path.exists(recording_log_file_dir):
            logger.info('Creating recording log file directory: {0}'.format(recording_log_file_dir))
            os.makedirs(recording_log_file_dir)
        logger.info('Invoking recording script: {0}'.format(script_path))
        # Ensure that the child process is detached from our process group
        subprocess.Popen([script_path], preexec_fn=os.setpgrp)

    def set_recording_status(self, recording_id, status):
        logger.info('Updating recording {0} status to {1}'.format(recording_id, status))
        self.execute('UPDATE recording SET status = %s WHERE id = %s', [status, recording_id])
        return self.rowcount() == 1
