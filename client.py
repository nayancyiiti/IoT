# install_twisted_rector must be called before importing the reactor
from __future__ import unicode_literals
from asyncio import base_tasks
from kivy.support import install_twisted_reactor
install_twisted_reactor()
from twisted.internet import reactor, protocol, error
import os
import sqlite3
# from scratch_oemcode import TwistedClientApp1
# self.servers = []
# server_type = ["thing", "oem_server"] server type can be one of these
server_id = 0

class ClientDB(object):
    DB_NAME = 'client.db'
    """Stores thing information for the client"""
    def __init__(self):
        self._dirname  = os.path.dirname(os.path.realpath(__file__))
        self._filename = self._dirname + os.path.sep + ClientDB.DB_NAME
        self._is_new   = not os.path.exists(self._filename)
        with sqlite3.connect(self._filename) as conn:
            if self._is_new:
                print('Initializing a new client database..')
                conn.execute('''CREATE TABLE thing (
                    thing_name TEXT,
                    thing_id TEXT,
                    key TEXT,
                    thing_ip TEXT,
                    thing_port INTEGER,
                    cloud_ip TEXT,
                    cloud_port INTEGER,
                    manifest_file TEXT,
                    UNIQUE (thing_id) ON CONFLICT REPLACE
                );''')
                conn.execute('CREATE TABLE user (user_id TEXT, username TEXT, password_hash TEXT)')
                conn.execute('''INSERT INTO user(user_id, username, password_hash)
                                VALUES ('1', 'Nayancy', 'NG1111@')''')
                
                conn.commit()

    def authenticate_user(self, username, password_hash):
        users = []
        with sqlite3.connect(self._filename) as conn:
            query = 'SELECT user_id FROM user WHERE username=:username AND password_hash=:password_hash'
            cursor = conn.cursor()
            cursor.execute(query, {'username': username, "password_hash": password_hash})
            users = list(cursor.fetchall())
        return len(users) > 0

    def insert_thing_info(self, thing):
        # print("thing_port is", thing["thing_port"])
        values = [("('%s', '%s', '%s', '%s', %d, '%s', %d, '%s')" % (thing["thing_name"], thing["thing_id"], thing["key"], thing["thing_ip"], thing["thing_port"], thing["cloud_ip"],thing["cloud_port"],thing["manifest_file"]))]
        print("in insert_thing_info",values)
        values = ', '.join(values)
        query = 'INSERT INTO thing VALUES %s' % values
        with sqlite3.connect(self._filename) as conn:
            conn.execute(query)
            conn.commit()  

    def update_thing_info(self,tid,manifest_file):
        print("update manifest_file name")
        with sqlite3.connect(self._filename) as conn:
            query = 'UPDATE thing SET manifest_file=:manifest_file WHERE thing_id=:thing_id'
            conn.execute(query, {'manifest_file': manifest_file, 'thing_id': tid})
            conn.commit()

    def get_thing_info(self):
        things = {}
        with sqlite3.connect(self._filename) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT thing_name, thing_id, key, thing_ip, thing_port, manifest_file FROM thing')
            for row in cursor.fetchall():
                thing_name, thing_id, key, thing_ip, thing_port, manifest_file = row
                things[thing_id] = {
                    "name": thing_name,
                    "id":thing_id,
                    "key": key,
                    "thing_ip": thing_ip,
                    "thing_port": thing_port,
                    "manifest_file": manifest_file
                }
        print("things",things)        
        return things                 

class EchoClient(protocol.Protocol):
    def connectionMade(self):
        print("inside connection made")
        print(self.factory.app.ip)
        print(self.factory.app.port)
        print(self.factory.app.server_type)  
        self.factory.app.on_connect(self.transport)   
        

    def dataReceived(self, data):
        data = data.decode('utf-8')
        print("data data is",data)
        if("password" in data):
            self.factory.app.password_handle(data)

        elif("pwd_verified" in data):
            data = data.split(':')
            res = data[3]
            print("inside code pwd_verified")
            print(res)            
           
            
            if(res == "True"):
                tid = self.factory.app.thing_id
                print("tid val is ",tid);
                # tkey = self.factory.app.thing_pass
                self.factory.app.saved_device ="no"
                self.factory.app.req_thing_address()
            elif(res == "False"):
                self.factory.app.root.ids.device_invalid.text = "Device is invalid! Please provide correct information."
                pass  

        elif("ip_addr" in data):
            data = data.split(":")
            print("data in ip_addr inside",data)
            data[2] = int(data[2])
            # print("data2 is", data[2])
            thing_info = {'thing_name': self.factory.app.thing_name, 'thing_id': self.factory.app.thing_id,'key': self.factory.app.thing_pass,'thing_ip':data[1],
                          'thing_port':data[2],'cloud_ip':self.factory.app.oem_ip,'cloud_port':self.factory.app.oem_port,
                          'manifest_file':""}
            # close_connection_with_oem()
            self.transport.loseConnection()

            # Now make the connection with thing
            self.factory.app.make_connection_with_thing(data[1],data[2])
            
            # Insert in database
            self.factory.app.db.insert_thing_info(thing_info)
            
            # self.factory.app.probe_request("Probe verify")
            print("sended probe to thing")  
        elif("file" in data):  
            print("inside file transfer")
            x = data.partition(":file:")  
            # print(x[0], x[1], x[2])  
            # get the file name and data
            file_name = x[0].split("/")[-1]
            if(len(file_name) == 0):
                print("Please provide path, not folder path.")
            else:
                print(file_name)            
            
            file_data = x[2]
            
            f = open(file_name,'w')
            f.write(file_data)
            f.close()                
            print("file_name is ",file_name)  

            self.factory.app.db.update_thing_info(self.factory.app.thing_id, file_name)
            # print("update manifest",file_name)   

            # generate GUI from json file 
            self.factory.app.generate_ui(file_name)      
                              
            
class EchoClientFactory(protocol.ClientFactory):
    # print(EchoClient)
    protocol = EchoClient

    def __init__(self, app):
        self.app = app
     
    def startedConnecting(self, connector):
        print("in started connecting")
        self.app.on_message('started to connect.')
        # print(self.__dict__)
        # ConnectScreen().connect_thing("started to connect")

    def clientConnectionFailed(self, connector, reason):
        print('Connection failed. Reason:', reason)    
        if reactor.running:
            reactor.stop()
        if reason.type == error.ConnectionRefusedError:
            print("Connection refused")
        if reason.type == error.TimeoutError:
            print("Timeout")
    
    def clientConnectionLost(self, connector, reason):
        # self.factory.servers.remove(self)
        # connector.connect()
        print('Connection Lost. Reason:', reason)

from kivy.app import App
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.button import Button
from kivymd.uix.button import MDFlatButton
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.textfield import MDTextField
from kivymd.uix.selectioncontrol import MDSwitch
from kivymd.uix.dropdownitem import MDDropDownItem
from kivymd.uix.menu import MDDropdownMenu
from kivy.storage.jsonstore import JsonStore
from kivy.uix.popup import Popup
from kivy.core.window import Window
from kivymd.app import MDApp
from kivymd.font_definitions import theme_font_styles
from kivymd.uix.behaviors import TouchBehavior
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.button import MDRaisedButton

from kivy.lang import Builder
from kivy.metrics import dp
from kivy.clock import Clock
import time
from kivy.properties import ObjectProperty
# import design_file
# import type_layout
# Window.size = (450,700)

KV = '''
#:import toast kivymd.toast.toast
MDBoxLayout:
    id:string_box
    height: self.minimum_height
    size_hint_y : None
    md_bg_color: 1, 1, 1, 1
    MDLabel:
        id:string_control_name
        font_style : "Subtitle1"
        text:"string"             
'''

class TwistedClientApp(MDApp):
    some_text = "hello world" 
    newnew = "dd"
    db = ClientDB()

    def build(self):
        print("in in build")
        # print(self.root.current)
        self.get_things_from_db()

    def authenticate_user_id(self):
        # self.user_id = self.root.ids.user_id.text
        # self.user_pass = self.root.ids.user_pass.text
        self.user_id = "Nayancy"
        self.user_pass = "NG1111@"
        verify_user = self.db.authenticate_user(self.user_id, self.user_pass)
        if(verify_user):
            print("user verified", verify_user)
            self.root.current = 'menu'
        else:
            print("Please enter correct details", verify_user)
            self.root.ids.user_invalid.text = "User invalid! Please enter correct details."

    
    def get_things_from_db(self):
        things_list = {}
        print("inside get_things_from_db")        
        things_list = self.db.get_thing_info()
        # print(things_list)
        if(things_list):
            for i in things_list:
                print("list is",things_list[i]["id"])
                thing_id_curr = things_list[i]["id"]
                (globals()[f"thing_id_curr{thing_id_curr}"]) = things_list[i]["id"]

                (globals()[f"self.manifest_file{thing_id_curr}"]) = things_list[i]["manifest_file"]
        
                print("thing id is",thing_id_curr)
                print("manifest file is",things_list[i]["manifest_file"])
                self.devices_name = MDFlatButton(text = things_list[i]["name"], font_style = "Subtitle1", pos_hint= {"left": 0}, size_hint =(1, 0))
                self.devices_name.id = things_list[i]["manifest_file"]
                self.devices_name.ip = things_list[i]["thing_ip"]
                self.devices_name.port = things_list[i]["thing_port"]
                #self.root.ids.list_of_devices_layout.md_bg_color = 0.5, 0.85, 0.5, 1
                print("i is", i)
                #  here m conatins the device_name flatbutton
                self.devices_name.bind(on_release=lambda m:self.generate_ui_and_connect(m.id,m.ip,m.port))                 
                self.root.ids.list_of_devices_layout.add_widget(self.devices_name)
                
               
            self.clkd_ip = things_list[i]["thing_ip"]
            self.clkd_port = things_list[i]["thing_port"]
            self.thing_id = things_list[i]["id"]                
            print("id is", things_list[i]["id"])
        else:
            self.devices_name = MDLabel(text = "No devices available", font_style = "Subtitle1", halign = "center" )
            self.root.ids.list_of_devices_layout.add_widget(self.devices_name)
            
    def generate_ui_and_connect(self,v1,v2,v3):  
        self.saved_device = "yes"    
        self.make_connection_with_thing(v2,v3)  
        self.generate_ui(v1)
        print("connect data is", v1,v2,v3)


    def connect_to_thing(self,*args):
        print("in connect_to_thing")
        print(self.thing_id, self.clkd_ip, self.clkd_port)
        self.make_connection_with_thing(self.clkd_ip, self.clkd_port)


    def generate_ui(self,file_name):     
        print("in generate UI")   
        self.root.current = 'ui_generation'
        # Builder.load_file('ui.kv')
        # store = JsonStore('ac.json')
        print("m f name",file_name)
        store = JsonStore(file_name)        
        self.device = store.get('DEVICE')
        self.control = store.get('CONTROL')
        self.mode = store.get('MODE')

        # Device name text
        self.root.ids.device_name.text = self.device["NAME"]
       
        # Control's list
        for i in self.control:
            self.control_name = i
            self.b1 = MDLabel(
                text = i
            )
            self.control_ui_generation(self.control[i],"ititial_call",0)
            
        # mode's list 
        for j in self.mode:
            self.b2 =MDFlatButton(
                text = j
            )
            
            self.root.ids.grid_mode.add_widget(self.b2)


    def control_ui_generation(self, ctrl,call,count_time):
        if(call is "struct_call"):
            pass

        # print("control is",ctrl)
        for c in ctrl:            
            if(c == "BOOLEAN"):
                self.boolean_control_handler(ctrl[c])
            elif(c == "NUMERIC"):
                self.numeric_control_handler(ctrl[c],call)                    
            elif(c == "STRING"):
                self.string_control_handler(ctrl[c])
            elif(c == "STRUCT"):
                self.struct_control_handler(ctrl[c])
            else:
                print("Not a valid type")


    def struct_control_handler(self,ctrl):
        self.struct_data = ctrl["struct"]
        count = len(self.struct_data)
        print("struct len",count)    
        self.struct_layout_outer = MDBoxLayout(orientation = 'vertical',size = ("20dp", "150dp"),size_hint_y= None)
        self.struct_layout_inner = MDBoxLayout(orientation = 'horizontal')
        self.struct_control_name = MDLabel(text = self.control_name, font_style = "Subtitle1")
        
        self.struct_layout_outer.add_widget(self.struct_control_name)
        
        for s in self.struct_data:
            # print(s)        
            # print(type(s))
            # self.root.ids.control_info.spacing = "0dp"   
            self.control_name = s         
            self.control_ui_generation(self.struct_data[s],"struct_calling",count)  
            count = count - 1

        self.struct_layout_outer.add_widget(self.struct_layout_inner)
        self.root.ids.control_info.add_widget(self.struct_layout_outer)

    def boolean_control_handler(self,ctrl):
        
        cname = self.control_name
        (globals()[f"cname{cname}"]) = self.control_name
        (globals()[f"self.false_value{cname}"]) = ctrl[0]
        (globals()[f"self.true_value{cname}"]) = ctrl[1]

        self.boolean_layout = MDBoxLayout(size = ("20dp", "80dp"),size_hint_y= None)
        self.boolean_layout.md_bg_color = 1, 1, 1, 1
        self.boolean_layout.line_color = (0.2, 0.2, 0.2, 0.1)
        self.boolean_layout.pos_y = 15
        # self.boolean_layout.size_hint_y = .2
        self.bool_control_name = MDLabel(size_hint_x = .5, text = self.control_name, pos=(100,20), font_style = "Subtitle1")
        self.f_val = MDLabel(size_hint_x = .2, halign = "right", text = (globals()[f"self.false_value{cname}"]))
        self.bool_switch = MDSwitch(size_hint_x = .1, pos_hint = {"bottom":.8})
        self.t_val = MDLabel(size_hint_x = .2, text = (globals()[f"self.true_value{cname}"]))
        
        self.boolean_layout.add_widget(self.bool_control_name)
        self.boolean_layout.add_widget(self.f_val)
        self.boolean_layout.add_widget(self.bool_switch)
        self.boolean_layout.add_widget(self.t_val)

        self.bool_switch.bind(active=lambda *args:self.set_boolean_value(globals()[f"cname{cname}"],(globals()[f"self.false_value{cname}"]),(globals()[f"self.true_value{cname}"]),*args))
            
        self.root.ids.control_info.add_widget(self.boolean_layout)



    def numeric_control_handler(self,ctrl,call):
        cname = self.control_name
        print("cname is", cname)
        globals()[f"cname{cname}"] = self.control_name
        globals()[f"self.min_range{cname}"] = ctrl["RANGE"][0][0]
        globals()[f"self.max_range{cname}"] = ctrl["RANGE"][0][1]
        globals()[f"self.step_size{cname}"] = ctrl["RANGE"][0][2]
        globals()[f"self.operation{cname}"] = ctrl["RANGE"][0][3]
        globals()[f"self.unit{cname}"] = ctrl["RANGE"][0][4]        
        # print("max_rangemax_range is", self.max_rangeTemperature)

        # numeric layout
        self.numeric_layout_outer = MDBoxLayout(orientation = 'vertical', size = ("20dp", "100dp"),size_hint_y= None)
        self.numeric_layout = MDBoxLayout()
        self.numeric_layout_outer.md_bg_color = 1, 1, 1, 1
        self.numeric_layout_outer.line_color = (0.2, 0.2, 0.2, 0.1)   
        self.numeric_control_name = MDLabel(text = self.control_name, size_hint_x = 1, pos_hint= {"left":.5}, font_style = "Subtitle1")                
        self.minus_button = MDFlatButton(size_hint_x = .2, text = "-", pos_hint= {"top":1})
        
        
        globals()[f"self.value_label{cname}"] = MDLabel(size_hint_x = .3, halign = "right", text = str(ctrl["RANGE"][0][0]))
        self.root.ids['control_val'] = globals()[f"self.value_label{cname}"] 
        self.unit_value = MDLabel(size_hint_x = .4, halign = "left", text = globals()[f"self.unit{cname}"])
        self.plus_button = MDFlatButton(size_hint_x = .2, text = "+", pos_hint= {"top":1})
        
        # self.step_size = self.control[i]["range"][2]
        # print(self.step_size)globals()[f"cname{cname}"]
        self.minus_button.bind(on_press=lambda x:self.set_value_minus(globals()[f"cname{cname}"]))
        self.plus_button.bind(on_press=lambda x:self.set_value_plus(globals()[f"cname{cname}"]))
            
        # self.numeric_layout.add_widget(self.numeric_control_name)
        self.numeric_layout.add_widget(self.minus_button)                 
        self.numeric_layout.add_widget(globals()[f"self.value_label{cname}"])
        self.numeric_layout.add_widget(self.unit_value)
        self.numeric_layout.add_widget(self.plus_button)
        # print(self.screen.parent)
        # print("numeric_control_handler")
        self.numeric_layout_outer.add_widget(self.numeric_control_name)
        self.numeric_layout_outer.add_widget(self.numeric_layout) 
        
        if(call is "struct_calling"):
            self.struct_layout_inner.add_widget(self.numeric_layout_outer)
        else:
            self.root.ids.control_info.add_widget(self.numeric_layout_outer) 

    def focus_menu(self, *args):
        print("inside1 focus")
        # for i in args:
        #     print(i)
        print("inside focus")
        if args[2]:
            print('User focused')
            # print(args[1]))
            globals()[f"self.menu{args[0]}"].open()
            # print("inside focus end")
        else:
            print('User defocused', args[1])

    def string_control_handler(self,ctrl): 
        self.option = ctrl["OPTION"]
        cname = self.control_name
        (globals()[f"cname{cname}"]) = self.control_name
        # print("option_len",len(self.option))
        
        self.screen = Builder.load_string(KV)
        globals()[f"self.menu_text{cname}"] = MDTextField(text = self.option[0])
         
        self.screen.ids.string_control_name.text = self.control_name
        globals()[f"self.menu_text{cname}"].bind(focus=lambda *args:self.focus_menu(globals()[f"cname{cname}"], *args))
        
        self.screen.ids.string_control_name.parent.add_widget(globals()[f"self.menu_text{cname}"])   
        
        # print("variousvariod id",self.screen.ids.string_control_name.parent)
          
        menu_items = [
            {
                "text": f"{i}",
                "height": dp(56),
                "viewclass": "OneLineListItem",
                "on_release": lambda x=f"{i}": self.set_item(x,(globals()[f"cname{cname}"])),
            } for i in self.option
        ]      

        globals()[f"self.menu{cname}"] = MDDropdownMenu(
            caller=self.screen.ids.string_control_name,
            items=menu_items,
            width_mult=4,
        )       
        print("globals",globals()[f"self.menu{cname}"])
        # print(self.menuFan1)
        print("menu_items", menu_items)
        self.screen.line_color = 0.2, 0.2, 0.2, 0.1       
        self.root.ids.control_info.add_widget(self.screen)

    def set_item(self, text_item,cname):
        print(text_item)
        self.send_invoke_msg(cname,text_item)
        print("h111")
        globals()[f"self.menu_text{cname}"].text = text_item
        print("h222")
        globals()[f"self.menu{cname}"].dismiss() 
        print("h333") 

    def set_boolean_value(self, *args):
        print("start print")
        for i in args:
            print(i)
        print("inside set_boolean value window")        
        print("control name is",args[0])
        if(args[4]):
            val = args[2]
        else:
            val = args[1]  
        print("value is ",val)        
        self.send_invoke_msg(args[0],val)

    def set_value_minus(self, c_name):
        print("inside set_value minus window")       
        # c_name globals()[f"variable1{x}"]
        curr_val = globals()[f"self.value_label{c_name}"].text
        step_diff = globals()[f"self.step_size{c_name}"]
        step_diff_type = type(step_diff)
        curr_val_type = type(curr_val)        
        print("curr_val",curr_val)
        # curr_val = int(float(curr_val))
        if(step_diff_type is float or step_diff_type is int):
            curr_val = float(curr_val)
            step_diff = float(step_diff)
        else:
             print("step size is non-numeric")
             return
        if(globals()[f"self.operation{c_name}"] == '+'):
            if(globals()[f"self.min_range{c_name}"] < curr_val):       
                curr_val = curr_val - step_diff
                curr_val = str(curr_val)
                self.send_invoke_msg(c_name,curr_val)
                # check the device response and update accordingly
                globals()[f"self.value_label{c_name}"].text = curr_val
                # print(self.__dict__)
            else:
                print("can not lower the value. Out of range.")
        elif(globals()[f"self.operation{c_name}"] == '*'):
            if(globals()[f"self.min_range{c_name}"] < curr_val):       
                curr_val = float(curr_val)
                curr_val = curr_val / step_diff
                curr_val = str(curr_val)
                self.send_invoke_msg(c_name,curr_val)
                globals()[f"self.value_label{c_name}"].text = curr_val
                # print(self.__dict__)
            else:
                print("can not lower the value. Out of range.")
        elif(globals()[f"self.operation{c_name}"] == '-1'):
            print("HP need to be implemented")           
            curr_val = float(curr_val)
            print(step_diff)
            curr_val = 1/((1/curr_val)-step_diff)
            curr_val = str(curr_val)
            self.send_invoke_msg(c_name,curr_val)
            globals()[f"self.value_label{c_name}"].text = curr_val
                
             
        else:
            print("not a valid operation type") 

    def set_value_plus(self, c_name):
        print("inside set_value plus window")
        curr_val = globals()[f"self.value_label{c_name}"].text
        step_diff = globals()[f"self.step_size{c_name}"]
        step_diff_type = type(step_diff)
        curr_val_type = type(curr_val)        
        print("curr_val",curr_val)
        if(step_diff_type is int or step_diff_type is float):
            curr_val = float(curr_val)
            step_diff = float(step_diff)   
        else:
            print("step size is non-numeric")
            return
        
        if(globals()[f"self.operation{c_name}"] == '+'):
            if(curr_val < globals()[f"self.max_range{c_name}"]):
                curr_val = curr_val + step_diff
                print("cu",curr_val,type(curr_val),step_diff,type(step_diff))
                curr_val = str(curr_val)
                self.send_invoke_msg(c_name,curr_val)
                globals()[f"self.value_label{c_name}"].text = curr_val
            else:
                print("can not further increase the value. Out of range.")
        elif(globals()[f"self.operation{c_name}"] == '*'):
            if(curr_val < globals()[f"self.max_range{c_name}"]):       
                curr_val = curr_val * step_diff
                curr_val = str(curr_val)
                self.send_invoke_msg(c_name,curr_val)
                globals()[f"self.value_label{c_name}"].text = curr_val
                # print(self.__dict__)
            else:
                print("can not further increase the value. Out of range.")
        elif(globals()[f"self.operation{c_name}"] == '-1'):
             
            curr_val = float(curr_val)
            print(step_diff)
            print("curr_val is",curr_val)
            curr_val = 1/((1/curr_val)+step_diff)
            curr_val = str(curr_val)
            self.send_invoke_msg(c_name,curr_val)
            globals()[f"self.value_label{c_name}"].text = curr_val 

        else:
            print("not a valid operation type")    
  
    def send_invoke_msg(self,control_name,value):
        print("iconnect_to_servernside send_invoke msg.")   
        print(control_name)   
        value = "Invoke:"+"set:"+control_name+":"+value
        print(value)
        # self.cur_v = value
        # invoke_packet = ["invoke","set",control,value]
        invoke_packet = "invoke,set,control,value"

        self.send_data(value)
        

    
    def on_connect(self, conn):
        print('-- connected')
        # self.conn = conn
        # print(self.server_type)  
        if (self.server_type == "thing"):
            self.conn1 = conn
            if(self.saved_device == "no"):
                self.probe_request("Probe")
        elif(self.server_type == "oem_server"):
            self.conn2 = conn
            self.device_verification()
 
        # self.root.current = 'connect_screen'

    def send_data_oem(self,data): 
        self.data = data
        self.conn2.write(self.data.encode("utf-8"))

    def send_data(self,data): 
        self.data = data
        # print("in thing send data", self.data)
        self.conn1.write(self.data.encode("utf-8"))    
    
    def make_connection_with_thing(self,ip,port):
        print("d_data1 is")
        self.root.current = 'connect_screen'
        self.server_type = "thing"
        self.connect_to_server(ip,port,self.server_type);    
   
    # This fruntion is being called from .kv file
    def make_connection(self,name,id,ip):
        self.thing_name = name
        self.thing_id = id
        self.thing_ip = ip
        print("d_data1 is")
        self.root.current = 'connect_screen'
        self.server_type = "thing"
        self.connect_to_server("localhost",8001,self.server_type);    
   
    # This fruntion is being called from .kv file
    def registration_make_connection(self,name,id,ip):
        self.thing_name = name
        self.thing_id = id
        self.thing_ip = ip
        print("d_data is")
        self.root.current = 'connect_screen'
        self.server_type = "thing"
        self.connect_to_server("localhost",8001,self.server_type);    
    
    def connect_to_server(self,ip,port,server_type):
        self.ip = ip
        self.port = port
        self.server_id = server_id+1
        self.server_type = server_type
        print("server id is",server_id)
        print("server type is",server_type)
        reactor.connectTCP(self.ip, self.port, EchoClientFactory(self))    
    
    def on_message(self, msg):
        self.msg = msg
        print(self.msg)
        self.root.ids.connect_status.text = msg
        # print("self",self)
        # print("self.root",self.root)
        # print("self.root.ids",self.root.ids)
        # print("self.root.ids.connect_status",self.root.ids.connect_status)
        
    
    def password_handle(self,data):
        self.root.current = 'input_pass_screen'

    def device_verification(self):
        self.thing_name = self.root.ids.device_name1.text        
        self.thing_id = self.root.ids.device_id.text
        self.thing_pass = self.root.ids.device_pass.text
        # self.thing_name = "AC"
        print("device id is",self.thing_id)
        print(self.thing_pass)
        # device_info = "verify"+ ":" +device_id+":"+device_pass
        thing_info = "verify" + ":" +self.user_id + ":" + self.user_pass+ ":" +self.thing_id + ":" + self.thing_pass
        # self.conn.write(device_info.encode("utf-8"))
        self.send_data_oem(thing_info)
 
    def connect_to_oem(self):
        # connecting with OEM via cloud to verify the device id and password
        server_type = "oem_server"
        self.oem_address = self.root.ids.oem_ip.text
        self.oem_address = self.oem_address.split(':')
        
        self.oem_ip = self.oem_address[0]
        self.oem_port  = int(self.oem_address[1])
        print("oem ip and port is",self.oem_ip,self.oem_port)
        
        self.connect_to_server(self.oem_ip,self.oem_port,server_type); 
    
    def probe_request(self,data):
        print("inside probe request")
        print(data)
        self.send_data(data)
    
    def req_thing_address(self):
        print("inside111 req_thing_address",self.thing_id,self.thing_pass)
        data = "req_add:"+self.thing_id+":"+self.thing_pass
        self.send_data_oem(data)
    
if __name__ == '__main__':
    TwistedClientApp().run()
