import base64
import json
import logging
import io
import os
import os.path
import sqlite3
import time

from websocket import create_connection, WebSocketConnectionClosedException
import requests
import yaml
import ComicGenerator


MAX_ERRORS = 5

class InvalidConfigError(Exception):
    pass

class TooManyErrorsError(Exception):
    pass

class WeedBot:
    def __init__(self, cfg_path="default.yaml"):
        # raise an exception if the cfg_path doesn't exist, otherwise load it
        if not os.path.exists(cfg_path):
            logging.exception("config file not found: %s", cfg_path)
            raise InvalidConfigError("config file not found: " + cfg_path)
        with open(cfg_path) as f:
            loaded = yaml.load(f)
            self.cfg = loaded

        try:
            slog_level = self.cfg["log_level"]
        except KeyError:
            slog_level = "warning"

        if slog_level == "debug":
            log_level = logging.DEBUG
        elif slog_level == "info":
            log_level = logging.INFO
        elif slog_level == "error":
            log_level = logging.ERROR
        elif slog_level == "critical":
            log_level = logging.CRITICAL
        elif slog_level == "warning":
            log_level = logging.WARNING
        else:
            raise InvalidConfigError("Invalid logging level: " + slog_level)

        try:
            room = self.cfg["room"]
        except KeyError:
            raise InvalidConfigError("Missing room.")
        self.room = room

        try:
            self.key = self.cfg["api_key"]
        except KeyError:
            raise InvalidConfigError("Missing imgur API key.")

        try:
            log_path = self.cfg["log_path"]
        except KeyError:
            log_path = self.room + ".log"
        # logging.basicConfig(filename=log_path, level=log_level)

        self._connect()
        self.msg_id = 0
        self.error_count = 0

        try:
            self.expire_hours = self.cfg["expire_hours"]
        except KeyError:
            logging.warning("expire_hours missing, defaulting to 24.")
            self.expire_hours = 24

        try:
            db_path = self.cfg["db_path"]
        except KeyError:
            db_path = "weedbot.db"

        try:
            self.nick = self.cfg["nick"]
        except KeyError:
            self.nick = "WeedBot"

        try:
            self.password = self.cfg["password"]
        except KeyError:
            self.password = None

        self.db = sqlite3.connect(db_path)
        self.db.row_factory = sqlite3.Row
        self._db_init()

        self.gen = ComicGenerator.ComicGenerator()


    def _increment_error_count(self):
        self.error_count += 1
        if self.error_count >= MAX_ERRORS:
            raise TooManyErrorsError

    def _db_init(self):
        try:
            self.db.execute("CREATE TABLE IF NOT EXISTS message ("
                            "room TEXT NOT NULL,"
                            "id TEXT NOT NULL,"
                            "parent TEXT,"
                            "time INTEGER,"
                            "sender TEXT,"
                            "content TEXT,"
                            "PRIMARY KEY (room, id)"
                            ");"
                            )
        except sqlite3.Error as e:
            # TODO: reconnect
            logging.critical("Could not initialize database: %s", e)
            # FIXME: Correct way to re-raise exception?
            raise e

    def _connect(self):
        self.conn = create_connection("wss://euphoria.io/room/{}/ws".format(self.cfg["room"]))

    def _send_packet(self, packet):
        logging.debug("Sending packet of type: %s", packet["type"])
        try:
            ret = self.conn.send(json.dumps(packet))
            self.msg_id += 1
            return ret
        # TODO: handle reconnect delays better
        except WebSocketConnectionClosedException:
            time.sleep(3)
            logging.warning("Connection closed. Attempting reconnect.")
            self._connect()
            return self._send_packet(packet)

    def _auth(self):
        logging.debug("Sending authentication.")
        packet = {"type": "auth",
                  "data": {"type": "passcode",
                           "passcode": self.cfg["password"]},
                  "id": str(self.msg_id)}
        return self._send_packet(packet)

    def _handle_ping_event(self, packet):
        # TODO: spin pruning off into separate process/thread
        self._prune_old()
        logging.debug("Forming ping reply.")
        reply = {"type": "ping-reply",
                 "data": {"time": packet["data"]["time"]},
                 "id": str(self.msg_id)}
        return self._send_packet(reply)

    def _set_nick(self):
        logging.debug("Sending nick.")
        packet = {"type": "nick",
                  "data": {"name": self.nick},
                  "id": str(self.msg_id)}
        return self._send_packet(packet)

    def _send_message(self, text, parent):
        logging.debug("Sending message with text: %s", text)
        packet = {"type": "send",
                  "data": {"content": text,
                           "parent": parent},
                  "id": str(self.msg_id)}
        return self._send_packet(packet)

    def _handle_send_event(self, packet):
        logging.debug("Received send-event.")
        self._log_send_event(packet)
        if packet["data"]["content"] == "!comic":
            self._handle_comic(packet)


    def _log_send_event(self, packet):
        logging.debug("Logging send-event.")
        try:
            parent = packet["data"]["parent"]
        except KeyError:
            parent = ""
        try:
            self.db.execute("INSERT INTO message VALUES (?, ?, ?, ?, ?, ?)",
                            (self.room,
                            packet["data"]["id"],
                            parent,
                            packet["data"]["time"],
                            packet["data"]["sender"]["name"],
                            packet["data"]["content"]))
        except sqlite3.Error as e:
            logging.error("Error logging send-event: %s", e)

    def _prune_old(self):
        # get expiration time in seconds
        expired = int(time.time()) - self.expire_hours * 60 * 60
        try:
            self.db.execute("DELETE FROM message WHERE time < ?;", (expired,))
        except sqlite3.Error as e:
            logging.error("Error pruning old messages: %s", e)

    # FIXME: Everything
    # TODO: Handle root level comics
    # TODO: convert to using bare cursor
    def _handle_comic(self, packet):
        logging.debug("Processing !comic command.")
        newest = packet["data"]["time"]
        # parent of !comic command's ID
        try:
            last_message_id = packet["data"]["parent"]
        except KeyError:
            self._send_message("Usage: reply on a new level to the last message you want included in the comic.", packet["data"]["id"])
            return
        # parent of !comic command
        last_msg = self.db.execute("SELECT content, time, id, parent, sender FROM message WHERE id = ?", (last_message_id,)).fetchone()

        # if message not found, send an error
        if last_msg is None:
            self._send_message("Error: message not found in database.", last_message_id)
            return

        # parent of comic conversation
        root_msg = self.db.execute("SELECT content, time, id, parent, sender FROM message WHERE id = ?", (last_msg["parent"],)).fetchone()
        if root_msg is not None:
            root_msg_id = root_msg["id"]
        else:
            root_msg_id = ""

        limit = self.cfg["msg_limit"]

        candidates = self.db.execute("SELECT content, time, id, parent, sender FROM message WHERE parent = ? AND time <= ? ORDER BY time ASC;",
                                     (root_msg_id,
                                      newest)).fetchall()
        if len(candidates) < limit and root_msg is not None:
            # not enough messages, get the parent
            candidates = [root_msg] + candidates
        # TODO filter messages by time


        img = self.gen.make_comic(candidates)
        ret = self._upload_to_imgur(img)

        self._send_message(ret, last_message_id)


    def _dispatch(self, packet):
        # TODO: Check for error/bounce packets, and replies with error field
        logging.debug("Dispatching packet.")
        if packet["type"] == "ping-event":
            self._handle_ping_event(packet)
        elif packet["type"] == "send-event":
            self._handle_send_event(packet)


    def _upload_to_imgur(self, img):
        logging.debug("Uploading image to imgur.")
        headers = {'Authorization': 'Client-ID ' + self.key}
        mem_img = io.BytesIO()
        img.save(mem_img, format="JPEG", quality=85)
        base64img = base64.b64encode(mem_img.getvalue())
        url = "https://api.imgur.com/3/upload.json"
        r = requests.post(url, data={'key': self.key, 'image': base64img, 'title': 'Weedbot Comic'}, headers=headers, verify=False)
        val = json.loads(r.text)
        try:
            return val['data']['link']
        except KeyError:
            return val['data']['error']

    def run(self):
        logging.debug("Starting.")
        if self.password is not None:
            self._auth()
        self._set_nick()

        while(True):
            try:
                rawdata = self.conn.recv()
                packet = json.loads(rawdata)
            except WebSocketConnectionClosedException:
                time.sleep(3)
                self._connect()
                if self.password is not None:
                    self._auth()
                self._set_nick()
            else:
                self._dispatch(packet)




if __name__ == "__main__":
    weedbot = WeedBot()
    weedbot.run()