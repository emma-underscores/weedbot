import yaml
import json
import time
import sqlite3

from websocket import create_connection, WebSocketConnectionClosedException

class WeedBot:
    def __init__(self, cfg_path):
        # TODO: Set sane defaults if file does not exist or is not specified
        with open(cfg_path) as f:
            loaded = yaml.load(f)
            self.cfg = loaded
        self._connect()
        self.data = {"msg_id": 0}
        self.db = sqlite3.connect(self.cfg["db_path"])
        self._db_init()

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
            # TODO: reconnect/log
            print("DB init failed.")

    def _connect(self):
        self.conn = create_connection("wss://euphoria.io/room/{}/ws".format(self.cfg["room"]))

    def _send_packet(self, packet):
        try:
            ret = self.conn.send(json.dumps(packet))
            self.data["msg_id"] += 1
            return ret
        # TODO: handle reconnect delays better
        except WebSocketConnectionClosedException:
            time.sleep(3)
            self._connect()
            return self._send_packet(packet)

    def _auth(self):
        packet = {"type": "auth",
                  "data": {"type": "passcode",
                           "passcode": self.cfg["password"]},
                  "id": str(self.data["msg_id"])}
        return self._send_packet(packet)

    def _handle_ping(self, packet):
        # TODO: spin pruning off into separate process/thread
        self._prune_old()
        reply = {"type": "ping-reply",
                 "data": {"time": packet["time"]},
                 "id": str(self.data["msg_id"])}
        return self._send_packet(reply)

    def _set_nick(self):
        packet = {"type": "nick",
                  "data": {"name": self.cfg["nick"]},
                  "id": str(self.data["msg_id"])}
        return self._send_packet(packet)

    def _send_message(self, text, parent):
        packet = {"type": "send",
                  "data": {"content": text,
                           "parent": parent},
                  "id": str(self.data["msg_id"])}
        return self._send_packet(packet)

    def _handle_send_event(self, packet):
        self._log_send_event(packet)

    def _log_send_event(self, packet):
        try:
            self.db.execute("INSERT INTO message VALUES (?, ?, ?, ?, ?, ?)",
                            (self.cfg["room"],
                            packet["id"],
                            packet["parent"],
                            packet["time"],
                            packet["sender"]["name"],
                            packet["content"]))
        # TODO: handle errors properly
        except sqlite3.Error as e:
            print("Failed to record send-event.")

    def _prune_old(self):
        expired = time.time() - self.cfg["expire_hours"] * 60 * 60
        try:
            self.db.execute("DELETE FROM message WHERE time < ?;", expired)
        # TODO: you know the drill...
        except sqlite3.Error as e:
            print("Failed to prune old messages.")
    #
    def _handle_comic(self, packet):
        parent = packet["parent"]
        limit = self.cfg["msg_limit"]
        curs = self.db.cursor()
        curs.execute("SELECT content, time FROM message WHERE parent = ? LIMIT ? ORDER BY time ASC", (parent, limit))
        children = curs.fetchall()
        curs.execute("SELECT content, time FROM message WHERE id = ?", parent)
        top = curs.fetchone()
        messages = [top].extend(children)
        self._send_message("\n".join(str(message) for message in messages))


    def _dispatch(self, packet):
        if self.data["type"] == "ping-event":
            self._handle_ping(packet)
        elif data["type"] == "send-event":
            self._handle_send_event(packet)