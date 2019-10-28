import paramiko
import sys
import traceback
import time
import select
import datetime
import time
import re
import xml.etree.ElementTree as ET
from pprint import pprint
import pytz
import csv
import json
import asyncio
import fabric
from log_init import initialize_logger
from models import CpsuFiles, CpsuFileSchema
from config import db

"""
Note that backend components are located in CTEC in Colorado - the times are therefore in MDT

Get date associated with each break id into UTC for ease of conversion
Attempt to store into sqlite database
Figure out user interaction and updating the database
1 - how to update - will you scan the break log for new breakids
2 - once a new breakid is found will you scan the cpsu

Figure out how to separate marshmallow schemas
Figure out the stupid Mototerm if you can only tail wtf
Finish up creating APIs for TMC
Pick and choose which tmcs to tail for logs? Do I thread the CASU log too?
"""


class SshConnection():
    ip = ""
    username = "vw"
    password = "pinotnoir"

    def __init__(self):
        while True:
            i = 1
            print("Trying to connect to %s (%i/30)" % (self.ip, i))

            i = 1
            try:
                self.ssh = paramiko.SSHClient()
                self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                self.ssh.connect(self.ip, username=self.username, password=self.password)
                print("Connected to %s" % self.ip)
                break
            except paramiko.AuthenticationException:
                print("Authentication failed when connecting to %s" % self.ip)
                sys.exit(1)
            except:
                print("Could not SSH to %s, waiting for it to start" % self.ip)
                i += 1
                time.sleep(2)

            # If we could not connect within time limit
            if i == 30:
                print("Could not connect to %s. Giving up" % self.ip)
                sys.exit(1)

    @staticmethod
    def break_log_date_format():
        return datetime.datetime.now(pytz.timezone('US/Mountain')).strftime('%Y%m%d')


# TODO: where does CASU2/Arris fit into the workflow?
class ArrisCasu(SshConnection):
    ip = "172.30.85.42"
    logger = initialize_logger("ArrisCasu")


class CiscoCasu(SshConnection):
    ip = "172.30.85.41"
    logger = initialize_logger("CiscoCasu")

    # TODO: It's not live - is there a point in tailing this log at this point?
    async def tail_log(self):
        # Send the command (non-blocking)
        i = 0
        try:
            stdin, stdout, stderr = self.ssh.exec_command(
                f"cd /data/casurun/ && tail -f breaks-{SshConnection.break_log_date_format()}.log | grep --line-buffered 'HGTV'",
                get_pty=True)
            sys.stdout.flush()
            while True:
                if not self.ssh.get_transport().is_active():
                    print("Disconnect")
                    try:
                        self.ssh.connect(self.ip, username=self.username, password=self.password)
                        await asyncio.sleep(1)
                        if self.ssh.get_transport().is_active():
                            stdin, stdout, stderr = self.ssh.exec_command(
                                f"cd /data/casurun/ && tail -f breaks-{SshConnection.break_log_date_format()}.log | grep --line-buffered 'HGTV'",
                                get_pty=True)
                    except Exception:
                        print("Could not SSH to %s, waiting for it to start" % self.ip)

                if stdout.channel.recv_ready():
                    print("ready")
                    try:
                        rl, wl, xl = select.select([stdout.channel], [], [], 0.0)
                        if len(rl) > 0:
                            # Print data from stdout
                            # print(stdout.channel.recv(1024).decode('utf-8'))
                            # TODO: different channels split out two lines at a time... do I parse both? or look for end? idk
                            current = datetime.datetime.now()
                            # break_id = re.search('break (\\d+)', stdout.channel.recv(8192).decode('utf-8'))
                            # ad_id = re.search('adid=(\\d+)', stdout.channel.recv(8192).decode('utf-8'))
                            # instime = re.search('instime=(\\d+:\\d+:\\d+)', stdout.channel.recv(8192).decode('utf-8'))
                            # channel = re.search('\\((\\w+)\\)', stdout.channel.recv(8192).decode('utf-8'))
                            print(f"TESTING {current}:          {stdout.channel.recv(8192).decode('utf-8')}")
                            # test.tmc()

                            break
                            # print(f"TESTING {current}: Break ID: {break_id.group(1)}, Ad ID: {ad_id.group(1)}, instime: {instime.group(1)}, channel:{channel.group(1)}")

                            # break
                    except Exception as e:
                        print(e)
                        traceback.print_exc(file=sys.stdout)
                # await asyncio.sleep(1)
        except Exception as e:
            print(e)
            traceback.print_exc(file=sys.stdout)
        # Disconnect from the host
        finally:
            print("Command done, closing SSH connection")
            self.ssh.close()

    def parse_break_log(self):
        try:
            sftp = self.ssh.open_sftp()
            with sftp.file(f"/data/casurun/breaks-{SshConnection.break_log_date_format()}.log",
                           mode='r') as full_break_log:
                casu_break_log_info = {}
                for line in full_break_log:
                    if re.search('\\((\\w+)\\)', line).group(1) in casu_break_log_info:
                        casu_break_log_info[re.search('\\((\\w+)\\)', line).group(1)][
                            int(re.search('break (\\d+)', line).group(1))] = {
                            "casu_adid": int(re.search('adid=(\\d+)', line).group(1)),
                            "instime": re.search('instime=(\\d+:\\d+:\\d+)', line).group(1),
                            "cpsu": []
                            }
                    else:
                        casu_break_log_info[re.search('\\((\\w+)\\)', line).group(1)] = {
                            int(re.search('break (\\d+)', line).group(1)): {
                                "casu_adid": int(re.search('adid=(\\d+)', line).group(1)),
                                "instime": re.search('instime=(\\d+:\\d+:\\d+)', line).group(1),
                                "cpsu": []
                                }
                            }
            return casu_break_log_info
        finally:
            print("Command done, closing SSH connection")
            self.ssh.close()


class Cpsu(SshConnection):
    ip = "172.30.85.43"
    logger = initialize_logger("Cpsu")
    # today_begin_mdt = datetime.datetime.strptime()

    def parse_playout_files(self, casu_dict):
        try:
            sftp = self.ssh.open_sftp()
            file_list = []

            # TODO: Make this dynamic; check only the last and new playout.csv files
            stdin, stdout, stderr = self.ssh.exec_command(
                f"cd /data/cpsu/Impressions && ls playout_{SshConnection.break_log_date_format()[2:]}*", get_pty=True)
            # Wait for the command to terminate
            while not stdout.channel.exit_status_ready():
                # Only print data if there is data to read in the channel
                if stdout.channel.recv_ready():
                    rl, wl, xl = select.select([stdout.channel], [], [], 0.0)
                    if len(rl) > 0:
                        # When decoded, "\r\n" and two whitespaces are found between each result
                        file_list = stdout.read().decode('utf-8').replace("\r\n", "  ").strip().split("  ")
            # TODO: what format of date...?
            # TODO: do i need a marshmellow schema?
            read_files = CpsuFiles.query.filter(CpsuFiles.read_time == datetime.datetime.now().strftime('%Y-%m-%d')).all()
            file_schema = CpsuFileSchema(many=True)
            all_read_playout_files = file_schema.dump(read_files).data
            read_files = {x for x in all_read_playout_files['filename']}

            pprint(all_read_playout_files)
            # How to force the re-read of last file?
            for playout_file in read_files:
                if len(read_files) > 0 and playout_file != file_list[len(file_list) - 1]:
                    if playout_file in all_read_playout_files:
                        continue
                else:
                    schema = CpsuFileSchema()
                    new_file = schema.load(playout_file, session=db.session).data
                    db.session.add(new_file)
                    db.session.commit()
                    # pprint(schema.dump(new_file).data)

                    with sftp.file(f"/data/cpsu/Impressions/{playout_file}", mode='r') as cpsu_csv:
                        reader = csv.DictReader(cpsu_csv)
                        """
                        OrderedDict([('# mso', 'Charter'),
                                     ('router_id', 'CTEC'),
                                     ('machine_id', 'CPSU1'),
                                     ('mac', '0021be4fc14c'),
                                     ('datetime', '2019-10-11 01:57:58'),
                                     ('break', '201519997'),
                                     ('pos', '0'),
                                     ('adid', '5264'),
                                     ('full_play_flag', '1'),
                                     ('problem_flag', '0'),
                                     ('no_feeder_flag', '0'),
                                     ('profile', '0'),
                                     ('duration', '27.04'),
                                     ('pres_mode', '1'),
                                     ('delayed_playback', '0'),
                                     ('cc', '56'),
                                     ('rpt_datetime', '2019-10-11 01:00:00'),
                                     ('partial_data_flag', '0'),
                                     ('lua_datetime', '2019-10-10 03:45:51'),
                                     ('seg_file_id', '5264'),
                                     ('variant_id', 'e7_400305__0'),
                                     ('flag_mask', '1'),
                                     ('sdv_result', '0'),
                                     ('sdv_sourceid', '0'),
                                     ('sdv_response', '0')])
                        """
                        for row in reader:
                            for channel in casu_dict:
                                if int(row['break']) in casu_dict[channel]:
                                    casu_dict[channel][int(row['break'])]["cpsu"].append(
                                        {"stb_mac": row['mac'],
                                         "cpsu_adid": int(row['adid']),
                                         "full_play_flag": int(row['full_play_flag']),
                                         "profile": int(row['profile']),
                                         "duration": float(row['duration']),
                                         "flag_mask": int(row['flag_mask']),
                                         "sdv_result": int(row['sdv_result'])
                                         }
                                        )

        finally:
            print("Command done, closing SSH connection")
            self.ssh.close()
            sftp.close()

    def test_insert(self):

        # TODO: Make this dynamic; check only the last and new playout.csv files
        # stdin, stdout, stderr = self.ssh.exec_command(
        #     f"cd /data/cpsu/Impressions && ls playout_{SshConnection.break_log_date_format()[2:]}*", get_pty=True)
        # # Wait for the command to terminate
        # while not stdout.channel.exit_status_ready():
        #     # Only print data if there is data to read in the channel
        #     if stdout.channel.recv_ready():
        #         rl, wl, xl = select.select([stdout.channel], [], [], 0.0)
        #         if len(rl) > 0:
        #             # When decoded, "\r\n" and two whitespaces are found between each result
        #             file_list = stdout.read().decode('utf-8').replace("\r\n", "  ").strip().split("  ")
        file_list = ['playout_191027_00.csv',
                      'playout_191027_06.csv',
                      'playout_191027_12.csv',
                      'playout_191027_01.csv',
                      'playout_191027_07.csv',
                      'playout_191027_13.csv',
                      'playout_191027_02.csv',
                      'playout_191027_08.csv',
                      'playout_191027_14.csv',
                      'playout_191027_03.csv',
                      'playout_191027_09.csv',
                      'playout_191027_15.csv',
                      'playout_191027_04.csv',
                      'playout_191027_10.csv',
                      'playout_191027_16.csv',
                      'playout_191027_05.csv',
                      'playout_191027_11.csv',
                      'playout_191027_17.csv']
        read_files = CpsuFiles.query.filter(CpsuFiles.read_time >= datetime.datetime.now().strftime('%Y-%m-%d')+" 06:00:00").filter(CpsuFiles.read_time <= (datetime.datetime.now()+datetime.timedelta(days=1)).strftime('%Y-%m-%d')+" 06:00:00").all()
        pprint(read_files)
        file_schema = CpsuFileSchema(many=True)
        all_read_playout_files = file_schema.dump(read_files)
        # Schema creates:
        """
        [{'filename': 'playout_191027_00.csv',
  'read_time': '2019-10-27T23:43:09.722194'},
 {'filename': 'playout_191027_06.csv',
  'read_time': '2019-10-27T23:43:09.752192'},
 {'filename': 'playout_191027_12.csv',
  'read_time': '2019-10-27T23:43:09.776192'},
 {'filename': 'playout_191027_01.csv',
  'read_time': '2019-10-27T23:43:09.806214'},
 {'filename': 'playout_191027_07.csv',
  'read_time': '2019-10-27T23:43:09.836193'},
 {'filename': 'playout_191027_13.csv',
  'read_time': '2019-10-27T23:43:09.863217'},
 {'filename': 'playout_191027_02.csv',
  'read_time': '2019-10-27T23:43:09.890193'},
 {'filename': 'playout_191027_08.csv',
  'read_time': '2019-10-27T23:43:09.915221'},
 {'filename': 'playout_191027_14.csv',
  'read_time': '2019-10-27T23:43:09.947217'},
 {'filename': 'playout_191027_03.csv',
  'read_time': '2019-10-27T23:43:09.972193'},
 {'filename': 'playout_191027_09.csv',
  'read_time': '2019-10-27T23:43:09.999219'},
 {'filename': 'playout_191027_15.csv',
  'read_time': '2019-10-27T23:43:10.027192'},
 {'filename': 'playout_191027_04.csv',
  'read_time': '2019-10-27T23:43:10.055192'},
 {'filename': 'playout_191027_10.csv',
  'read_time': '2019-10-27T23:43:10.079193'},
 {'filename': 'playout_191027_16.csv',
  'read_time': '2019-10-27T23:43:10.103194'},
 {'filename': 'playout_191027_05.csv',
  'read_time': '2019-10-27T23:43:10.129218'},
 {'filename': 'playout_191027_11.csv',
  'read_time': '2019-10-27T23:43:10.155219'},
 {'filename': 'playout_191027_17.csv',
  'read_time': '2019-10-27T23:43:10.181192'}]
        """
        pprint(all_read_playout_files)
        # How to force the re-read of last file?
        # for playout_file in file_list:
        #     file = CpsuFiles(filename=playout_file)
        #     db.session.add(file)
        #     db.session.commit()


class Stb(SshConnection):
    ip = "172.30.112.19"
    username = "zodiac"
    password = "z0d1D0b"

    # TODO: In progress - I can't retrieve from the pseudo terminal the logs - ask michael...
    async def fabric_test(self):
        with fabric.Connection(host="zodiac@172.30.112.19", connect_kwargs={"password": "z0d1D0b"}) as ssh:
            ssh.run("sshpass -p \"q7KtsXLQzkhAj\" ssh zodiac@10.243.156.70; log_echo on> testing.log", pty=True)
            # with fabric.Connection(host="zodiac@10.243.156.70", connect_kwargs={"password": "q7KtsXLQzkhAj"},
            #                        gateway=ssh) as zodiac:
            #     pass
                # zodiac.run('exit')


    # async def tail_stb_logs(self):
    #     # Send the command (non-blocking)
    #     try:
    #         stdin, stdout, stderr = self.ssh.exec_command("script -f testing.log && tail -f testing.log")
    #
    #         if stdout.channel.recv_ready():
    #             print("ready")
    #             try:
    #                 rl, wl, xl = select.select([stdout.channel], [], [], 0.0)
    #                 if len(rl) > 0:
    #                     # TODO: different channels split out two lines at a time... do I parse both? or look for end? idk
    #                     current = datetime.datetime.now()
    #                     print(f"TESTING {current}:          {stdout.channel.recv(8192).decode('utf-8')}")
    #             except Exception as e:
    #                 print(e)
    #                 traceback.print_exc(file=sys.stdout)
    #     except Exception as e:
    #         print(e)
    #         traceback.print_exc(file=sys.stdout)
    #     # Disconnect from the host
    #     finally:
    #         print("Command done, closing SSH connection")
    #         self.ssh.close()
    #
    # async def log_echo_on(self):
    #     transport = self.ssh.get_transport()
    #     dest_addr = ("10.243.156.70", 22)
    #     local_addr = ("172.30.112.19", 22)
    #     channel = transport.open_channel("direct-tcpip", dest_addr, local_addr)
    #
    #     zodiac = paramiko.SSHClient()
    #     zodiac.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    #     zodiac.connect("10.243.156.70", username="zodiac", password="q7KtsXLQzkhAj", sock=channel)
    #     stdin, stdout, stderr = zodiac.exec_command('"log_echo on"', get_pty=True)
    #     while True:
    #         print(f"{stdout.channel.recv(8192).decode('utf-8')}")
    #         time.sleep(5)


def main():
    start = time.time()

    test = Stb()
    asyncio.run(test.fabric_test())
    # break_logs = CiscoCasu()
    # playout_files = Cpsu()
    # parsed_break_log = break_logs.parse_break_log()
    # playout_files.parse_playout_files(parsed_break_log)
    # pprint(parsed_break_log)
    # playout_files.test_insert()

    end = time.time()
    print(end - start)


if (__name__ == '__main__'):
    main()
