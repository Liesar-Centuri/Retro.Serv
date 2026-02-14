This progect is meant to facilitate local copying of files on a large range of hardware through a simple webserver.

To start the project:

  1. Create a directory and copy the project into it.
  2. Create a new folder in the same directory, note the name as it will be used later to start the server.
  3. Open a command prompt in the main project directory
  4. Type in the following command: pythonb server.py 8000 -b (Created Folder Name)
  5. Use the local ip of the machine, paired with port 8000 to connect to the server.

Requirements:
  Python 3.13.9
  Windows (Not tested on linux)

This project is still in early stages of development, bugs are expected!

Note: This webpage has minimal security by design to allow older browsers to access it, as such **DO NOT** expose this server to a public network!
