#Kelly Chibuike Ojukwu

# A simple server that handles requests and sends files
import socket
import select
import sys
import re
import signal
import queue
from datetime import datetime as dt
import os


'''
    Example: HTTP Request
    ● HTTP Request = Request line + Header fields + Empty line
    ● Request line (case sensitive):
    ○ GET /filename HTTP/1.0
    ● Each header field:
    ○ Case-insensitive field name
    ○ Colon (“:”)
    ○ Optional leading whitespace
    ○ Case-insensitive field value
    ○ Optional trailing whitespace
    ● Correct format:
    ○ GET /filename HTTP/1.0\r\nConnection:Keep-alive\r\n\r\n
    ○ GET /filename HTTP/1.0\r\nConnection: keep-alive\r\n\r\n
    ○ GET /filename HTTP/1.0\r\n\r\n
    ○ On Windows, a newline is denoted with “\r\n”
    ○ On Unix-like operating systems, “\n” = “\r\n” (your code should support both)
'''


TIMEOUT_TIME = 30
# A map that holds all info on a specific socket relevant to the server:
# Includes time of creation, timeout time etc
# Has the following schema socket 
signal.signal(signal.SIGTSTP, signal.SIG_IGN)
# Sockets we are looking to read from
input_sockets = []
# Scokets we are looking to write to
output_sockets = []


socket_map = {}

socket_info = {"last_line": None,
               "requests" : [],
               "last accessed time": None
               
               }


requests_response = {
    200: "OK",
    400: "Bad Request",
    404: "Not Found",}

persistent_map = {
    True: "keep-alive",
    False: "close",
    
}

http_response_start = "HTTP/1.0"
http_response_response_end = "\r\nConnection: "
http_bad_request_response_end = " close\r\n\r\n"

# Handles new line and forbidden char differences between Unix-like and Windows OS
forbbidden_chars = "[/]"

next_line_char = "\\r\\n|\\n" #"\n\r|\n"
'''if sys.platform.startswith('win'):
    next_line_char = "\r\n"
    forbbidden_chars = "[\\<\\>\\:\"\\\/\\|\\?\\*]"
'''
# Map of queues for outgoing messages, ensures that message is sent to the client end of socket that triggered it
message_queues = {}
requests_map = {}

def close_socket(t_socket: socket):
    global output_sockets
    global input_sockets
    if t_socket in input_sockets: input_sockets.remove(t_socket)
    if t_socket in output_sockets: 
        output_sockets.remove(t_socket)
    t_socket.close()

def main(ip_address, port_number: int):
    # Create a socket for the server that is non-blocking and bind it to a port
    
    my_ip_address = ip_address
    # Create the socket for the server and put it into input sockets array
    server_socket = ServerSocketManager.create_socket(my_ip_address, port_number)
    server_socket_holder = SocketHolder(server_socket, None, None)
    global input_sockets

    input_sockets = [server_socket]
    global output_sockets
    exception_sockets = []
    while (input_sockets):
        # Wait until we have a socket to read/write/exception 
        readable, writable, exceptions = select.select(input_sockets, output_sockets, exception_sockets)
        
        # Kill elderly sockets
        for s in output_sockets:
            if socket_map[s].should_socket_kill():

                close_socket(s)
                
        
        for the_socket in readable:
            #The server socket is ready to accept a connection
            if the_socket is server_socket:

                # Create a socket for communication with the client and put it in a socketHolder object
                client_socket, address = the_socket.accept()
                
                client_socket.setblocking(0)
                socket_holder = SocketHolder(client_socket,None, address)

                # Create relationship between socket's map and holder
                socket_map[client_socket] = socket_holder
                input_sockets.append(client_socket)
                message_queues[client_socket] = queue.Queue()


            # There is a client socket that wants to message server
            else:
                #Receive the data from the client
                # try:
                data = the_socket.recv(1024).decode()
                # except OSError:
                #     continue

                #Process the data and transform it into a map of arrays of requests (finished and wip)
                if data:
                    socket_holder = socket_map[the_socket]
                    if the_socket not in output_sockets:
                        output_sockets.append(the_socket)
                        requests_map = socket_holder.process_input(data)

                    
                else:
                    # No data but activity -> closed
                    close_socket(the_socket)

        for the_socket in writable:
            socket_holder = socket_map[the_socket]
            try:

                next_request = socket_holder.get_requests_queue().get_nowait()
            except queue.Empty:
                if the_socket in output_sockets:
                    output_sockets.remove(the_socket)
                pass
            else:

                socket_holder.process_request(next_request)
 

def is_valid_request(request:str)->bool:
    #valid_http_request = "GET /.*\s+HTTP/1.0\s*"
    valid_http_request = 'GET /((\S*)|(".*"))\s* HTTP/1.0\s*'

    '/((\S+)|(".*"))\s* HTTP'
    matched_request = re.fullmatch(valid_http_request, request)
    if matched_request is not None:
        return True
    return False
    
def is_valid_header(request:str)->bool:
    valid_http_header = ("Connection:\s*(Keep-alive|close)\s*|\s*")
    matched_header = re.fullmatch(valid_http_header, request, flags= re.I)
    if matched_header is not None:
        return True
    return False



class SocketHolder:
    the_socket = None
    last_accessed_time = None
    #A list with each line that has been given to the server from the respective client
    input_list = None
    persistent = False
    input_message = None
    unprocessed_message = None
    actualized_requests = None
    valid_requests = None
    potential_requests = None
    address = None
    output_queue = None
    requests_queue = None

    def __init__(self, socket, creation_time, address_tuple):
        self.address = address_tuple
        self.the_socket = socket
        self.last_accessed_time = dt.now()
        self.input_message = str()
        self.potential_requests = []
        self.requests_queue = queue.Queue()

        self.valid_requests = []
        self.actualized_requests = []

    def get_persistence(self):
        return self.persistent

    def get_requests_queue(self):
        return self.requests_queue
    


    # Checks if connection has violated timeout
    def should_socket_kill(self):
        current_time = dt.now()
        if (current_time - self.last_accessed_time).seconds >= 30:
            return True
        return False
    
    def set_persistent(self, input: bool):
        self.persistent = input
        
    def add_to_input_list(self,input:str):
        self.input_list.add(input)
        end_line_match = re.fullmatch(next_line_char)
        #We're at the end of a request
        if end_line_match is not None:
            return
        
    #Takes in an input string and adds it to requests queue
    def process_input(self, input: str):
        self.last_accessed_time = dt.now()
        # Split apart the input into a string array line by line. 
        # An item in the array with all whitespace characters represents a double new line
        self.potential_requests.extend(input.splitlines())
        #print("Init state of potential requests: ",self.potential_requests)
        actualized_requests = []
        index = 0

        
      

        while index < len(self.potential_requests):
            # Check if the request is invalid (ignore empty lines before a request)
            
            if not is_valid_request(self.potential_requests[0]) :
                #If we have leading whitespace before get requests
                if re.match("\S", self.potential_requests[0]) is None:
                    self.potential_requests.pop(0)
                    index = 0
                    continue
                self.potential_requests.pop(0)
                for thing in actualized_requests:

                    self.process_request(thing)
                self.set_persistent(False)
                self.print_to_server(self.potential_requests[0], 400)

                self.send_header(400)
                
                #close_socket(self.the_socket)
                #Stop after bad request
                #actualized_requests = None
                #Kill the connection

                # Stop actualized requests list at the first badly formed request line
                return {"finished":actualized_requests}
            
            #Longer than 2 lines for request
            if index > 2:
                close_socket(self.the_socket)
                return {"finished": actualized_requests}
                
            
            # If we have found a double new line in our text (end of request)
            if re.match("\S", self.potential_requests[index]) is  None:
                
                
                #Get everything before the double new line and add to list of complete requests
                request = self.potential_requests[:index]
                if len(request) != 0:
                    actualized_requests.append(request)
                    self.requests_queue.put(request)
                self.potential_requests.pop(0)
                for i in range(0, index):
                    self.potential_requests.pop(0)
                index = 0
                continue
            
        
            index = index+1

        for request in self.potential_requests:
            if not is_valid_request(request) and not is_valid_header(request):
                self.potential_requests.remove(request)
        
        return {"finished": actualized_requests,
                "wip": self.potential_requests}
    
    # Processes requests that have been verified to have a proper first line and size of 2 at most
    def process_request(self, request: []):
        self.last_accessed_time = dt.now()
        self.persistent = False
        request_line = request[0]
        temp_file_name = re.search('/((\S*)|(".*"))\s* HTTP',request_line).group()
        if not temp_file_name.__contains__('"'):
            temp_file_name = re.split("\s",temp_file_name)[0]
        else:
            temp_file_name = re.search('(".*")').group()
        #Remove space after file name and HTTP tag
        file_name = temp_file_name[1:]#[1:len(temp_file_name)-5]

        if file_name == "":
            file_name = "index.html"


        header_line = None
        #A good request will at most have 2 linesbind(
        '''if len(request ) > 2:
            print("Bad request")
            return
        '''
        

        if is_valid_request(request_line) :
            if len(request) > 1:
                header_line = request[1]
                if not is_valid_header(header_line):
                    
                    request[1] = "Connection: close"
                    self.send_file(file_name, request)
                else:
                    # Valid request with valid header
                    self.send_file(file_name, request)
                
            else:
                #Valid request
                request.append("Connection: close")
                self.send_file(file_name, request)
            
        else:
            self.set_persistent(False)
            self.print_to_server(self.potential_requests[0], 400)
            self.send_header(400)
            #print("Bad request")
            
        return
    
    #Preps a header to be sent to a client's terminal
    def send_header(self, response_code):
        self.send_to_client(self.gen_header(response_code))
        if response_code == 400:

            close_socket(self.the_socket)

    def gen_header(self, response_code):
        return "HTTP/1.0 " + str(response_code) +" "+ requests_response[response_code] +"\r\nConnection: " + persistent_map[self.persistent] +"\r\n\r\n"


    #Preps a file to be sent to a client's terminal
    def send_file(self,file_name, request):
        file_contents = None
        #open(file_name).read()
        keep_alive_regex = "\s*Connection:\s*keep-alive\s*"
        if re.match(keep_alive_regex, request[1], re.I) is not None:
            self.set_persistent(True)
        try:
            file_contents = open(file_name).read()
        except FileNotFoundError:

            


            self.send_header(404)

            self.print_to_server(request[0], 404)
            if not self.persistent:
                
                close_socket(self.the_socket)
            pass
            #input_sockets.remove(self.the_socket)
            # Close the connection
            #del self
            
            return

        #self.the_socket.send(file_contents)
        self.print_to_server(request[0], 200)
        self.send_header(200)
        self.send_to_client(file_contents)

    # Sends a string message to a client's terminal
    def send_to_client(self, message):
        total_sent = 0
        message_size = sys.getsizeof(message)-49
        while total_sent < message_size :
            bytes_sent = self.the_socket.send(message[total_sent:].encode())
            total_sent = total_sent + bytes_sent

    def print_to_server(self, request, response_code):
        curr_time = dt.now()
        response = self.gen_header(response_code).split("\n")
        time_str = curr_time.strftime("%a %b %d %H:%M:%S ")
        time_zone = curr_time.astimezone().strftime("%Z")
        year_str = curr_time.strftime(" %Y")

        message = time_str + time_zone + year_str +": "+ str(self.address[0]) + ":" +str(self.address[0]) + request + "; "+ response[0]
        print(message)



# Class on seperate thread that waits asynchronously so that sockets can be created at any time and added to a queue
class ServerSocketManager:

    # Used to enforce condition that only one socket is opened for each connection
    open_sockets = {}
    def self(self):
        return

    # Create a new socket and bind it to an ip address and port number

    def create_socket(ip_address: str, port_number: int) -> socket:
            address_tuple = (ip_address, port_number)
            new_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            new_socket.setsockopt(socket.SOL_SOCKET,  socket.SO_REUSEADDR, 1)
            #new_socket.setblocking(0)

            new_socket.bind(address_tuple)
            new_socket.listen(5)
            #new_socket.accept()
            return new_socket


    def kill_socket(self, socket_id):
        target_socket = self.open_sockets[socket_id]
        if target_socket is not None:
            target_socket
            self.open_sockets.pop(socket_id)










# Take in input line by line, when double new line is found then put request in request array
ip_address = sys.argv[1]
port_num = sys.argv[2]

main(ip_address, int(port_num))
