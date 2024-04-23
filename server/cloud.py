from twisted.internet.protocol import Protocol, Factory
from twisted.internet import reactor
from twisted.internet.protocol import ServerFactory as ServFactory, connectionDone
from twisted.internet.endpoints import TCP4ServerEndpoint
import struct
import os
import sqlite3

class CloudDB(object):
    DB_NAME = 'cloud.db'
    """Stores thing information for the cloud"""
    def __init__(self):
        self._dirname  = os.path.dirname(os.path.realpath(__file__))
        self._filename = self._dirname + os.path.sep + CloudDB.DB_NAME
        self._init_db()

    def _init_db(self):
        self._is_new   = not os.path.exists(self._filename)
        with sqlite3.connect(self._filename) as conn:
            if self._is_new:
                print('Initializing a new cloud database')
                conn.execute('CREATE TABLE thing (thing_id TEXT, key TEXT, thing_name TEXT, thing_ip TEXT, thing_port INTEGER)')
                # for prototype password_hash contains password itself
                conn.execute('CREATE TABLE user (user_id TEXT, password_hash TEXT)')
                conn.execute('CREATE TABLE user_thing (user_id TEXT, thing_id TEXT)')
                conn.execute('''INSERT INTO thing(thing_id, key, thing_ip, thing_port)
                                VALUES ('AC001', '11', 'localhost', 8002), 
                                       ('AC002', '11', 'localhost', 8003),                             
                                       ('LB001', '11', 'localhost', 8004)''')
                conn.commit()
    
    def insert_user_info(self,user_id,user_pass):
        values = [("('%s', '%s')" % (user_id, user_pass))]
        # print(values)
        values = ', '.join(values)
        query = 'INSERT INTO user VALUES %s' % values
        with sqlite3.connect(self._filename) as conn:
            conn.execute(query)
            conn.commit() 

    def insert_user_thing(self,user_id,thing_id):
        values = [("('%s', '%s')" % (user_id, thing_id))]
        # print(values)
        values = ', '.join(values)
        query = 'INSERT INTO user_thing VALUES %s' % values
        with sqlite3.connect(self._filename) as conn:
            conn.execute(query)
            conn.commit()

    def get_all_things_dict(self):
        things = {}
        with sqlite3.connect(self._filename) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT thing_id, key, ip FROM thing')
            for row in cursor.fetchall():
                thing_id, key, ip = row
                things[thing_id] = {
                    "key": key,
                    "ip": ip
                }
        return things
    
    def verify_thing(self, thing_id, key):
        things = []
        print("thing_key is",key)
        with sqlite3.connect(self._filename) as conn:
            query = 'SELECT thing_id FROM thing WHERE thing_id=:thing_id AND key=:key'
            print("query is", query)
            cursor = conn.cursor()
            print("cursor is", cursor)
            ex = cursor.execute(query, {'thing_id': thing_id, 'key': key})
            print("ex is", ex)
            things = list(cursor.fetchall())
            print("things list is",things)
        return len(things) > 0

    def get_thing_address(self, thing_id, key):
        things = []
        print("thing_key is",key)
        with sqlite3.connect(self._filename) as conn:
            query = 'SELECT thing_ip, thing_port FROM thing WHERE thing_id=:thing_id AND key=:key'
            # print("query is", query)
            cursor = conn.cursor()            
            cursor.execute(query, {'thing_id': thing_id, 'key': key})
            things = list(cursor.fetchall())
            print("things list is",things)
        return things   
   
    def authenticate_user(self, username, password_hash):
        users = []
        with sqlite3.connect(self._filename) as conn:
            query = 'SELECT user_id FROM user WHERE username=:username AND password_hash=:password_hash'
            cursor = conn.cursor()
            cursor.execute(query, {'username': username, "password_hash": password_hash})
            users = list(cursor.fetchall())
        return len(users) > 0
        
    def get_user_thing_ids(self, username, password_hash):
        things = []
        with sqlite3.connect(self._filename) as conn:
            cursor = conn.cursor()
            query = """SELECT t.thing_id, t.key, ut.thing_name
                    FROM
                        user u
                        INNER JOIN user_thing ut ON u.user_id=ut.user_id
                        INNER JOIN thing t ON t.thing_id=ut.thing_id
                    WHERE
                        u.username=:username AND
                        u.password_hash=:password_hash"""
            cursor.execute(query, {'username': username, "password_hash": password_hash})
            for row in cursor.fetchall():
                thing_id, key, thing_name = row
                things.append({"thing_id": thing_id, "key": key, "thing_name": thing_name})
        return things

class IotaException(Exception):
    pass

class MessageTooBigException(IotaException):

    def __init__(self, msg):
        self.msg = msg

class Echo(Protocol):
    db = CloudDB()

    def connectionMade(self):
        print("connection made in cloud")
         
    def dataReceived(self, data):
        data = data.decode("utf-8")
        print(data)
        if("verify" in data):
            self.verify_device_data(data)
        elif("req_add" in data):
            self.send_thing_address(data)    

    def verify_device_data(self,data): 
        verify = False
        data = data.split(':')
        print("data is",data)
        #verify = select * from device_info where device_id = data[0] and password = data[1]
        verify = self.db.verify_thing(data[3],data[4])
        print("verify is", verify)
        if(verify):
            verify =str(verify)
            payload = "pwd_verified" +":"+ verify
            self.db.insert_user_info(data[1],data[2])
            self.db.insert_user_thing(data[1],data[3])            
        else:
            verify =str(verify)
            payload = "pwd_verified" +":"+ verify            
        msg = self._build_message(payload)
        self.send_data(msg)

    
    def send_thing_address(self,data):
        # get the ip address from database using thing ip and key and userid
        data = data.split(':')
        print("data is",data)
        things = self.db.get_thing_address(data[1],data[2])
        tip = str(things[0][0])
        tport = str(things[0][1])
        print(things[0][0])
        addr = "ip_addr:"+ tip + ":" + tport
        print("ip_addr",addr)
        self.send_data(addr)

    def _build_message(self,payload, key=None):
        # self.payload = payload
        # print("here1",payload)
        if len(payload) > 3994:
            raise MessageTooBigException("Message too big!")
        protocol_name, protocol_version = "1", "1"
        header = protocol_name + ":" + protocol_version
        message = header +":"+ payload
        return message

    def send_data(self,data): 
        self.transport.write(data.encode("utf-8"))  

    def connectionLost(self, reason=connectionDone):
        # self.disconnect()
        pass

def main():
    f = Factory()
    f.protocol = Echo
    reactor.listenTCP(8001, f)
    reactor.run()


if __name__ == "__main__":
    main()
