import yaml
import json
import time
import sqlite3
import logging
import os.path

from websocket import create_connection, WebSocketConnectionClosedException

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
            log_path = self.cfg["log_path"]
        except KeyError:
            log_path = self.room + ".log"
        logging.basicConfig(filename=log_path, level=log_level)

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

        self.db = sqlite3.connect(db_path)
        self._db_init()

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
                  "id": str(self.data["msg_id"])}
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
            self.db.execute("INSERT INTO message VALUES (?, ?, ?, ?, ?, ?)",
                            (self.room,
                            packet["data"]["id"],
                            packet["data"]["parent"],
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
        print(type(newest))
        last_message_id = packet["data"]["parent"]
        last_msg = self.db.execute("SELECT content, time, id, parent FROM message WHERE id = ?", (last_message_id,)).fetchone()
        root_msg = self.db.execute("SELECT content, time, id FROM message WHERE id = ?", (last_msg[3],)).fetchone()
        limit = self.cfg["msg_limit"]
        candidates = self.db.execute("SELECT content, time, id FROM message WHERE parent = ? AND time <= ? ORDER BY time ASC;",
                                     (root_msg[2],
                                      newest)).fetchall()
        if len(candidates) < limit:
            # not enough messages, get the parent
            candidates = [root_msg] + candidates
        # TODO filter messages by time

        self._send_message(str(candidates), last_message_id)


    def _dispatch(self, packet):
        # TODO: Check for error/bounce packets, and replies with error field
        logging.debug("Dispatching packet.")
        if packet["type"] == "ping-event":
            self._handle_ping_event(packet)
        elif packet["type"] == "send-event":
            self._handle_send_event(packet)


    def run(self):
        logging.debug("Starting.")
        self._set_nick()

        while(True):
            try:
                rawdata = self.conn.recv()
                packet = json.loads(rawdata)
            except WebSocketConnectionClosedException:
                sleep(3)
                self._connect()
            else:
                self._dispatch(packet)

if __name__ == "__main__":
    weedbot = WeedBot()
    weedbot.run()