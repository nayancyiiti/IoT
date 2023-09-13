# install_twisted_rector must be called before importing the reactor
from __future__ import unicode_literals
from kivy.support import install_twisted_reactor
install_twisted_reactor()
from twisted.internet import error

from twisted.internet.protocol import Protocol, Factory
from twisted.internet import reactor
from twisted.internet.protocol import ServerFactory as ServFactory, connectionDone
from twisted.internet.endpoints import TCP4ServerEndpoint
# import sys
# print(sys.path) 

class Echo_thing(Protocol):
    count = 0
    regis = 0
    
    def connectionMade(self):
        print("connection made")
        
    def check_pass_requirement(self):
        return True

    def probe_handler(self, data):        
            file = open("ac_json/ac.json",'r')
            # print("file opened")
            f = file.read()
            file.close() 
            file_name = file.name          
            f = file_name+":file:"+f            
            self.transport.write(f.encode('utf-8'))

    def dataReceived(self, data):
        data = data.decode("utf-8")
        # print(data,"\n")
        if("Probe" in data):
            # print(data,"\n")
            self.probe_handler(data)
              
        if("Invoke" in data):
            # print(data,"\n")
            self.factory.app.invoke_handler(data)


    def connectionLost(self, reason=connectionDone):
        # self.disconnect()
        pass

class EchoServerFactory(Factory):
    protocol = Echo_thing

    def __init__(self, app):
        self.app = app


from kivymd.app import MDApp
from kivy.core.window import Window
Window.size = (450,700)


class AcApp(MDApp):
    
    def build(self):
        reactor.listenTCP(8004, EchoServerFactory(self))
        return 

    def invoke_handler(self, data):
        print("invoke data is",data)         
        if("16.5" in data):
            print("16.5 data")
            self.root.ids.image.source = 'ac1.png'
        elif("16" in data):   
            print("16 data") 
            self.root.ids.image.source = 'ac.png'
        else:
            print(data)             

if __name__ == "__main__":
    AcApp().run()
