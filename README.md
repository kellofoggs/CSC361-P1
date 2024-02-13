This simply python http server uses standard python libraries. 
To run the server type "python3 sws.py <ip-address> <port_number>" in the terminal
In another terminal use something like netcat to interact with the server and make requests to it

The server supports GET requests w/ and w/o persistence and can respond with 200, 400, and 404 file not found responses
The server also automatically disconnects a client that has been idle for the past 30 seconds and will print out a log entry after every request is processed
