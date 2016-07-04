import logging, os, subprocess
from config import Config
from database import DatabaseClient
from datetime import datetime, timedelta
from plex import PlexClient
from psycopg2 import IntegrityError
from threading import Timer

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

class DVR(DatabaseClient):
    def __init__(self, config = None, media_extension = 'm4v'):
        self.config = config if config else Config().load()
        self.media_extension = media_extension
        self.media_dir = self.config.get('plex', 'media_dir')
        self.plex_section_id = self.config.get('plex', 'section_id')
        self.hdhr_ip = self.config.get('hdhomerun', 'ip')
        self.hdhr_port = self.config.get('hdhomerun', 'recording_port')
        self.hdhr_profile = self.config.get('hdhomerun', 'transcode_profile')
        self.start_early_sec = int(self.config.get('dvr', 'start_early_sec'))
        self.end_late_sec = int(self.config.get('dvr', 'end_late_sec'))
        self.recording_script_dir = self.config.get('dvr', 'recording_script_dir')
        self.recording_log_file = self.config.get('dvr', 'recording_log_file')
        self.set_recording_status_script_path = os.path.realpath(os.path.join(os.path.dirname(__file__), '../set-recording-status'))
        self.refresh_plex_section_script_path = os.path.realpath(os.path.join(os.path.dirname(__file__), '../refresh-plex-section'))
        DatabaseClient.__init__(self, self.config)

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
            # TODO: determine an available tuner dynamically
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

    def skip_recording(self, recording_id):
        self.execute('SELECT * FROM recording WHERE id = %s', [recording_id])
        rec = self.fetchone()
        if rec:
            return self.set_recording_status(recording_id, 'skipped')
        else:
            raise Exception('Recording {0} not found'.format(id))

    def delete_recording(self, recording_id):
        self.execute('SELECT * FROM recording WHERE id = %s', [recording_id])
        rec = self.fetchone()
        if rec:
            logger.info('Deleting recording {0}, media_path={1}'.format(rec.id, rec.media_path))
            if os.path.isfile(rec.media_path):
                os.remove(rec.media_path)
            else:
                logger.warning('Recording file not found: {0}'.format(rec.media_path))
            self.execute('DELETE FROM recording WHERE id = %s', [recording_id])
            PlexClient(config = self.config).refresh_section(self.plex_section_id)
        else:
            raise Exception('Recording {0} not found'.format(id))

    def add_season_pass(self, title, new_only):
        try:
            self.execute('INSERT INTO season_pass (program_title, new_only) VALUES (%s, %s)', [title, new_only])
            self.reconcile_season_pass_recordings()
            self.execute('SELECT * FROM season_pass WHERE program_title = %s', [title])
            return self.fetchone()
        except IntegrityError as e:
            return {'error': str(e)}

    def reconcile_season_pass_recordings(self):
        logger.info('Deleting skipped recordings for past programs')
        self.execute('DELETE FROM recording USING station_program WHERE recording.status = \'skipped\' AND station_program.id = recording.station_program_id AND station_program.air_date_time < CURRENT_TIMESTAMP')
        logger.info('Rows deleted: {0}'.format(self.rowcount()))
        logger.info('Reconciling season pass recordings')
        self.execute('DELETE FROM recording USING season_pass, station_program, program WHERE recording.status NOT IN (\'recording\',\'ready\') AND season_pass.id = recording.season_pass_id AND station_program.id = recording.station_program_id AND program.id = station_program.program_id AND program.title != season_pass.program_title')
        logger.info('Rows deleted: {0}'.format(self.rowcount()))
        self.execute('SELECT season_pass.id as season_pass_id, station_program.id as station_program_id, station_program.air_date_time, station_program.program_id FROM season_pass JOIN program ON program.title = season_pass.program_title JOIN station_program ON station_program.program_id = program.id JOIN station ON station.id = station_program.station_id WHERE station.active AND station_program.air_date_time > CURRENT_TIMESTAMP AND (station_program.new OR NOT season_pass.new_only) AND NOT EXISTS (SELECT 1 FROM recording WHERE station_program_id = station_program.id) ORDER BY station_program.air_date_time, season_pass.priority, season_pass.id')
        for row in self.fetchall():
            # This is necessary to avoid duplicate recordings
            program_id = row.program_id
            self.execute('SELECT 1 FROM recording JOIN station_program ON station_program.id = recording.station_program_id WHERE station_program.program_id = %s', [program_id])
            if not self.fetchone():
                season_pass_id = row.season_pass_id
                station_program_id = row.station_program_id
                air_date_time = row.air_date_time
                self.execute('SELECT * FROM program WHERE id = %s', [program_id])
                program = self.fetchone()
                # Deconflict with existing recordings (TODO: manual takes precedence)
                self.execute('SELECT program.title FROM recording JOIN station_program ON station_program.id = recording.station_program_id JOIN program ON program.id = station_program.program_id WHERE station_program.air_date_time <= %s AND station_program.air_date_time + (station_program.duration||\' seconds \')::interval > %s', [air_date_time, air_date_time])
                conflict = self.fetchone()
                if conflict:
                    logger.warning('CONFLICT: Cannot schedule {0} at {1}, conflicts with {2}'.format(program.title, air_date_time, conflict.title))
                else:
                    media_path = self.dest_file(program, air_date_time)
                    logger.info('Scheduling \'{0}\' at {1}'.format(program.title, air_date_time))
                    self.execute('INSERT INTO recording (status, station_program_id, season_pass_id, media_path) VALUES (\'pending\', %s, %s, %s)',
                                 [station_program_id, season_pass_id, media_path])

    def purge_old_data(self):
        logger.info('Purging old station_program entries')
        self.execute('DELETE FROM station_program WHERE air_date_time + (duration||\' seconds\')::interval < CURRENT_TIMESTAMP AND NOT EXISTS (SELECT 1 FROM recording WHERE station_program_id = station_program.id)')
        logger.info('Rows deleted: {0}'.format(self.rowcount()))

        logger.info('Purging unscheduled program entries')
        self.execute('DELETE FROM program WHERE NOT EXISTS (SELECT 1 FROM station_program WHERE program_id = program.id)')
        logger.info('Rows deleted: {0}'.format(self.rowcount()))

        logger.info('Purging old station_schedule entries')
        self.execute("DELETE FROM station_schedule WHERE start_date_utc < date(CURRENT_TIMESTAMP - INTERVAL '1 day')")
        logger.info('Rows deleted: {0}'.format(self.rowcount()))
